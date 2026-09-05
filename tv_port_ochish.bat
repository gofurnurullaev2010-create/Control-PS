@echo off
chcp 65001 >nul
title Control PS — TV port 8099
echo Windows firewall da TCP 8099 ni ochamiz (TV START/STOP uchun).
echo Administrator huquqi kerak.
netsh advfirewall firewall delete rule name="ControlPS TV lock gate 8099" >nul 2>&1
netsh advfirewall firewall add rule name="ControlPS TV lock gate 8099" dir=in action=allow protocol=TCP localport=8099 enable=yes profile=any
if errorlevel 1 (
  echo XATO: o'ng tugma → "Administrator sifatida ishga tushirish"
  pause
  exit /b 1
)
echo Tayyor. Control PS ni qayta oching.
pause
