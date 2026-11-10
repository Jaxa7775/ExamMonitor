@echo off
rem Talaba kompyuteridan klientni butunlay olib tashlaydi.
echo Imtihon nazorati klienti olib tashlanmoqda...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ExamMonitorClient /f >nul 2>&1
taskkill /im student_client.exe /f >nul 2>&1
timeout /t 1 /nobreak >nul
rmdir /s /q "C:\ExamMonitor" >nul 2>&1
echo Olib tashlandi.
pause
