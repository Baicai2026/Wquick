#include "parser.h"
#include <stdexcept>
#include <sstream>

Parser::Parser(std::vector<Token> t) : tokens(std::move(t)), pos(0) {}

Token& Parser::peek(int offset) {
    size_t p = pos + offset;
    if (p >= tokens.size()) return tokens.back();
    return tokens[p];
}

Token& Parser::advance() {
    Token& t = tokens[pos];
    if (pos + 1 < tokens.size()) pos++;
    return t;
}

bool Parser::check(TokenType t) const {
    if (pos >= tokens.size()) return false;
    return tokens[pos].type == t;
}

bool Parser::match(TokenType t) {
    if (check(t)) { advance(); return true; }
    return false;
}

Token Parser::expect(TokenType t, const std::string& msg) {
    if (!check(t)) {
        std::ostringstream oss;
        oss << "[Line " << peek().line << "] Parser error: expected " << msg
            << ", got '" << peek().value << "'";
        throw std::runtime_error(oss.str());
    }
    return advance();
}

// =================== 主解析入口 ===================

std::unique_ptr<ProgramNode> Parser::parse() {
    std::vector<StmtPtr> stmts;
    while (!check(TokenType::EOF_TOKEN)) {
        stmts.push_back(parseStmt());
    }
    return std::make_unique<ProgramNode>(std::move(stmts));
}

// =================== 语句列表（到某个stopLabel为止）===================
std::vector<StmtPtr> Parser::parseStmtList(TokenType stop1, TokenType stop2) {
    std::vector<StmtPtr> stmts;
    while (!check(stop1) && !check(stop2) && !check(TokenType::EOF_TOKEN)) {
        stmts.push_back(parseStmt());
    }
    return stmts;
}

// =================== 语句路由 ===================
StmtPtr Parser::parseStmt() {
    // 跳过 import:0; 这样的无操作import
    if (check(TokenType::IMPORT)) return parseImport();
    if (check(TokenType::LET))    return parseVarDecl();
    if (check(TokenType::IF))     return parseIf();
    if (check(TokenType::FOR))    return parseFor();
    if (check(TokenType::WHILE))  return parseWhile();
    if (check(TokenType::RETURN)) return parseReturn();
    if (check(TokenType::BREAK))  return parseBreak();
    if (check(TokenType::CONTINUE)) return parseContinue();

    // 标签语句
    if (check(TokenType::LABEL_START))    return parseLabelStart();
    if (check(TokenType::LABEL_DEF))      return parseLabelDef();
    if (check(TokenType::LABEL_LOOP))     return parseLabelLoop();
    if (check(TokenType::LABEL_SWITCH))   return parseLabelSwitch();
    if (check(TokenType::LABEL_FILE))     return parseLabelFile();
    if (check(TokenType::LABEL_TEMPLATE)) return parseLabelTemplate();
    if (check(TokenType::LABEL_NAMESPACE))return parseLabelNamespace();
    if (check(TokenType::LABEL_CLASS))    return parseLabelClass();

    // output/input 内置
    if (check(TokenType::IDENTIFIER) && peek().value == "output") return parseOutput();
    if (check(TokenType::IDENTIFIER) && peek().value == "input")  return parseInput();

    // 表达式语句（赋值、调用、ioplus等）
    ExprPtr e = parseExpr();

    // 检测是否是 ioplus 流语句
    if (check(TokenType::ARROW_RIGHT)) {
        // iplus -> a -> b -> c;
        return parseIOPlusInput(std::move(e));
    }
    if (check(TokenType::ARROW_LEFT)) {
        // oplus <- a <- b;
        return parseIOPlusOutput(std::move(e));
    }

    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<ExprStmt>(std::move(e));
}

// =================== import ===================
StmtPtr Parser::parseImport() {
    advance(); // import
    expect(TokenType::COLON, ":");
    std::string mod;
    if (check(TokenType::INTEGER) && peek().value == "0") {
        advance(); // 0 表示不导入
        mod = "0";
    } else if (check(TokenType::IDENTIFIER)) {
        mod = advance().value;
    } else {
        mod = advance().value;
    }
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<ImportStmt>(mod);
}

