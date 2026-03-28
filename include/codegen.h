#pragma once
#include "ast.h"
#include <string>
#include <sstream>
#include <unordered_set>

class CodeGen {
public:
    CodeGen();
    std::string generate(ProgramNode* prog);

private:
    std::ostringstream out;
    int indentLevel;
    bool hasIOPlus;
    bool hasFileOps;
    bool hasTime;                               // import:time
    bool hasRandom;                             // import:random
    std::unordered_set<std::string> templates;  // 已定义的 template 名
    std::unordered_set<std::string> namespaces; // 已定义的 namespace 名（成员访问用 ::）

    std::string indent();
    void inc() { indentLevel++; }
    void dec() { if (indentLevel > 0) indentLevel--; }

    void genProgram(ProgramNode* prog);
    void genStmt(Stmt* stmt);
    void genBlock(const std::vector<StmtPtr>& stmts);
    void genExprStmt(ExprStmt* s);
    void genVarDecl(VarDeclStmt* s);
    void genArrayDecl(ArrayDeclStmt* s);
    void genIf(IfStmt* s);
    void genSwitch(SwitchStmt* s);
    void genFor(ForStmt* s);
    void genWhile(WhileStmt* s);
    void genLoop(LoopStmt* s);
    void genDef(DefStmt* s);
    void genReturn(ReturnStmt* s);
    void genOutput(OutputStmt* s);
    void genInput(InputStmt* s);
    void genImport(ImportStmt* s);
    void genFile(FileStmt* s);
    void genTemplate(TemplateStmt* s);
    void genNamespace(NamespaceStmt* s);
    void genClass(ClassStmt* s);
    void genIOPlusInput(IOPlusInputStmt* s);
    void genIOPlusOutput(IOPlusOutputStmt* s);
    void genStartBlock(StartBlockStmt* s);

    std::string genExpr(Expr* e);
    std::string genExprStr(Expr* e);

    std::string mapType(const std::string& wqType);
};
