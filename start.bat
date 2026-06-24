@echo off
title AEEP - AI Engineering Execution Platform

echo ============================================================
echo   AEEP - AI Engineering Execution Platform
echo   Starting...
echo ============================================================
echo.

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv not found. Installing...
    powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
)

cd /d "%~dp0"

echo [1/3] Checking Python dependencies...
uv sync --quiet
if errorlevel 1 (
    echo [ERROR] Dependency install failed. Check your internet connection.
    pause
    exit /b 1
)
echo [1/3] Done.

echo [2/3] Checking Playwright browser...
uv run playwright install chromium --quiet 2>nul
if errorlevel 1 (
    echo [2/3] Installing Playwright browser (first time, ~100MB)...
    uv run playwright install chromium
)
echo [2/3] Done.

echo [3/3] Launching Web UI...
echo.
echo   Open in browser: http://localhost:7860
echo   Close this window to stop the server.
echo.
uv run python app.py

pause