// =================== 变量声明 ===================
StmtPtr Parser::parseVarDecl() {
    advance(); // let
    std::string typeName;
    bool isConst = false;

    // 解析 <类型> 或 <const> 或 <数组类型>
    if (check(TokenType::LT)) {
        typeName = parseTypeName();
        if (typeName == "const") {
            isConst = true;
            typeName = "";
        }
    }

    std::string name = expect(TokenType::IDENTIFIER, "variable name").value;

    // 数组声明: let <int> arr[5]; 或 let <int> arr = [...];
    if (check(TokenType::LBRACKET)) {
        advance();
        ExprPtr sz = parseExpr();
        expect(TokenType::RBRACKET, "]");
        expect(TokenType::SEMICOLON, ";");
        return std::make_unique<ArrayDeclStmt>(typeName, name, std::move(sz),
                                               std::vector<ExprPtr>());
    }

    ExprPtr init;
    if (match(TokenType::ASSIGN)) {
        // 检查是否是数组字面量
        if (check(TokenType::LBRACKET)) {
            advance();
            std::vector<ExprPtr> elems;
            if (!check(TokenType::RBRACKET)) {
                elems.push_back(parseExpr());
                while (match(TokenType::COMMA)) {
                    elems.push_back(parseExpr());
                }
            }
            expect(TokenType::RBRACKET, "]");
            expect(TokenType::SEMICOLON, ";");
            return std::make_unique<ArrayDeclStmt>(typeName, name, nullptr, std::move(elems));
        }
        init = parseExpr();
    }
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<VarDeclStmt>(typeName, isConst, name, std::move(init));
}

// =================== 类型名解析 <int> ===================
std::string Parser::parseTypeName() {
    expect(TokenType::LT, "<");
    std::string t;
    if (check(TokenType::INT_KW))    { t = "int";    advance(); }
    else if (check(TokenType::FLOAT_KW))  { t = "float";  advance(); }
    else if (check(TokenType::CHAR_KW))   { t = "char";   advance(); }
    else if (check(TokenType::STRING_KW)) { t = "string"; advance(); }
    else if (check(TokenType::BOOL_KW))   { t = "bool";   advance(); }
    else if (check(TokenType::CONST_KW))  { t = "const";  advance(); }
    else if (check(TokenType::IDENTIFIER)){ t = advance().value; }
    else t = advance().value;
    expect(TokenType::GT, ">");
    return t;
}

// =================== if/elif/else ===================
StmtPtr Parser::parseIf() {
    std::vector<IfBranch> branches;
    // if
    advance(); // if
    expect(TokenType::LPAREN, "(");
    ExprPtr cond = parseExpr();
    expect(TokenType::RPAREN, ")");
    expect(TokenType::LBRACE, "{");
    auto body = parseStmtList(TokenType::RBRACE);
    expect(TokenType::RBRACE, "}");
    branches.push_back({std::move(cond), std::move(body)});

    // elif*
    while (check(TokenType::ELIF)) {
        advance();
        expect(TokenType::LPAREN, "(");
        ExprPtr ec = parseExpr();
        expect(TokenType::RPAREN, ")");
        expect(TokenType::LBRACE, "{");
        auto eb = parseStmtList(TokenType::RBRACE);
        expect(TokenType::RBRACE, "}");
        branches.push_back({std::move(ec), std::move(eb)});
    }
    // else?
    if (check(TokenType::ELSE)) {
        advance();
        expect(TokenType::LBRACE, "{");
        auto eb = parseStmtList(TokenType::RBRACE);
        expect(TokenType::RBRACE, "}");
        branches.push_back({nullptr, std::move(eb)});
    }
    return std::make_unique<IfStmt>(std::move(branches));
}

