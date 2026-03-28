#pragma once
#include <string>
#include <vector>
#include <memory>
#include <optional>

// ================= 前向声明 =================
struct Expr;
struct Stmt;
using ExprPtr = std::unique_ptr<Expr>;
using StmtPtr = std::unique_ptr<Stmt>;

// ================= 表达式节点 =================

struct Expr {
    virtual ~Expr() = default;
    enum class Kind {
        IntLit, FloatLit, StrLit, CharLit, BoolLit,
        Ident,
        BinOp, UnaryOp,
        Assign, CompoundAssign,
        Call,           // func(args)
        ArrayAccess,    // arr[idx]
        MemberAccess,   // obj.field
        ArrayLit,       // [a, b, c]
        TypeCast,       // int(expr), float(expr), char(expr)
        This, Super,
        StructInit,     // TypeName{field1, field2, ...}
    } kind;
    explicit Expr(Kind k) : kind(k) {}
};

// 整数字面量
struct IntLitExpr : Expr {
    long long value;
    IntLitExpr(long long v) : Expr(Kind::IntLit), value(v) {}
};
// 浮点字面量
struct FloatLitExpr : Expr {
    double value;
    FloatLitExpr(double v) : Expr(Kind::FloatLit), value(v) {}
};
// 字符串字面量
struct StrLitExpr : Expr {
    std::string value;
    StrLitExpr(std::string v) : Expr(Kind::StrLit), value(std::move(v)) {}
};
// 字符字面量
struct CharLitExpr : Expr {
    char value;
    CharLitExpr(char v) : Expr(Kind::CharLit), value(v) {}
};
// 布尔字面量
struct BoolLitExpr : Expr {
    bool value;
    BoolLitExpr(bool v) : Expr(Kind::BoolLit), value(v) {}
};
// 标识符
struct IdentExpr : Expr {
    std::string name;
    IdentExpr(std::string n) : Expr(Kind::Ident), name(std::move(n)) {}
};
// 二元运算
struct BinOpExpr : Expr {
    std::string op;
    ExprPtr left, right;
    BinOpExpr(std::string o, ExprPtr l, ExprPtr r)
        : Expr(Kind::BinOp), op(std::move(o)),
          left(std::move(l)), right(std::move(r)) {}
};
// 一元运算
struct UnaryOpExpr : Expr {
    std::string op;
    ExprPtr operand;
    UnaryOpExpr(std::string o, ExprPtr e)
        : Expr(Kind::UnaryOp), op(std::move(o)), operand(std::move(e)) {}
};
// 赋值
struct AssignExpr : Expr {
    ExprPtr target;
    ExprPtr value;
    AssignExpr(ExprPtr t, ExprPtr v)
        : Expr(Kind::Assign), target(std::move(t)), value(std::move(v)) {}
};
// 复合赋值 (+=, -=, *=, /=)
struct CompoundAssignExpr : Expr {
    std::string op;
    ExprPtr target;
    ExprPtr value;
    CompoundAssignExpr(std::string o, ExprPtr t, ExprPtr v)
        : Expr(Kind::CompoundAssign), op(std::move(o)),
          target(std::move(t)), value(std::move(v)) {}
};
// 函数/方法调用
struct CallExpr : Expr {
    ExprPtr callee;
    std::vector<ExprPtr> args;
    CallExpr(ExprPtr c, std::vector<ExprPtr> a)
        : Expr(Kind::Call), callee(std::move(c)), args(std::move(a)) {}
};
// 数组访问
struct ArrayAccessExpr : Expr {
    ExprPtr array;
    ExprPtr index;
    ArrayAccessExpr(ExprPtr a, ExprPtr i)
        : Expr(Kind::ArrayAccess), array(std::move(a)), index(std::move(i)) {}
};
// 成员访问
struct MemberAccessExpr : Expr {
    ExprPtr object;
    std::string member;
    MemberAccessExpr(ExprPtr o, std::string m)
        : Expr(Kind::MemberAccess), object(std::move(o)), member(std::move(m)) {}
};
// 数组字面量
struct ArrayLitExpr : Expr {
    std::vector<ExprPtr> elements;
    ArrayLitExpr(std::vector<ExprPtr> e)
        : Expr(Kind::ArrayLit), elements(std::move(e)) {}
};
// 类型转换
struct TypeCastExpr : Expr {
    std::string targetType; // "int","float","char","string"
    ExprPtr operand;
    TypeCastExpr(std::string t, ExprPtr e)
        : Expr(Kind::TypeCast), targetType(std::move(t)), operand(std::move(e)) {}
};
// this
struct ThisExpr : Expr {
    ThisExpr() : Expr(Kind::This) {}
};
// super
struct SuperExpr : Expr {
    std::vector<ExprPtr> args; // super(args) 调用父类构造
    SuperExpr(std::vector<ExprPtr> a) : Expr(Kind::Super), args(std::move(a)) {}
};
// 聚合/结构体初始化：TypeName{field1, field2, ...}
struct StructInitExpr : Expr {
    ExprPtr typeName;              // 通常是 IdentExpr，表示类型名
    std::vector<ExprPtr> fields;
    StructInitExpr(ExprPtr t, std::vector<ExprPtr> f)
        : Expr(Kind::StructInit), typeName(std::move(t)), fields(std::move(f)) {}
};

