@echo off
setlocal
cd /d "%~dp0"

rem Procura o Python: launcher "py" com 3.12, depois qualquer 3.x, depois "python" no PATH.
set "PYTHON_CMD="
py -3.12 --version >nul 2>&1 && set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD (
    py -3 --version >nul 2>&1 && set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
    python --version >nul 2>&1 && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Python nao encontrado. Instale o Python 3.12 ou superior: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Usando: %PYTHON_CMD%
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Ambiente preparado com sucesso.
pause
exit /b 0

:error
echo Falha ao preparar o ambiente.
pause
exit /b 1
