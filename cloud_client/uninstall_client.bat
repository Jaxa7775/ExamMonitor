@echo off
rem Talaba kompyuteridan olib tashlash
setlocal
set "TARGET=C:\ExamMonitor"
taskkill /f /im student_client.exe >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ExamMonitorClient /f >nul 2>&1
if exist "%TARGET%" rmdir /s /q "%TARGET%"
echo Imtihon nazorati klienti olib tashlandi.
pause
