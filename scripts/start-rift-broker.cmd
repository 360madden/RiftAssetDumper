@echo off
setlocal
set "REPO_ROOT=%~dp0.."
set "BROKER=%REPO_ROOT%\scripts\rift_broker.py"

if not defined RIFTREADER_PYTHON (
    py -3 --version >nul 2>nul
    if not errorlevel 1 ( set "PY=py -3" & goto FOUND )
    python --version >nul 2>nul
    if not errorlevel 1 ( set "PY=python" & goto FOUND )
    echo ERROR: No Python found. Set RIFTREADER_PYTHON or install py -3.
    exit /b 1
)
set "PY=%RIFTREADER_PYTHON%"

:FOUND
echo Starting RIFT input broker...
echo   Broker:  %BROKER%
echo   Python:  %PY%
echo   Endpoint: http://127.0.0.1:8769
echo.
echo Keep this window open while the AI needs game input.
echo Press Ctrl+C to stop.
echo.
%PY% "%BROKER%" %*