// =================== for ===================
StmtPtr Parser::parseFor() {
    advance(); // for
    expect(TokenType::LPAREN, "(");

    // 解析 init: let i = 1 (没有分号)
    StmtPtr init;
    if (check(TokenType::LET)) {
        advance(); // let
        std::string typeName;
        if (check(TokenType::LT)) typeName = parseTypeName();
        std::string name = expect(TokenType::IDENTIFIER, "var").value;
        expect(TokenType::ASSIGN, "=");
        ExprPtr iv = parseExpr();
        init = std::make_unique<VarDeclStmt>(typeName, false, name, std::move(iv));
    } else {
        ExprPtr e = parseExpr();
        init = std::make_unique<ExprStmt>(std::move(e));
    }
    expect(TokenType::COMMA, ",");
    ExprPtr cond = parseExpr();
    expect(TokenType::COMMA, ",");
    ExprPtr step = parseExpr();
    expect(TokenType::RPAREN, ")");
    expect(TokenType::LBRACE, "{");
    auto body = parseStmtList(TokenType::RBRACE);
    expect(TokenType::RBRACE, "}");
    return std::make_unique<ForStmt>(std::move(init), std::move(cond),
                                     std::move(step), std::move(body));
}

// =================== while ===================
StmtPtr Parser::parseWhile() {
    advance(); // while
    expect(TokenType::LPAREN, "(");
    ExprPtr cond = parseExpr();
    expect(TokenType::RPAREN, ")");
    expect(TokenType::LBRACE, "{");
    auto body = parseStmtList(TokenType::RBRACE);
    expect(TokenType::RBRACE, "}");
    return std::make_unique<WhileStmt>(std::move(cond), std::move(body));
}

// =================== `switch ===================
StmtPtr Parser::parseLabelSwitch() {
    advance(); // `switch
    ExprPtr subject = parseExpr();
    std::vector<SwitchCase> cases;
    while (!check(TokenType::LABEL_SWITCH_END) && !check(TokenType::EOF_TOKEN)) {
        if (check(TokenType::IF)) {
            advance();
            expect(TokenType::LPAREN, "(");
            ExprPtr val = parseExpr();
            expect(TokenType::RPAREN, ")");
            expect(TokenType::COLON, ":");
            std::vector<StmtPtr> body;
            while (!check(TokenType::IF) && !check(TokenType::ELSE) &&
                   !check(TokenType::LABEL_SWITCH_END) && !check(TokenType::EOF_TOKEN)) {
                body.push_back(parseStmt());
            }
            cases.push_back({std::move(val), std::move(body)});
        } else if (check(TokenType::ELSE)) {
            advance();
            expect(TokenType::COLON, ":");
            std::vector<StmtPtr> body;
            while (!check(TokenType::LABEL_SWITCH_END) && !check(TokenType::EOF_TOKEN)) {
                body.push_back(parseStmt());
            }
            cases.push_back({nullptr, std::move(body)});
        } else {
            advance(); // 跳过无法识别的token
        }
    }
    expect(TokenType::LABEL_SWITCH_END, "`switch/");
    return std::make_unique<SwitchStmt>(std::move(subject), std::move(cases));
}

// =================== `loop ===================
StmtPtr Parser::parseLabelLoop() {
    advance(); // `loop
    ExprPtr count = parseExpr();
    auto body = parseStmtList(TokenType::LABEL_LOOP_END);
    expect(TokenType::LABEL_LOOP_END, "`loop/");
    return std::make_unique<LoopStmt>(std::move(count), std::move(body));
}