// ================= 语句节点 =================

struct Stmt {
    virtual ~Stmt() = default;
    enum class Kind {
        Block, ExprStmt, VarDecl, ArrayDecl,
        If, Switch, For, While, Loop,
        Def, Return, Break, Continue,
        Output, Input,
        ImportStmt,
        File,
        Template, Collection,
        Namespace,
        Class,
        IOPlusInput, IOPlusOutput,
        StartBlock,
        Program,
    } kind;
    explicit Stmt(Kind k) : kind(k) {}
};

// 块语句
struct BlockStmt : Stmt {
    std::vector<StmtPtr> stmts;
    BlockStmt(std::vector<StmtPtr> s) : Stmt(Kind::Block), stmts(std::move(s)) {}
};
// 表达式语句
struct ExprStmt : Stmt {
    ExprPtr expr;
    ExprStmt(ExprPtr e) : Stmt(Kind::ExprStmt), expr(std::move(e)) {}
};

// 变量声明
struct VarDeclStmt : Stmt {
    std::string typeName;   // 类型名，可为空（自动推断）
    bool isConst;
    std::string name;
    ExprPtr init;           // 可为空
    VarDeclStmt(std::string tn, bool c, std::string n, ExprPtr i)
        : Stmt(Kind::VarDecl), typeName(std::move(tn)), isConst(c),
          name(std::move(n)), init(std::move(i)) {}
};

// 数组声明
struct ArrayDeclStmt : Stmt {
    std::string elemType;
    std::string name;
    ExprPtr sizeExpr;             // 固定长度，可为空
    std::vector<ExprPtr> initElements; // 初始化列表，可为空
    ArrayDeclStmt(std::string et, std::string n, ExprPtr sz, std::vector<ExprPtr> elems)
        : Stmt(Kind::ArrayDecl), elemType(std::move(et)), name(std::move(n)),
          sizeExpr(std::move(sz)), initElements(std::move(elems)) {}
};

// if/elif/else
struct IfBranch {
    ExprPtr cond;           // nullptr表示else分支
    std::vector<StmtPtr> body;
};
struct IfStmt : Stmt {
    std::vector<IfBranch> branches; // if, elif..., else
    IfStmt(std::vector<IfBranch> b) : Stmt(Kind::If), branches(std::move(b)) {}
};

// switch
struct SwitchCase {
    ExprPtr value;          // nullptr表示else
    std::vector<StmtPtr> body;
};
struct SwitchStmt : Stmt {
    ExprPtr subject;
    std::vector<SwitchCase> cases;
    SwitchStmt(ExprPtr s, std::vector<SwitchCase> c)
        : Stmt(Kind::Switch), subject(std::move(s)), cases(std::move(c)) {}
};

// for
struct ForStmt : Stmt {
    StmtPtr init;      // let i = 1
    ExprPtr cond;
    ExprPtr step;
    std::vector<StmtPtr> body;
    ForStmt(StmtPtr i, ExprPtr c, ExprPtr s, std::vector<StmtPtr> b)
        : Stmt(Kind::For), init(std::move(i)), cond(std::move(c)),
          step(std::move(s)), body(std::move(b)) {}
};

// while
struct WhileStmt : Stmt {
    ExprPtr cond;
    std::vector<StmtPtr> body;
    WhileStmt(ExprPtr c, std::vector<StmtPtr> b)
        : Stmt(Kind::While), cond(std::move(c)), body(std::move(b)) {}
};

