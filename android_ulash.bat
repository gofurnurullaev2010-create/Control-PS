@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Control PS — Android TV ulash
echo.
echo  Control PS — Android TV ni qo'shish
echo  ===================================
echo.
py -3.11 "%~dp0android_ulash.py" %*
if errorlevel 1 py -3 "%~dp0android_ulash.py" %*
echo.
pause