// =================== `def ===================
StmtPtr Parser::parseLabelDef() {
    advance(); // `def
    std::string name = expect(TokenType::IDENTIFIER, "function name").value;
    int headerLine = peek().line;      // 函数名所在行
    std::vector<std::string> params;

    if (check(TokenType::LPAREN)) {
        // 新格式：`def name(x:type, y:type) -> rettype
        advance(); // (
        while (!check(TokenType::RPAREN) && !check(TokenType::EOF_TOKEN)) {
            if (check(TokenType::IDENTIFIER)) {
                params.push_back(advance().value);
                // 跳过 :type
                if (match(TokenType::COLON)) {
                    // 类型可能是 int / float / string / bool / char / IDENTIFIER
                    while (!check(TokenType::COMMA) && !check(TokenType::RPAREN)
                           && !check(TokenType::EOF_TOKEN)) {
                        advance();
                    }
                }
            }
            if (!match(TokenType::COMMA)) break;
        }
        expect(TokenType::RPAREN, ")");
        // 跳过 -> rettype（一个类型 token）
        if (match(TokenType::ARROW_RIGHT)) {
            if (!check(TokenType::LABEL_DEF_END) && !check(TokenType::EOF_TOKEN)) {
                advance(); // 跳过返回类型名
            }
        }
    } else if (match(TokenType::COMMA)) {
        // 旧格式：`def name, param1, param2
        while (check(TokenType::IDENTIFIER) && peek().line == headerLine) {
            params.push_back(advance().value);
            if (!check(TokenType::COMMA) || peek().line != headerLine) break;
            advance(); // COMMA
        }
    }

    auto body = parseStmtList(TokenType::LABEL_DEF_END);
    expect(TokenType::LABEL_DEF_END, "`def/");
    return std::make_unique<DefStmt>(name, std::move(params), std::move(body));
}

// =================== `file ===================
StmtPtr Parser::parseLabelFile() {
    advance(); // `file
    std::vector<FileOp> ops;
    while (!check(TokenType::LABEL_FILE_END) && !check(TokenType::EOF_TOKEN)) {
        // read/write/a
        if (!check(TokenType::IDENTIFIER)) { advance(); continue; }
        std::string op = advance().value; // read/write/a
        expect(TokenType::COLON, ":");
        std::vector<ExprPtr> args;
        args.push_back(parseExpr());
        while (match(TokenType::COMMA)) {
            args.push_back(parseExpr());
        }
        expect(TokenType::SEMICOLON, ";");
        ops.push_back({op, std::move(args)});
    }
    expect(TokenType::LABEL_FILE_END, "`file/");
    return std::make_unique<FileStmt>(std::move(ops));
}

// =================== `template ===================
StmtPtr Parser::parseLabelTemplate() {
    advance(); // `template
    std::string name = expect(TokenType::IDENTIFIER, "template name").value;
    std::vector<TemplateField> fields;
    while (!check(TokenType::LABEL_TEMPLATE_END) && !check(TokenType::EOF_TOKEN)) {
        if (check(TokenType::LET)) {
            advance();
            std::string typeName;
            if (check(TokenType::LT)) typeName = parseTypeName();
            std::string fname = expect(TokenType::IDENTIFIER, "field name").value;
            expect(TokenType::SEMICOLON, ";");
            fields.push_back({typeName, fname});
        } else {
            advance();
        }
    }
    expect(TokenType::LABEL_TEMPLATE_END, "`template/");
    return std::make_unique<TemplateStmt>(name, std::move(fields));
}

// =================== `namespace ===================
StmtPtr Parser::parseLabelNamespace() {
    advance(); // `namespace
    std::string name = expect(TokenType::IDENTIFIER, "namespace name").value;
    auto body = parseStmtList(TokenType::LABEL_NAMESPACE_END);
    expect(TokenType::LABEL_NAMESPACE_END, "`namespace/");
    return std::make_unique<NamespaceStmt>(name, std::move(body));
}

