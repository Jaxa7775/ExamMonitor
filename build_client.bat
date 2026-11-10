@echo off
rem Talaba klientini bitta .exe faylga aylantiradi (o'qituvchi kompyuterida bajariladi).
rem Pillow .exe ichiga paketlanadi, shuning uchun talaba kompyuteriga Python kerak bo'lmaydi.
cd /d "%~dp0"
py -m PyInstaller --noconsole --onefile --name student_client ^
   --collect-all comtypes ^
   --collect-all uiautomation ^
   --collect-all pyaudio ^
   --hidden-import comtypes.stream ^
   student_client.py
echo.
echo ============================================================
echo  Tayyor:  dist\student_client.exe
echo.
echo  Talaba kompyuteriga ko'chirish uchun kerakli fayllar:
echo     1) dist\student_client.exe
echo     2) config.ini
echo     3) install_client.bat
echo     4) uninstall_client.bat
echo  Ularni bitta papkaga qo'ying va talaba kompyuterida
echo  install_client.bat ni ishga tushiring.
echo ============================================================
pause
