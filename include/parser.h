#pragma once
#include "token.h"
#include "ast.h"
#include <vector>
#include <memory>

class Parser {
public:
    explicit Parser(std::vector<Token> tokens);
    std::unique_ptr<ProgramNode> parse();

private:
    std::vector<Token> tokens;
    size_t pos;

    Token& peek(int offset = 0);
    Token& advance();
    bool check(TokenType t) const;
    bool match(TokenType t);
    Token expect(TokenType t, const std::string& msg);

    // 程序结构
    std::vector<StmtPtr> parseStmtList(TokenType stopLabel1,
                                        TokenType stopLabel2 = TokenType::EOF_TOKEN);

    // 语句解析
    StmtPtr parseStmt();
    StmtPtr parseImport();
    StmtPtr parseVarDecl();
    StmtPtr parseIf();
    StmtPtr parseFor();
    StmtPtr parseWhile();
    StmtPtr parseLabelSwitch();
    StmtPtr parseLabelLoop();
    StmtPtr parseLabelDef();
    StmtPtr parseLabelFile();
    StmtPtr parseLabelTemplate();
    StmtPtr parseLabelNamespace();
    StmtPtr parseLabelClass();
    StmtPtr parseLabelStart();
    StmtPtr parseOutput();
    StmtPtr parseInput();
    StmtPtr parseReturn();
    StmtPtr parseBreak();
    StmtPtr parseContinue();

    // IOPlus
    StmtPtr parseIOPlusInput(ExprPtr iplus);
    StmtPtr parseIOPlusOutput(ExprPtr oplus);

    // 表达式
    ExprPtr parseExpr();
    ExprPtr parseAssign();
    ExprPtr parseOr();
    ExprPtr parseAnd();
    ExprPtr parseEquality();
    ExprPtr parseRelational();
    ExprPtr parseAddSub();
    ExprPtr parseMulDiv();
    ExprPtr parseUnary();
    ExprPtr parsePostfix();
    ExprPtr parsePrimary();

    // 工具
    std::string parseTypeName();   // 解析 <int> 这种类型
    std::vector<ExprPtr> parseArgList(); // 解析 (a, b, c)
};