// =================== `class ===================
StmtPtr Parser::parseLabelClass() {
    advance(); // `class
    std::string name = expect(TokenType::IDENTIFIER, "class name").value;
    std::string parent;
    if (check(TokenType::EXTENDS)) {
        advance();
        parent = expect(TokenType::IDENTIFIER, "parent class name").value;
    }
    std::vector<ClassField> fields;
    std::vector<ClassMethod> methods;

    while (!check(TokenType::LABEL_CLASS_END) && !check(TokenType::EOF_TOKEN)) {
        if (check(TokenType::LET)) {
            advance();
            std::string typeName;
            if (check(TokenType::LT)) typeName = parseTypeName();
            std::string fname = expect(TokenType::IDENTIFIER, "field name").value;
            ExprPtr init;
            if (match(TokenType::ASSIGN)) init = parseExpr();
            expect(TokenType::SEMICOLON, ";");
            fields.push_back({typeName, fname, std::move(init)});
        } else if (check(TokenType::LABEL_CONSTRUCTOR)) {
            int ctorHeaderLine = peek().line;
            advance();
            expect(TokenType::COMMA, ",");
            std::vector<std::string> params;
            // 只消耗与 `constructor 同行的 IDENTIFIER 作为参数
            while (check(TokenType::IDENTIFIER) && peek().line == ctorHeaderLine) {
                params.push_back(advance().value);
                if (!check(TokenType::COMMA) || peek().line != ctorHeaderLine) break;
                advance(); // COMMA
            }
            auto body = parseStmtList(TokenType::LABEL_CONSTRUCTOR_END);
            expect(TokenType::LABEL_CONSTRUCTOR_END, "`constructor/");
            methods.push_back({name, params, std::move(body), true});
        } else if (check(TokenType::LABEL_METHOD)) {
            int methodHeaderLine = peek().line;
            advance();
            std::string mname = expect(TokenType::IDENTIFIER, "method name").value;
            expect(TokenType::COMMA, ",");
            std::vector<std::string> params;
            // 只消耗与 `method 同行的 IDENTIFIER 作为参数
            while (check(TokenType::IDENTIFIER) && peek().line == methodHeaderLine) {
                params.push_back(advance().value);
                if (!check(TokenType::COMMA) || peek().line != methodHeaderLine) break;
                advance(); // COMMA
            }
            auto body = parseStmtList(TokenType::LABEL_METHOD_END);
            expect(TokenType::LABEL_METHOD_END, "`method/");
            methods.push_back({mname, params, std::move(body), false});
        } else {
            advance();
        }
    }
    expect(TokenType::LABEL_CLASS_END, "`class/");
    return std::make_unique<ClassStmt>(name, parent, std::move(fields), std::move(methods));
}

// =================== `start ... `/ ===================
StmtPtr Parser::parseLabelStart() {
    advance(); // `start
    auto body = parseStmtList(TokenType::LABEL_END);
    expect(TokenType::LABEL_END, "`/");
    return std::make_unique<StartBlockStmt>(std::move(body));
}

// =================== output ===================
StmtPtr Parser::parseOutput() {
    advance(); // output
    expect(TokenType::COLON, ":");
    std::vector<ExprPtr> args;
    args.push_back(parseExpr());
    while (match(TokenType::COMMA)) {
        args.push_back(parseExpr());
    }
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<OutputStmt>(std::move(args));
}

// =================== input ===================
StmtPtr Parser::parseInput() {
    advance(); // input
    expect(TokenType::COLON, ":");
    ExprPtr prompt, target;
    // input:"提示词",变量; 或 input:,变量; 或 input:"提示词",; 或 input:,;
    if (!check(TokenType::COMMA)) {
        prompt = parseExpr();
    }
    expect(TokenType::COMMA, ",");
    if (!check(TokenType::SEMICOLON)) {
        target = parseExpr();
    }
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<InputStmt>(std::move(prompt), std::move(target));
}

// =================== return ===================
StmtPtr Parser::parseReturn() {
    advance(); // return
    expect(TokenType::COLON, ":");
    ExprPtr val;
    if (!check(TokenType::SEMICOLON)) {
        val = parseExpr();
    }
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<ReturnStmt>(std::move(val));
}

// =================== break ===================
StmtPtr Parser::parseBreak() {
    advance(); // break
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<BreakStmt>();
}

// =================== continue ===================
StmtPtr Parser::parseContinue() {
    advance(); // continue
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<ContinueStmt>();
}

// =================== IOPlus ===================
StmtPtr Parser::parseIOPlusInput(ExprPtr iplus) {
    // iplus -> a -> b -> c;
    std::vector<ExprPtr> targets;
    while (match(TokenType::ARROW_RIGHT)) {
        targets.push_back(parseExpr());
    }
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<IOPlusInputStmt>(std::move(targets));
}

