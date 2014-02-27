@echo off

echo #################################################################
echo Build Windows Executable
echo Note: Requires PyInstaller
echo #################################################################

pyinstaller -F RemIdx.py
echo Moving dist\RemIdx.exe to .
move /y dist\RemIdx.exe .

rmdir /s/q dist
rmdir /s/q build

echo .
echo #################################################################
echo Build Done.
echo #################################################################
pause