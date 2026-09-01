@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "tv_tools_env.bat" call "tv_tools_env.bat"
py -3 main.py
if errorlevel 1 pause
