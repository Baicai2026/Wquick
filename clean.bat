@echo off
:: ========================================================
:: ✅ BFG 清理脚本（修复版）—— 加强路径检测 + 调试信息
:: 作者：你的助手（AI）
:: 用途：永久删除 1.5compiler.7z + 安全重建仓库
:: 特别：自动打印路径 + 检查 bfg.jar 是否真实存在
:: ========================================================

set REPO_DIR=%~dp0
set BFG_JAR="%REPO_DIR%bfg.jar"
set BACKUP_DIR="%REPO_DIR%backup_%date:~0,4%-%date:~5,2%-%date:~8,2%_%time:~0,2%-%time:~3,2%-%time:~6,2%"

echo.
echo [DEBUG] 当前脚本路径：%REPO_DIR%
echo [DEBUG] BFG JAR 文件路径：%BFG_JAR%
echo [DEBUG] 备份路径：%BACKUP_DIR%
echo.

:: ========================
:: 1. 检查 bfg.jar 是否存在
:: ========================
if not exist %BFG_JAR% (
    echo [ERROR] 未找到 bfg.jar 文件！
    echo [ERROR] 请确认：
    echo   - 文件名必须是 bfg.jar（小写）
    echo   - 放在脚本同目录： %REPO_DIR%
    echo   - 没有隐藏扩展名（如 bfg.jar.txt）
    echo.
    dir "%REPO_DIR%" /b
    echo.
    pause
    exit /b 1
)

:: ========================
:: 2. 验证 bfg.jar 是否真实可读
:: ========================
echo [INFO] 正在验证 bfg.jar 文件...
for /f "tokens=1" %%i in ('dir /b "%BFG_JAR%" ^| findstr /i "bfg.jar"') do (
    echo [OK] 发现 bfg.jar 文件：%%i
    set BFG_FILE=%%i
)

if not defined BFG_FILE (
    echo [ERROR] 找不到 bfg.jar！可能是文件名拼写错误。
    pause
    exit /b 1
)

echo [OK] bfg.jar 文件检测通过 ✅

:: ========================
:: 3. 进行备份
:: ========================
echo [INFO] 正在备份当前项目...
xcopy "%REPO_DIR%" "%BACKUP_DIR%" /s /e /h /i /y >nul
echo [OK] 备份完成：可随时还原！

:: ========================
:: 4. 删除 .git 文件夹
:: ========================
echo [INFO] 正在删除旧 .git 文件夹...
rd /s /q "%REPO_DIR%.git" >nul 2>&1
if errorlevel 1 (
    echo [WARN] 未找到 .git 或权限不足，继续...
)

:: ========================
:: 5. 初始化 Git
:: ========================
echo [INFO] 初始化新的 Git 仓库...
git init >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git 初始化失败，请检查是否安装 Git！
    echo [ERROR] 请在终端运行：git --version
    pause
    exit /b 1
)

echo [INFO] 添加所有文件...
git add . >nul 2>&1

echo [INFO] 生成初始提交...
git commit -m "Initial commit after cleaning 1.5compiler.7z" >nul 2>&1

:: ========================
:: 6. 使用 BFG 删除文件
:: ========================
echo [INFO] 使用 BFG 删除 1.5compiler.7z...
java -jar "%BFG_JAR%" --delete-files "1.5compiler.7z" .git

:: ========================
:: 7. 精简 Git
:: ========================
echo [INFO] 清理 Git 历史...
git reflog expire --expire=now --all && git gc --prune=now --aggressive
if errorlevel 1 (
    echo [ERROR] Git 清理失败！
    pause
    exit /b 1
)

echo.
echo [SUCCESS] ✅ 清理完成！
echo   - 1.5compiler.7z 已永久删除
echo   - 原始项目备份到： %BACKUP_DIR%
echo.
echo [NOTE] 请现在运行以下命令推送：
echo   git remote add origin <你的Git仓库地址>
echo   git push -f origin master v1.5
echo.
echo [WARNING] 强制推送会改写历史，团队成员需重置分支！
echo.

pause