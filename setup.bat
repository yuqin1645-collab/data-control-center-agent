@echo off
chcp 65001 >nul
title 数据中控 Agent - 环境安装

cd /d "%~dp0"

echo ========================================
echo   数据中控 Agent - 环境安装 (uv)
echo ========================================

echo.
echo [1/4] 创建虚拟环境 + 安装 Python 依赖...
where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv 未安装，请先安装: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

if exist .venv\Scripts\python.exe (
    echo   .venv 已存在，跳过创建
) else (
    echo   创建虚拟环境...
    uv venv .venv
    if errorlevel 1 (
        echo [ERROR] uv venv 创建失败
        pause
        exit /b 1
    )
)

uv pip install -r requirements_minimal.txt
if errorlevel 1 (
    echo.
    echo === 批量安装失败，逐个安装 ===
    uv pip install openai tiktoken chromadb sqlparse networkx pyyaml python-dotenv
    uv pip install wikipedia fastapi uvicorn python-multipart
    uv pip install "python-jose[cryptography]" bcrypt
    uv pip install sentence-transformers
)

echo.
echo [2/4] 初始化数据库...
set PYTHONPATH=.
.venv\Scripts\python.exe scripts\init_db.py
.venv\Scripts\python.exe scripts\init_auth.py

echo.
echo [3/4] 索引文档 + 知识图谱...
.venv\Scripts\python.exe scripts\index_documents.py
.venv\Scripts\python.exe scripts\build_graph.py

echo.
echo [4/4] 安装前端依赖...
cd frontend\react
if exist node_modules (
    echo   node_modules 已存在，跳过安装
) else (
    call npm install
)

echo.
echo ========================================
echo   安装完成! 运行 start.bat 启动
echo ========================================
pause
