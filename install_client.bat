@echo off
rem ============================================================
rem  TALABA KOMPYUTERIGA O'RNATISH
rem  Bu faylni student_client.exe va config.ini bilan bir
rem  papkada ishga tushiring (ikki marta bosing).
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

copy /y "%~dp0student_client.exe" "%TARGET%\" >nul
copy /y "%~dp0config.ini"         "%TARGET%\" >nul

rem Har safar kompyuter yonib, foydalanuvchi kirganda avtomatik ishga tushirish:
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ExamMonitorClient /t REG_SZ /d "\"%TARGET%\student_client.exe\"" /f >nul

rem Hozirning o'zida ishga tushirish:
start "" "%TARGET%\student_client.exe"

echo.
echo ============================================================
echo  TAYYOR.
echo  - Dastur %TARGET% papkasiga o'rnatildi va ishga tushdi.
echo  - Kompyuter har yoqilib login qilinganda avtomatik ishlaydi.
echo  - Ekran yuqorisida qizil "Imtihon nazorati faol" belgisi
echo    paydo bo'lishi kerak.
echo  Olib tashlash uchun: uninstall_client.bat
echo ============================================================
pause
