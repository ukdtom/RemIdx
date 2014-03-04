@echo off

echo #################################################################
echo Build Windows Executables
echo Note: Requires PyInstaller
echo #################################################################

echo Building 64bit
pyinstaller -F RemIdx.py -n RemIdx-64bit
echo Moving dist\RemIdx.exe to .
move /y dist\RemIdx-64bit.exe .

rmdir /s/q dist
rmdir /s/q build

echo Building 32bit
C:\Python27-32bit\Scripts\pyinstaller -F RemIdx.py -n RemIdx-32bit
echo Moving dist\RemIdx-32bit.exe to .
move /y dist\RemIdx-32bit.exe .

rmdir /s/q dist
rmdir /s/q build

echo .
echo #################################################################
echo Build Done.
echo #################################################################
pause