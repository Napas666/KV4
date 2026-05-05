@echo off
cd /d "%~dp0"
pip install --no-index --find-links=wheels pymem customtkinter pygame pywin32
python kv4.py
pause
