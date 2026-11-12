@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual ausente: %CD%\.venv
    echo Execute setup_env.bat uma vez antes de iniciar a aplicacao.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py
set "APP_EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %APP_EXIT_CODE%
