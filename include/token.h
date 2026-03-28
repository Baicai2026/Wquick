#pragma once
#include <string>

enum class TokenType {
    // 字面量
    INTEGER, FLOAT, STRING, CHAR, BOOL_TRUE, BOOL_FALSE,

    // 标识符和关键字
    IDENTIFIER,
    LET, IF, ELIF, ELSE, FOR, WHILE, RETURN, IMPORT, BREAK, CONTINUE,
    INT_KW, FLOAT_KW, CHAR_KW, STRING_KW, BOOL_KW, CONST_KW,
    THIS, SUPER, EXTENDS,

    // 标签关键字（backtick开头的）
    LABEL_START,      // `start
    LABEL_END,        // `/
    LABEL_DEF,        // `def
    LABEL_DEF_END,    // `def/
    LABEL_LOOP,       // `loop
    LABEL_LOOP_END,   // `loop/
    LABEL_SWITCH,     // `switch
    LABEL_SWITCH_END, // `switch/
    LABEL_FILE,       // `file
    LABEL_FILE_END,   // `file/
    LABEL_TEMPLATE,   // `template
    LABEL_TEMPLATE_END,//'`template/
    LABEL_NAMESPACE,  // `namespace
    LABEL_NAMESPACE_END, // `namespace/
    LABEL_CLASS,      // `class
    LABEL_CLASS_END,  // `class/
    LABEL_CONSTRUCTOR,    // `constructor
    LABEL_CONSTRUCTOR_END,// `constructor/
    LABEL_METHOD,         // `method
    LABEL_METHOD_END,     // `method/

    // 运算符
    PLUS, MINUS, STAR, SLASH, PERCENT,
    ASSIGN,          // =
    EQ,              // ==
    NEQ,             // !=
    LT,              // <
    GT,              // >
    LE,              // <=
    GE,              // >=
    AND,             // &&
    OR,              // ||
    NOT,             // !
    PLUS_ASSIGN,     // +=
    MINUS_ASSIGN,    // -=
    STAR_ASSIGN,     // *=
    SLASH_ASSIGN,    // /=
    ARROW_RIGHT,     // ->
    ARROW_LEFT,      // <-
    DOT,             // .

    // 分隔符
    SEMICOLON,       // ;
    COLON,           // :
    COMMA,           // ,
    LPAREN,          // (
    RPAREN,          // )
    LBRACE,          // {
    RBRACE,          // }
    LBRACKET,        // [
    RBRACKET,        // ]
    LANGLE_TYPE,     // < (类型括号左)
    RANGLE_TYPE,     // > (类型括号右)

    // 特殊
    EOF_TOKEN,
    UNKNOWN
};

struct Token {
    TokenType type;
    std::string value;
    int line;
    int col;

    Token(TokenType t, std::string v, int l, int c)
        : type(t), value(std::move(v)), line(l), col(c) {}
};
