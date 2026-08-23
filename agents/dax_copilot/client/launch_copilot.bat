@echo off
title Comercial Tinito - DAX Copilot
if exist "%~dp0launch_copilot.protected.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_copilot.protected.ps1"
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_copilot.ps1"
)
pause
