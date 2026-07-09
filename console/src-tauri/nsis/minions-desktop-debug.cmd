@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not defined MINIONS_LOG_LEVEL set "MINIONS_LOG_LEVEL=debug"
set "MINIONS_DESKTOP_DEBUG=1"
set "RUST_BACKTRACE=1"
if not defined WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS set "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222"

set "MINIONS_DEBUG_DIR=%MINIONS_WORKING_DIR%"
if not defined MINIONS_DEBUG_DIR if defined COPAW_WORKING_DIR set "MINIONS_DEBUG_DIR=%COPAW_WORKING_DIR%"
if not defined MINIONS_DEBUG_DIR if exist "%USERPROFILE%\.copaw" set "MINIONS_DEBUG_DIR=%USERPROFILE%\.copaw"
if not defined MINIONS_DEBUG_DIR set "MINIONS_DEBUG_DIR=%USERPROFILE%\.minions"
set "MINIONS_BACKEND_LOGS=%MINIONS_DEBUG_DIR%\desktop.log;%MINIONS_DEBUG_DIR%\minions.log"
set "MINIONS_SHELL_LOGS=%LOCALAPPDATA%\io.agentscope.minions.desktop\logs\minions-desktop.log;%LOCALAPPDATA%\com.minions.desktop\logs\minions-desktop.log"

echo ====================================
echo Minions Desktop - Debug Mode
echo ====================================
echo Log level: %MINIONS_LOG_LEVEL%
echo Working directory: %MINIONS_DEBUG_DIR%
echo Press Ctrl+C to stop watching logs.
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0minions-desktop-debug.ps1"
