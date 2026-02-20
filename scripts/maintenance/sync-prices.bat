@echo off
REM TCG Price Sync - Windows Batch Script
REM Schedule with Task Scheduler to run daily
REM
REM Usage: sync-prices.bat

cd /d "%~dp0.."

REM Load environment from .env if exists
if exist .env (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        set %%a=%%b
    )
)

REM Run price sync
tcg sync

pause
