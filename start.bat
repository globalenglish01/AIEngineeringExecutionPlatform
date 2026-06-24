@echo off
chcp 65001 >nul
title AEEP · AI 工程执行平台

echo ============================================================
echo   AEEP · AI 工程执行平台  ^|  一键启动
echo ============================================================
echo.

:: 检查 uv 是否安装
where uv >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 uv，正在安装...
    powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
)

:: 切换到项目目录
cd /d "%~dp0"

:: 安装依赖（已安装则跳过）
echo [1/3] 检查 Python 依赖...
uv sync --quiet
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)

:: 安装 Playwright 浏览器（首次需要下载，约 100MB）
echo [2/3] 检查 Playwright 浏览器...
uv run playwright install chromium --quiet 2>nul
if errorlevel 1 (
    echo [提示] Playwright 浏览器首次安装，请稍候...
    uv run playwright install chromium
)

:: 启动 Web UI
echo [3/3] 启动 Web UI...
echo.
echo   访问地址: http://localhost:7860
echo   关闭本窗口即可停止服务
echo.
uv run python app.py

pause