StmtPtr Parser::parseIOPlusOutput(ExprPtr oplus) {
    // oplus <- a <- b;
    std::vector<ExprPtr> values;
    while (match(TokenType::ARROW_LEFT)) {
        values.push_back(parseExpr());
    }
    expect(TokenType::SEMICOLON, ";");
    return std::make_unique<IOPlusOutputStmt>(std::move(values));
}

// =================== 表达式 (递归下降) ===================

ExprPtr Parser::parseExpr() {
    return parseAssign();
}

ExprPtr Parser::parseAssign() {
    ExprPtr left = parseOr();
    if (check(TokenType::ASSIGN)) {
        advance();
        ExprPtr right = parseAssign();
        return std::make_unique<AssignExpr>(std::move(left), std::move(right));
    }
    // 复合赋值
    if (check(TokenType::PLUS_ASSIGN) || check(TokenType::MINUS_ASSIGN) ||
        check(TokenType::STAR_ASSIGN) || check(TokenType::SLASH_ASSIGN)) {
        std::string op = advance().value;
        ExprPtr right = parseAssign();
        return std::make_unique<CompoundAssignExpr>(op, std::move(left), std::move(right));
    }
    return left;
}

ExprPtr Parser::parseOr() {
    ExprPtr left = parseAnd();
    while (check(TokenType::OR)) {
        std::string op = advance().value;
        ExprPtr right = parseAnd();
        left = std::make_unique<BinOpExpr>(op, std::move(left), std::move(right));
    }
    return left;
}

ExprPtr Parser::parseAnd() {
    ExprPtr left = parseEquality();
    while (check(TokenType::AND)) {
        std::string op = advance().value;
        ExprPtr right = parseEquality();
        left = std::make_unique<BinOpExpr>(op, std::move(left), std::move(right));
    }
    return left;
}

ExprPtr Parser::parseEquality() {
    ExprPtr left = parseRelational();
    while (check(TokenType::EQ) || check(TokenType::NEQ)) {
        std::string op = advance().value;
        ExprPtr right = parseRelational();
        left = std::make_unique<BinOpExpr>(op, std::move(left), std::move(right));
    }
    return left;
}

ExprPtr Parser::parseRelational() {
    ExprPtr left = parseAddSub();
    while (check(TokenType::LT) || check(TokenType::GT) ||
           check(TokenType::LE) || check(TokenType::GE)) {
        std::string op = advance().value;
        ExprPtr right = parseAddSub();
        left = std::make_unique<BinOpExpr>(op, std::move(left), std::move(right));
    }
    return left;
}

ExprPtr Parser::parseAddSub() {
    ExprPtr left = parseMulDiv();
    while (check(TokenType::PLUS) || check(TokenType::MINUS)) {
        std::string op = advance().value;
        ExprPtr right = parseMulDiv();
        left = std::make_unique<BinOpExpr>(op, std::move(left), std::move(right));
    }
    return left;
}

ExprPtr Parser::parseMulDiv() {
    ExprPtr left = parseUnary();
    while (check(TokenType::STAR) || check(TokenType::SLASH) || check(TokenType::PERCENT)) {
        std::string op = advance().value;
        ExprPtr right = parseUnary();
        left = std::make_unique<BinOpExpr>(op, std::move(left), std::move(right));
    }
    return left;
}

ExprPtr Parser::parseUnary() {
    if (check(TokenType::NOT)) {
        std::string op = advance().value;
        ExprPtr e = parseUnary();
        return std::make_unique<UnaryOpExpr>(op, std::move(e));
    }
    if (check(TokenType::MINUS)) {
        std::string op = advance().value;
        ExprPtr e = parseUnary();
        return std::make_unique<UnaryOpExpr>("-", std::move(e));
    }
    return parsePostfix();
}

