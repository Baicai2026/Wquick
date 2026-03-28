#include "lexer.h"
#include <stdexcept>
#include <unordered_map>

static std::unordered_map<std::string, TokenType> keywords = {
    {"let",    TokenType::LET},
    {"if",     TokenType::IF},
    {"elif",   TokenType::ELIF},
    {"else",   TokenType::ELSE},
    {"for",    TokenType::FOR},
    {"while",  TokenType::WHILE},
    {"return",   TokenType::RETURN},
    {"import",   TokenType::IMPORT},
    {"break",    TokenType::BREAK},
    {"continue", TokenType::CONTINUE},
    {"int",    TokenType::INT_KW},
    {"float",  TokenType::FLOAT_KW},
    {"char",   TokenType::CHAR_KW},
    {"string", TokenType::STRING_KW},
    {"bool",   TokenType::BOOL_KW},
    {"const",  TokenType::CONST_KW},
    {"this",   TokenType::THIS},
    {"super",  TokenType::SUPER},
    {"extends",TokenType::EXTENDS},
    {"true",   TokenType::BOOL_TRUE},
    {"false",  TokenType::BOOL_FALSE},
};

// backtick 标签映射
static std::unordered_map<std::string, TokenType> labels = {
    {"start",         TokenType::LABEL_START},
    {"/",             TokenType::LABEL_END},
    {"def",           TokenType::LABEL_DEF},
    {"def/",          TokenType::LABEL_DEF_END},
    {"loop",          TokenType::LABEL_LOOP},
    {"loop/",         TokenType::LABEL_LOOP_END},
    {"switch",        TokenType::LABEL_SWITCH},
    {"switch/",       TokenType::LABEL_SWITCH_END},
    {"file",          TokenType::LABEL_FILE},
    {"file/",         TokenType::LABEL_FILE_END},
    {"template",      TokenType::LABEL_TEMPLATE},
    {"template/",     TokenType::LABEL_TEMPLATE_END},
    {"namespace",     TokenType::LABEL_NAMESPACE},
    {"namespace/",    TokenType::LABEL_NAMESPACE_END},
    {"class",         TokenType::LABEL_CLASS},
    {"class/",        TokenType::LABEL_CLASS_END},
    {"constructor",   TokenType::LABEL_CONSTRUCTOR},
    {"constructor/",  TokenType::LABEL_CONSTRUCTOR_END},
    {"method",        TokenType::LABEL_METHOD},
    {"method/",       TokenType::LABEL_METHOD_END},
};

Lexer::Lexer(std::string source)
    : src(std::move(source)), pos(0), line(1), col(1) {}

char Lexer::peek(int offset) const {
    size_t p = pos + offset;
    if (p >= src.size()) return '\0';
    return src[p];
}

char Lexer::advance() {
    char c = src[pos++];
    if (c == '\n') { line++; col = 1; }
    else col++;
    return c;
}

void Lexer::skipWhitespaceAndComments() {
    while (pos < src.size()) {
        // 跳过空白
        if (std::isspace(peek())) {
            advance();
            continue;
        }
        // 单行注释 //
        if (peek() == '/' && peek(1) == '/') {
            while (pos < src.size() && peek() != '\n') advance();
            continue;
        }
        // 块注释 /* */
        if (peek() == '/' && peek(1) == '*') {
            advance(); advance();
            while (pos < src.size()) {
                if (peek() == '*' && peek(1) == '/') {
                    advance(); advance();
                    break;
                }
                advance();
            }
            continue;
        }
        break;
    }
}

Token Lexer::readString() {
    int sl = line, sc = col;
    advance(); // 跳过开头 "
    std::string val;
    while (pos < src.size() && peek() != '"') {
        if (peek() == '\\') {
            advance();
            char esc = advance();
            switch (esc) {
                case 'n': val += '\n'; break;
                case 't': val += '\t'; break;
                case '"': val += '"'; break;
                case '\\': val += '\\'; break;
                default: val += '\\'; val += esc;
            }
        } else {
            val += advance();
        }
    }
    if (pos < src.size()) advance(); // 跳过结尾 "
    return Token(TokenType::STRING, val, sl, sc);
}

Token Lexer::readChar() {
    int sl = line, sc = col;
    advance(); // 跳过 '
    std::string val;
    if (peek() == '\\') {
        advance();
        char esc = advance();
        switch (esc) {
            case 'n': val = "\n"; break;
            case 't': val = "\t"; break;
            case '\'': val = "'"; break;
            case '\\': val = "\\"; break;
            default: val += '\\'; val += esc;
        }
    } else {
        val += advance();
    }
    if (pos < src.size() && peek() == '\'') advance();
    return Token(TokenType::CHAR, val, sl, sc);
}

Token Lexer::readNumber() {
    int sl = line, sc = col;
    std::string val;
    bool isFloat = false;
    while (pos < src.size() && (std::isdigit(peek()) || peek() == '.')) {
        if (peek() == '.') {
            if (isFloat) break;
            isFloat = true;
        }
        val += advance();
    }
    return Token(isFloat ? TokenType::FLOAT : TokenType::INTEGER, val, sl, sc);
}

