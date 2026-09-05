@echo off
setlocal EnableExtensions
cd /d "%~dp0controlps-lock-android"

if not defined ANDROID_HOME (
  if exist "%LOCALAPPDATA%\Android\Sdk" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
)
if not defined ANDROID_HOME (
  if exist "%USERPROFILE%\AppData\Local\Android\Sdk" set "ANDROID_HOME=%USERPROFILE%\AppData\Local\Android\Sdk"
)
if not defined ANDROID_SDK_ROOT if defined ANDROID_HOME set "ANDROID_SDK_ROOT=%ANDROID_HOME%"

if defined ANDROID_HOME (
  powershell -NoProfile -Command "$p=$env:ANDROID_HOME -replace '\\','\\'; Set-Content -Path 'local.properties' -Value ('sdk.dir=' + $p) -Encoding ASCII"
)

if exist "gradlew.bat" (
  call gradlew.bat assembleRelease --no-daemon
) else (
  echo gradlew.bat yo'q — gradle wrapper kerak.
  exit /b 1
)

set "APK=app\build\outputs\apk\release\app-release.apk"
if not exist "%APK%" set "APK=app\build\outputs\apk\debug\app-debug.apk"
if not exist "%APK%" (
  echo APK yig'ilmadi.
  exit /b 1
)
copy /Y "%APK%" "%~dp0controlps-lock.apk"
echo Tayyor: %~dp0controlps-lock.apk
endlocal