ExprPtr Parser::parsePostfix() {
    ExprPtr e = parsePrimary();
    while (true) {
        if (check(TokenType::DOT)) {
            advance();
            std::string member = expect(TokenType::IDENTIFIER, "member name").value;
            e = std::make_unique<MemberAccessExpr>(std::move(e), member);
        } else if (check(TokenType::LBRACKET)) {
            advance();
            ExprPtr idx = parseExpr();
            expect(TokenType::RBRACKET, "]");
            e = std::make_unique<ArrayAccessExpr>(std::move(e), std::move(idx));
        } else if (check(TokenType::LPAREN)) {
            auto args = parseArgList();
            e = std::make_unique<CallExpr>(std::move(e), std::move(args));
        } else if (check(TokenType::LBRACE)) {
            // 聚合/结构体初始化：TypeName{ val1, val2, ... }
            // 例如 Point{10, 20}，生成为 TypeName{val1, val2}
            advance(); // {
            std::vector<ExprPtr> fields;
            if (!check(TokenType::RBRACE)) {
                fields.push_back(parseExpr());
                while (match(TokenType::COMMA)) {
                    if (check(TokenType::RBRACE)) break; // trailing comma
                    fields.push_back(parseExpr());
                }
            }
            expect(TokenType::RBRACE, "}");
            // 包装为 CallExpr（callee 是类型名 ident），代码生成时生成 TypeName{...}
            e = std::make_unique<StructInitExpr>(std::move(e), std::move(fields));
        } else {
            break;
        }
    }
    return e;
}

std::vector<ExprPtr> Parser::parseArgList() {
    expect(TokenType::LPAREN, "(");
    std::vector<ExprPtr> args;
    if (!check(TokenType::RPAREN)) {
        args.push_back(parseExpr());
        while (match(TokenType::COMMA)) {
            args.push_back(parseExpr());
        }
    }
    expect(TokenType::RPAREN, ")");
    return args;
}

ExprPtr Parser::parsePrimary() {
    // 整数
    if (check(TokenType::INTEGER)) {
        long long v = std::stoll(advance().value);
        return std::make_unique<IntLitExpr>(v);
    }
    // 浮点数
    if (check(TokenType::FLOAT)) {
        double v = std::stod(advance().value);
        return std::make_unique<FloatLitExpr>(v);
    }
    // 字符串
    if (check(TokenType::STRING)) {
        std::string v = advance().value;
        return std::make_unique<StrLitExpr>(v);
    }
    // 字符
    if (check(TokenType::CHAR)) {
        std::string v = advance().value;
        char ch = v.empty() ? '\0' : v[0];
        return std::make_unique<CharLitExpr>(ch);
    }
    // 布尔值
    if (check(TokenType::BOOL_TRUE))  { advance(); return std::make_unique<BoolLitExpr>(true); }
    if (check(TokenType::BOOL_FALSE)) { advance(); return std::make_unique<BoolLitExpr>(false); }
    // this
    if (check(TokenType::THIS)) { advance(); return std::make_unique<ThisExpr>(); }
    // super(args)
    if (check(TokenType::SUPER)) {
        advance();
        auto args = parseArgList();
        return std::make_unique<SuperExpr>(std::move(args));
    }
    // 括号
    if (check(TokenType::LPAREN)) {
        advance();
        ExprPtr e = parseExpr();
        expect(TokenType::RPAREN, ")");
        return e;
    }
    // 类型转换函数 int(x), float(x), char(x), string(x)
    if (check(TokenType::INT_KW) || check(TokenType::FLOAT_KW) ||
        check(TokenType::CHAR_KW) || check(TokenType::STRING_KW)) {
        std::string t = advance().value;
        auto args = parseArgList();
        if (args.size() != 1) throw std::runtime_error("Type cast takes 1 argument");
        return std::make_unique<TypeCastExpr>(t, std::move(args[0]));
    }
    // 标识符（变量/函数名）
    if (check(TokenType::IDENTIFIER)) {
        std::string name = advance().value;
        return std::make_unique<IdentExpr>(name);
    }
    throw std::runtime_error(std::string("[Line ") + std::to_string(peek().line) +
                             "] Unexpected token: '" + peek().value + "'");
}
