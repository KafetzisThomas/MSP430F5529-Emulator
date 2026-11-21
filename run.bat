@echo off
cd /d "%~dp0"
python simulator_imgui.py
if errorlevel 1 pause