Token Lexer::readIdentOrKeyword() {
    int sl = line, sc = col;
    std::string val;
    while (pos < src.size() && (std::isalnum(peek()) || peek() == '_')) {
        val += advance();
    }
    auto it = keywords.find(val);
    if (it != keywords.end()) return Token(it->second, val, sl, sc);
    return Token(TokenType::IDENTIFIER, val, sl, sc);
}

Token Lexer::readLabel() {
    int sl = line, sc = col;
    advance(); // 跳过 `
    // 读取标签名（可以包含字母、数字、/）
    std::string labelName;
    while (pos < src.size() && (std::isalnum(peek()) || peek() == '/' || peek() == '_')) {
        labelName += advance();
    }
    auto it = labels.find(labelName);
    if (it != labels.end()) return Token(it->second, "`" + labelName, sl, sc);
    // 未知标签，作为普通标识符处理
    return Token(TokenType::IDENTIFIER, labelName, sl, sc);
}

Token Lexer::readOperatorOrPunct() {
    int sl = line, sc = col;
    char c = peek();
    // 两字符运算符
    char c2 = peek(1);
    if (c == '-' && c2 == '>') { advance(); advance(); return Token(TokenType::ARROW_RIGHT, "->", sl, sc); }
    if (c == '<' && c2 == '-') { advance(); advance(); return Token(TokenType::ARROW_LEFT, "<-", sl, sc); }
    if (c == '=' && c2 == '=') { advance(); advance(); return Token(TokenType::EQ, "==", sl, sc); }
    if (c == '!' && c2 == '=') { advance(); advance(); return Token(TokenType::NEQ, "!=", sl, sc); }
    if (c == '<' && c2 == '=') { advance(); advance(); return Token(TokenType::LE, "<=", sl, sc); }
    if (c == '>' && c2 == '=') { advance(); advance(); return Token(TokenType::GE, ">=", sl, sc); }
    if (c == '&' && c2 == '&') { advance(); advance(); return Token(TokenType::AND, "&&", sl, sc); }
    if (c == '|' && c2 == '|') { advance(); advance(); return Token(TokenType::OR, "||", sl, sc); }
    if (c == '+' && c2 == '=') { advance(); advance(); return Token(TokenType::PLUS_ASSIGN, "+=", sl, sc); }
    if (c == '-' && c2 == '=') { advance(); advance(); return Token(TokenType::MINUS_ASSIGN, "-=", sl, sc); }
    if (c == '*' && c2 == '=') { advance(); advance(); return Token(TokenType::STAR_ASSIGN, "*=", sl, sc); }
    if (c == '/' && c2 == '=') { advance(); advance(); return Token(TokenType::SLASH_ASSIGN, "/=", sl, sc); }

    advance();
    switch (c) {
        case '+': return Token(TokenType::PLUS, "+", sl, sc);
        case '-': return Token(TokenType::MINUS, "-", sl, sc);
        case '*': return Token(TokenType::STAR, "*", sl, sc);
        case '/': return Token(TokenType::SLASH, "/", sl, sc);
        case '%': return Token(TokenType::PERCENT, "%", sl, sc);
        case '=': return Token(TokenType::ASSIGN, "=", sl, sc);
        case '<': return Token(TokenType::LT, "<", sl, sc);
        case '>': return Token(TokenType::GT, ">", sl, sc);
        case '!': return Token(TokenType::NOT, "!", sl, sc);
        case '.': return Token(TokenType::DOT, ".", sl, sc);
        case ';': return Token(TokenType::SEMICOLON, ";", sl, sc);
        case ':': return Token(TokenType::COLON, ":", sl, sc);
        case ',': return Token(TokenType::COMMA, ",", sl, sc);
        case '(': return Token(TokenType::LPAREN, "(", sl, sc);
        case ')': return Token(TokenType::RPAREN, ")", sl, sc);
        case '{': return Token(TokenType::LBRACE, "{", sl, sc);
        case '}': return Token(TokenType::RBRACE, "}", sl, sc);
        case '[': return Token(TokenType::LBRACKET, "[", sl, sc);
        case ']': return Token(TokenType::RBRACKET, "]", sl, sc);
        default:  return Token(TokenType::UNKNOWN, std::string(1, c), sl, sc);
    }
}

std::vector<Token> Lexer::tokenize() {
    std::vector<Token> tokens;
    while (true) {
        skipWhitespaceAndComments();
        if (pos >= src.size()) {
            tokens.emplace_back(TokenType::EOF_TOKEN, "", line, col);
            break;
        }
        char c = peek();
        if (c == '"')  { tokens.push_back(readString()); }
        else if (c == '\'') { tokens.push_back(readChar()); }
        else if (std::isdigit(c)) { tokens.push_back(readNumber()); }
        else if (std::isalpha(c) || c == '_') { tokens.push_back(readIdentOrKeyword()); }
        else if (c == '`') { tokens.push_back(readLabel()); }
        else { tokens.push_back(readOperatorOrPunct()); }
    }
    return tokens;
}
