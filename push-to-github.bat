@echo off
chcp 65001 >nul
REM 数据中控 Agent 一键推送到 GitHub
REM 前置: 已安装 gh 并登录 (gh auth login)

cd /d "%~dp0"

echo ============================================
echo  数据中控 Agent - GitHub 推送脚本
echo ============================================
echo.

REM 检查 gh 是否可用
where gh >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 gh 命令, 请确认已安装 GitHub CLI 并加入 PATH
    echo 下载: https://cli.github.com/
    pause
    exit /b 1
)

REM 检查登录状态
echo [1/4] 检查 GitHub 登录状态...
gh auth status >nul 2>nul
if errorlevel 1 (
    echo [需要登录] 请在弹出的浏览器中完成 GitHub 登录
    gh auth login --web --git-protocol https
    if errorlevel 1 (
        echo [错误] 登录失败
        pause
        exit /b 1
    )
)
echo 登录正常.
echo.

REM git 初始化
echo [2/4] 初始化 git 仓库...
if not exist ".git" (
    git init
    git branch -M main
) else (
    echo 仓库已存在, 跳过 init.
)
git add .
git commit -m "feat: 数据中控 Agent - 5路检索 (Text-to-SQL/传统RAG/GraphRAG/Wiki/SAG)" --allow-empty
echo.

REM 创建 GitHub 仓库并推送
echo [3/4] 创建 GitHub 仓库并推送...
echo 仓库名: data-control-center-agent
echo 描述: 企业数据中控 Agent - 多源数据自然语言查询 (Text-to-SQL/传统RAG/GraphRAG/Wiki/SAG)
echo.
echo 选择可见性: 输入 1=公开(推荐, 面试官能看)  2=私有
set /p VIS="可见性 [1]: "
if "%VIS%"=="" set VIS=1
if "%VIS%"=="1" (
    set VIS_FLAG=--public
) else (
    set VIS_FLAG=--private
)

gh repo create data-control-center-agent --source=. %VIS_FLAG% --push --description "企业数据中控 Agent - 多源数据自然语言查询 (Text-to-SQL/传统RAG/GraphRAG/Wiki/SAG)"
if errorlevel 1 (
    echo.
    echo [错误] 创建失败. 可能仓库名已存在, 或网络问题.
    echo 如果已存在同名仓库, 可以去 GitHub 删掉再跑, 或改个名字.
    pause
    exit /b 1
)

echo.
echo [4/4] 完成!
echo.
echo 仓库地址:
gh repo view --web 2>nul
echo.
echo 简历上填这个链接:
echo   https://github.com/%USERNAME%/data-control-center-agent
echo (把 %USERNAME% 换成你的 GitHub 用户名, 用 gh api user --jq .login 查看)
echo.
pause
