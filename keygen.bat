@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3.11 "%~dp0keygen.py" %*
if errorlevel 1 py -3 "%~dp0keygen.py" %*
pause
