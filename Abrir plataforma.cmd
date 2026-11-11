@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python plataforma.py --abrir
) else (
    py -3 plataforma.py --abrir
)
if errorlevel 1 pause
