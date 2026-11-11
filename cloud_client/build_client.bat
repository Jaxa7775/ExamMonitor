@echo off
rem Talaba klientini bitta .exe faylga aylantiradi (o'qituvchi kompyuterida bajariladi).
cd /d "%~dp0"
py -m pip install --upgrade websocket-client pillow uiautomation pyinstaller
py -m PyInstaller --noconsole --onefile --name student_client ^
   --collect-all comtypes ^
   --collect-all uiautomation ^
   --collect-all websocket ^
   --hidden-import comtypes.stream ^
   student_client.py
echo.
echo ============================================================
echo  Tayyor:  dist\student_client.exe
echo.
echo  Talaba kompyuteriga ko'chirish uchun kerakli fayllar:
echo     1) dist\student_client.exe
echo     2) config.ini   (config.example.ini dan nusxalab, to'ldiring)
echo     3) install_client.bat
echo     4) uninstall_client.bat
echo ============================================================
pause
