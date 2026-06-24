@echo off
title AEEP - AI Engineering Execution Platform

echo ============================================================
echo   AEEP - AI Engineering Execution Platform
echo   Starting...
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python dependencies...
uv sync --quiet
if errorlevel 1 (
    echo [ERROR] Dependency install failed. Check your internet connection.
    pause
    exit /b 1
)
echo [1/3] Done.

echo [2/3] Installing Playwright browser (skipped if already installed)...
uv run python -m playwright install chromium
echo [2/3] Done.

echo [3/3] Launching Web UI...
echo.
echo   Open in browser: http://localhost:7860
echo   Close this window to stop the server.
echo.
uv run python app.py

pause
