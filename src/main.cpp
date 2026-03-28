#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstdlib>
#include <ctime>
// 自己的头文件必须在 windows.h 之前，避免 THIS 等宏污染枚举
#include "lexer.h"
#include "parser.h"
#include "codegen.h"
// windows.h 放最后，并加保护宏
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#undef THIS   // windows.h 可能通过 ole2/objbase 定义 THIS 宏

// 返回 wqc.exe 所在目录（末尾带 \）
static std::string exeDir() {
    char buf[MAX_PATH];
    DWORD n = GetModuleFileNameA(nullptr, buf, MAX_PATH);
    if (n == 0) return "";
    std::string p(buf, n);
    auto pos = p.rfind('\\');
    return pos == std::string::npos ? "" : p.substr(0, pos + 1);
}

// ── Log 工具 ──────────────────────────────────────────────────────
// 写到 wqc.exe 同目录的 wqide.log，追加模式，带时间戳
static std::string g_logPath;

static void initLog() {
    g_logPath = exeDir() + "wqide.log";
}

static void logWrite(const std::string& level, const std::string& msg) {
    if (g_logPath.empty()) return;
    std::ofstream f(g_logPath, std::ios::app);
    if (!f.is_open()) return;
    // 时间戳
    std::time_t t = std::time(nullptr);
    char ts[20];
    std::strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", std::localtime(&t));
    f << "[" << ts << "] [" << level << "] " << msg << "\n";
}

#define LOG_INFO(msg)  logWrite("INFO",  msg)
#define LOG_WARN(msg)  logWrite("WARN",  msg)
#define LOG_ERROR(msg) logWrite("ERROR", msg)

// ─────────────────────────────────────────────────────────────────

// 解析 g++ 路径：WQ_GCC 环境变量 > wqc.exe 同目录 g++.exe > PATH 里的 g++
static std::string findGxx() {
    // 1. 环境变量
    const char* env = std::getenv("WQ_GCC");
    if (env && env[0]) return std::string(env);
    // 2. wqc.exe 旁边有 g++.exe（把 g++.exe 放到 wqc.exe 同目录即可免配置）
    std::string sib = exeDir() + "g++.exe";
    if (GetFileAttributesA(sib.c_str()) != INVALID_FILE_ATTRIBUTES) return sib;
    // 3. PATH（返回裸命令，让 cmd 自己搜）
    return "g++";
}

// 把任意路径转为绝对路径（解决 cmd 子进程工作目录不一致的问题）
static std::string toAbsPath(const std::string& path) {
    char buf[MAX_PATH];
    DWORD n = GetFullPathNameA(path.c_str(), MAX_PATH, buf, nullptr);
    if (n == 0 || n >= MAX_PATH) return path;  // 失败则原样返回
    return std::string(buf, n);
}

static std::string readFile(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open()) {
        throw std::runtime_error("Cannot open file: " + path);
    }
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

static void writeFile(const std::string& path, const std::string& content) {
    std::ofstream f(path);
    if (!f.is_open()) {
        throw std::runtime_error("Cannot write file: " + path);
    }
    f << content;
}

static void printUsage(const char* prog) {
    std::cerr << "Wquick Compiler v1.4\n";
    std::cerr << "Usage:\n";
    std::cerr << "  " << prog << " <source.wq>              -- compile and run\n";
    std::cerr << "  " << prog << " <source.wq> -o <output>  -- compile to binary\n";
    std::cerr << "  " << prog << " <source.wq> --emit-cpp   -- emit C++ source only\n";
    std::cerr << "  " << prog << " <source.wq> --tokens     -- dump tokens\n";
}

