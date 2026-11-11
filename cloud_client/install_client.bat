@echo off
rem ============================================================
rem  TALABA KOMPYUTERIGA O'RNATISH (bulutli versiya)
rem  student_client.exe va config.ini bilan bir papkada ishga tushiring.
rem  Admin huquqi SHART EMAS.
rem ============================================================
setlocal
set "TARGET=C:\ExamMonitor"

echo Imtihon nazorati klienti o'rnatilmoqda...

if not exist "%TARGET%" mkdir "%TARGET%"

if not exist "%~dp0student_client.exe" (
  echo [XATO] student_client.exe shu papkada topilmadi.
  echo Avval o'qituvchi kompyuterida build_client.bat ni ishga tushiring.
  pause
  exit /b 1
)
if not exist "%~dp0config.ini" (
  echo [XATO] config.ini topilmadi. config.example.ini dan nusxalab to'ldiring.
  pause
  exit /b 1
)

copy /y "%~dp0student_client.exe" "%TARGET%\" >nul
copy /y "%~dp0config.ini"         "%TARGET%\" >nul

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ExamMonitorClient /t REG_SZ /d "\"%TARGET%\student_client.exe\"" /f >nul

start "" "%TARGET%\student_client.exe"

echo.
echo ============================================================
echo  TAYYOR.  Dastur %TARGET% ga o'rnatildi va ishga tushdi.
echo  Kompyuter har login qilinganda avtomatik ishlaydi.
echo  Olib tashlash: uninstall_client.bat
echo ============================================================
pause
