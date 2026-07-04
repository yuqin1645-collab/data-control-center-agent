@echo off
chcp 65001 >nul
title 数据中控 Agent

echo ========================================
echo   数据中控 Agent - 启动中...
echo ========================================

cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo [ERROR] .venv 不存在，请先运行 setup.bat
    pause
    exit /b 1
)

echo.
echo [1/2] 启动后端 API (端口 8000)...
start "DCCA Backend" cmd /k "cd /d %~dp0 && set PYTHONPATH=. && .venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000"

echo [2/2] 启动前端 (端口 3000)...
cd frontend\react
start "DCCA Frontend" cmd /k "cd /d %~dp0\frontend\react && npm run dev"

echo.
echo ========================================
echo   启动完成!
echo   后端: http://localhost:8000
echo   前端: http://localhost:3000
echo   登录: admin / admin123
echo ========================================
echo.
echo 5 秒后打开浏览器...
timeout /t 5 /nobreak >nul
start http://localhost:3000

echo 按任意键关闭此窗口（后端和前端会继续运行）
pause >nul