int main(int argc, char* argv[]) {
    initLog();

    if (argc < 2) {
        printUsage(argv[0]);
        return 1;
    }

    std::string srcFile = argv[1];
    std::string outputFile;
    bool emitCpp = false;
    bool dumpTokens = false;
    bool runAfter = true;

    for (int i = 2; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--emit-cpp") { emitCpp = true; runAfter = false; }
        else if (arg == "--tokens") { dumpTokens = true; runAfter = false; }
        else if (arg == "-o" && i + 1 < argc) {
            outputFile = argv[++i];
            runAfter = false;
        }
    }

    // WQ_OUT 环境变量：IDE 用来指定输出 exe 路径（优先级高于 -o）
    const char* wqOut = std::getenv("WQ_OUT");
    if (wqOut && wqOut[0]) {
        outputFile = std::string(wqOut);
        runAfter = true;   // IDE 模式：编译完直接运行
        LOG_INFO("WQ_OUT=" + outputFile);
    }

    // WQ_NORUN 环境变量：IDE 设置后，wqc 只编译不运行（IDE 自己负责运行）
    const char* wqNoRun = std::getenv("WQ_NORUN");
    if (wqNoRun && wqNoRun[0] && std::string(wqNoRun) != "0") {
        runAfter = false;
        LOG_INFO("WQ_NORUN set, skip auto-run");
    }

    LOG_INFO("source=" + srcFile);

    // 读取源文件
    std::string source;
    try {
        source = readFile(srcFile);
    } catch (const std::exception& e) {
        std::string msg = std::string("Cannot open source: ") + e.what();
        std::cerr << "Error: " << e.what() << "\n";
        LOG_ERROR(msg);
        return 1;
    }

    // 词法分析
    Lexer lexer(source);
    std::vector<Token> tokens;
    try {
        tokens = lexer.tokenize();
    } catch (const std::exception& e) {
        std::string msg = std::string("[Lexer Error] ") + e.what();
        std::cerr << msg << "\n";
        LOG_ERROR(msg);
        return 1;
    }

    if (dumpTokens) {
        for (auto& tok : tokens) {
            std::cout << "[" << tok.line << ":" << tok.col << "] "
                      << (int)tok.type << " '" << tok.value << "'\n";
        }
        return 0;
    }

    // 语法分析
    Parser parser(std::move(tokens));
    std::unique_ptr<ProgramNode> ast;
    try {
        ast = parser.parse();
    } catch (const std::exception& e) {
        std::string msg = std::string("[Parser Error] ") + e.what();
        std::cerr << msg << "\n";
        LOG_ERROR(msg);
        return 1;
    }

    // 代码生成
    CodeGen cg;
    std::string cppCode;
    try {
        cppCode = cg.generate(ast.get());
    } catch (const std::exception& e) {
        std::string msg = std::string("[CodeGen Error] ") + e.what();
        std::cerr << msg << "\n";
        LOG_ERROR(msg);
        return 1;
    }

    if (emitCpp) {
        std::cout << cppCode;
        return 0;
    }

    // 写入临时 cpp 文件 —— 全部使用绝对路径，避免 cmd 子进程工作目录不一致
    std::string absSrc   = toAbsPath(srcFile);
    std::string tmpCpp   = absSrc + ".tmp.cpp";
    std::string binFile  = outputFile.empty() ? (absSrc + ".exe") : toAbsPath(outputFile);
    writeFile(tmpCpp, cppCode);

    LOG_INFO("binFile=" + binFile);

    // 查找 g++ 可执行文件
    std::string gccPath = findGxx();
    LOG_INFO("g++=" + gccPath);

    // ── 用 CreateProcess + 管道捕获 g++ 输出 ────────────────────────
    // 构造命令行（和原来一样的参数）
    std::string compileArgs =
        "\"" + gccPath + "\" -std=c++17 -O2 -o \"" + binFile + "\" \"" + tmpCpp + "\" -lpthread";

    SECURITY_ATTRIBUTES sa{};
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;

    HANDLE hReadOut, hWriteOut;
    CreatePipe(&hReadOut, &hWriteOut, &sa, 0);
    SetHandleInformation(hReadOut, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOA si{};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = hWriteOut;
    si.hStdError  = hWriteOut;

    PROCESS_INFORMATION pi{};
    std::string cmdLine = "cmd /c \"" + compileArgs + "\"";

    // CreateProcess 需要可写 buffer
    std::vector<char> cmdBuf(cmdLine.begin(), cmdLine.end());
    cmdBuf.push_back('\0');

    BOOL ok = CreateProcessA(
        nullptr, cmdBuf.data(), nullptr, nullptr,
        TRUE, CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi);

    CloseHandle(hWriteOut);  // 父进程关掉写端，才能读到 EOF

    std::string gppOutput;
    if (ok) {
        char buf[4096];
        DWORD nRead;
        while (ReadFile(hReadOut, buf, sizeof(buf) - 1, &nRead, nullptr) && nRead > 0) {
            buf[nRead] = '\0';
            gppOutput += buf;
        }
        WaitForSingleObject(pi.hProcess, INFINITE);
        DWORD exitCode = 0;
        GetExitCodeProcess(pi.hProcess, &exitCode);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        CloseHandle(hReadOut);

        if (exitCode != 0) {
            // 把 g++ 的输出原样打到 stderr（IDE 会捕获）
            std::cerr << gppOutput;
            std::cerr << "[Compile Error] g++ failed.\n";
            std::cerr << "g++ path used: " << gccPath << "\n";
            LOG_ERROR("g++ failed, output:\n" + gppOutput);
            std::remove(tmpCpp.c_str());
            return 1;
        }
        // 编译成功时把 g++ 输出写进 log（通常是空，保留备查）
        if (!gppOutput.empty()) {
            LOG_INFO("g++ output:\n" + gppOutput);
        }
    } else {
        CloseHandle(hReadOut);
        std::string msg = "[Compile Error] CreateProcess failed, g++=" + gccPath;
        std::cerr << msg << "\n";
        LOG_ERROR(msg);
        std::remove(tmpCpp.c_str());
        return 1;
    }

    std::remove(tmpCpp.c_str());
    std::cout << "[OK] Compiled -> " << binFile << "\n";
    LOG_INFO("compile OK -> " + binFile);

    if (runAfter) {
        std::cout << "[Run]\n";
        // binFile 已是绝对路径，用引号包裹直接运行
        int ret = std::system(("\"" + binFile + "\"").c_str());
        LOG_INFO("run exit=" + std::to_string(ret));
        return ret;
    }
    return 0;
}