// loop (标签循环)
struct LoopStmt : Stmt {
    ExprPtr count;   // 循环次数
    std::vector<StmtPtr> body;
    LoopStmt(ExprPtr c, std::vector<StmtPtr> b)
        : Stmt(Kind::Loop), count(std::move(c)), body(std::move(b)) {}
};

// 函数定义
struct DefStmt : Stmt {
    std::string name;
    std::vector<std::string> params;
    std::vector<StmtPtr> body;
    DefStmt(std::string n, std::vector<std::string> p, std::vector<StmtPtr> b)
        : Stmt(Kind::Def), name(std::move(n)), params(std::move(p)), body(std::move(b)) {}
};

// return
struct ReturnStmt : Stmt {
    ExprPtr value;   // 可为空
    ReturnStmt(ExprPtr v) : Stmt(Kind::Return), value(std::move(v)) {}
};

// break
struct BreakStmt : Stmt {
    BreakStmt() : Stmt(Kind::Break) {}
};

// continue
struct ContinueStmt : Stmt {
    ContinueStmt() : Stmt(Kind::Continue) {}
};

// output
struct OutputStmt : Stmt {
    std::vector<ExprPtr> args;
    OutputStmt(std::vector<ExprPtr> a) : Stmt(Kind::Output), args(std::move(a)) {}
};

// input
struct InputStmt : Stmt {
    ExprPtr prompt;    // 可为空
    ExprPtr target;    // 可为空
    InputStmt(ExprPtr p, ExprPtr t)
        : Stmt(Kind::Input), prompt(std::move(p)), target(std::move(t)) {}
};

// import
struct ImportStmt : Stmt {
    std::string module;
    ImportStmt(std::string m) : Stmt(Kind::ImportStmt), module(std::move(m)) {}
};

// file操作
struct FileOp {
    std::string op;    // "read","write","a"
    std::vector<ExprPtr> args;
};
struct FileStmt : Stmt {
    std::vector<FileOp> ops;
    FileStmt(std::vector<FileOp> o) : Stmt(Kind::File), ops(std::move(o)) {}
};

// template
struct TemplateField {
    std::string typeName;
    std::string name;
};
struct TemplateStmt : Stmt {
    std::string name;
    std::vector<TemplateField> fields;
    TemplateStmt(std::string n, std::vector<TemplateField> f)
        : Stmt(Kind::Template), name(std::move(n)), fields(std::move(f)) {}
};

// namespace
struct NamespaceStmt : Stmt {
    std::string name;
    std::vector<StmtPtr> body;
    NamespaceStmt(std::string n, std::vector<StmtPtr> b)
        : Stmt(Kind::Namespace), name(std::move(n)), body(std::move(b)) {}
};

// class
struct ClassMethod {
    std::string name;
    std::vector<std::string> params;
    std::vector<StmtPtr> body;
    bool isConstructor;
};
struct ClassField {
    std::string typeName;
    std::string name;
    ExprPtr init;
};
struct ClassStmt : Stmt {
    std::string name;
    std::string parentClass; // 继承，可为空
    std::vector<ClassField> fields;
    std::vector<ClassMethod> methods;
    ClassStmt(std::string n, std::string p,
              std::vector<ClassField> f, std::vector<ClassMethod> m)
        : Stmt(Kind::Class), name(std::move(n)), parentClass(std::move(p)),
          fields(std::move(f)), methods(std::move(m)) {}
};

// IOPlus input
struct IOPlusInputStmt : Stmt {
    std::vector<ExprPtr> targets;
    IOPlusInputStmt(std::vector<ExprPtr> t)
        : Stmt(Kind::IOPlusInput), targets(std::move(t)) {}
};

// IOPlus output
struct IOPlusOutputStmt : Stmt {
    std::vector<ExprPtr> values;
    IOPlusOutputStmt(std::vector<ExprPtr> v)
        : Stmt(Kind::IOPlusOutput), values(std::move(v)) {}
};

// start 块（主程序体）
struct StartBlockStmt : Stmt {
    std::vector<StmtPtr> body;
    StartBlockStmt(std::vector<StmtPtr> b)
        : Stmt(Kind::StartBlock), body(std::move(b)) {}
};

// 程序根节点
struct ProgramNode : Stmt {
    std::vector<StmtPtr> stmts;
    ProgramNode(std::vector<StmtPtr> s)
        : Stmt(Kind::Program), stmts(std::move(s)) {}
};
