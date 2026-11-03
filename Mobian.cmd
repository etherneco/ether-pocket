@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Switch-EtherPocket.ps1" -System Mobian
pause
