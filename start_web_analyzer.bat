@echo off
echo ============================================================
echo Financial Document Analyzer - Web Interface
echo ============================================================
echo.
echo Starting server...
echo.
echo Open your browser to: http://localhost:8080
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

cd /d "%~dp0"
.venv\Scripts\python analyzer_server.py

pause
