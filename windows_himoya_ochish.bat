@echo off
chcp 65001 >nul
title Control PS — Windows Defender ruxsati
echo.
echo  ControlPS_v216.exe virus EMAS.
echo  Windows Defender PyInstaller .exe ni noto'g'ri belgilaydi.
echo  Faqat shu papkaga ruxsat beriladi — himoya o'chirilmaydi.
echo.
echo  Administrator huquqi kerak.
echo.

net session >nul 2>&1
if errorlevel 1 (
  echo XATO: o'ng tugma → "Запуск от имени администратора"
  pause
  exit /b 1
)

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Add-MpPreference -ExclusionPath '%ROOT%' -ErrorAction Stop; Write-Host 'Papka ruxsat: %ROOT%'"
if errorlevel 1 (
  echo Defender ruxsat qo'shilmadi.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-ChildItem -LiteralPath '%ROOT%' -Filter 'ControlPS_v*.exe' -ErrorAction SilentlyContinue | ForEach-Object { Unblock-File -LiteralPath $_.FullName; Add-MpPreference -ExclusionProcess $_.Name }"

echo.
echo Tayyor. Endi:
echo  1^) Windows Xavfsizlik → Virus va tahdidlardan himoya → Himoya tarixi
echo  2^) ControlPS_v216.exe ni "Восстановить" / Restore qiling (agar o'chirilgan bo'lsa)
echo  3^) Dastur papkasidan ControlPS_v216.exe ni qayta oching
echo.
pause
