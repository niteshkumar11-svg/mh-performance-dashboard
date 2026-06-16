@echo off
REM ---- MH Performance Dashboard launcher ----
REM Double-click this file to start the dashboard and open it in your browser.
cd /d "%~dp0"
echo Starting MH Performance Dashboard...
echo (Keep this window open while using the dashboard. Close it to stop.)
python -m streamlit run app.py
pause
