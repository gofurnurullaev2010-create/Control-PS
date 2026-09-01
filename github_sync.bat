@echo off
chcp 65001 >nul
setlocal

rem Control PS loyihasini GitHub bilan sinxronlash.
rem O'zgarish bo'lsa commit qilib yuboradi, bo'lmasa hech nima qilmaydi.

set "PATH=C:\Program Files\Git\cmd;%PATH%"
cd /d "%~dp0"

git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo XATO: bu papka git repozitoriysi emas.
    exit /b 1
)

git add -A
git diff --cached --quiet
if not errorlevel 1 (
    echo O'zgarish yo'q - GitHub allaqachon yangi.
    exit /b 0
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH:mm"') do set "STAMP=%%i"

git commit -q -m "Avtomatik yangilanish: %STAMP%"
if errorlevel 1 (
    echo XATO: commit qilinmadi.
    exit /b 1
)

git push -q origin main
if errorlevel 1 (
    echo XATO: GitHubga yuborilmadi. Internet yoki kirish ma'lumotlarini tekshiring.
    exit /b 1
)

echo GitHub yangilandi: %STAMP%
exit /b 0
