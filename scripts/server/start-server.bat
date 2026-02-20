@echo off
REM TCG Card Scanner Server - Windows
REM
REM Usage: start-server.bat

cd /d "%~dp0.."

REM Load environment from .env if exists
if exist .env (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        set %%a=%%b
    )
)

echo Starting TCG Card Scanner...
echo Open http://localhost:5000 in your browser
echo.

tcg server
