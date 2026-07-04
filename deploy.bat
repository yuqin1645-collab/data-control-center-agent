@echo off
chcp 65001 >nul
REM 数据中控 Agent 一键部署到 GitHub
REM 用法: 双击运行, 或在项目根目录执行 deploy.bat

cd /d "%~dp0"

echo ============================================
echo  数据中控 Agent - GitHub 一键部署
echo ============================================
echo.

REM 1. 检查 gh 是否安装
where gh >nul 2>nul
if errorlevel 1 (
    echo [X] 未检测到 gh CLI, 请先安装: https://cli.github.com/
    pause
    exit /b 1
)
echo [OK] gh 已安装

REM 2. 检查 gh 登录状态
echo.
echo 检查 GitHub 登录状态...
gh auth status >nul 2>nul
if errorlevel 1 (
    echo [!] 未登录 GitHub, 正在打开浏览器登录...
    echo     按提示完成登录后, 重新运行本脚本
    gh auth login --web --git-protocol https
    if errorlevel 1 (
        echo [X] 登录失败
        pause
        exit /b 1
    )
)
echo [OK] GitHub 已登录

REM 3. 读取仓库名 (默认 data-control-center-agent)
set REPO_NAME=data-control-center-agent
echo.
set /p REPO_NAME=仓库名 (回车默认 %REPO_NAME%):

REM 4. 选择可见性
echo.
echo 仓库可见性:
echo   1) public  (公开, 面试官可查看 - 推荐)
echo   2) private (私有)
set /p VIS_CHOICE=选择 (回车默认 1):
if "%VIS_CHOICE%"=="2" (
    set VIS_FLAG=--private
) else (
    set VIS_FLAG=--public
)

REM 5. git init + commit
echo.
echo [1/3] 初始化 git 仓库...
if not exist .git (
    git init
    git branch -M main
) else (
    echo     已是 git 仓库, 跳过 init
)
git add .
git commit -m "feat: 数据中控 Agent - 5路检索 (Text-to-SQL/传统RAG/GraphRAG/Wiki/SAG)" --quiet
if errorlevel 1 (
    echo     无新增改动或提交失败, 继续
)
echo [OK] 代码已提交

REM 6. 创建 GitHub 仓库并推送
echo.
echo [2/3] 创建 GitHub 仓库并推送...
gh repo create %REPO_NAME% %VIS_FLAG% --source=. --remote=origin --push
if errorlevel 1 (
    echo.
    echo [X] 创建/推送失败. 可能原因:
    echo     - 仓库已存在: 改名或先删除旧仓库
    echo     - 网络问题: 检查代理
    echo.
    echo 手动命令:
    echo   git remote add origin https://github.com/<你的用户名>/%REPO_NAME%.git
    echo   git push -u origin main
    pause
    exit /b 1
)

REM 7. 输出仓库地址
echo.
echo [3/3] 获取仓库地址...
for /f "delims=" %%i in ('gh repo view %REPO_NAME% --json url -q .url') do set REPO_URL=%%i
echo.
echo ============================================
echo  部署成功!
echo  仓库地址: %REPO_URL%
echo ============================================
echo.
echo 把这个地址加到简历项目名旁边即可.
echo.
pause
