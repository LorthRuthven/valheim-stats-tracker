@echo off
cd /d "%~dp0"
rem Lance la nouvelle interface Windows si l'archive Qt a ete decompressee ici.
if exist "%~dp0ValheimStatsTracker\ValheimStatsTracker.exe" (
  start "" "%~dp0ValheimStatsTracker\ValheimStatsTracker.exe"
  exit /b 0
)
if exist "%~dp0ValheimStatsTracker.exe" (
  start "" "%~dp0ValheimStatsTracker.exe"
  exit /b 0
)
rem Compatibilite totale avec l'installation historique Python.
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 app.py
) else (
  python app.py
)
if errorlevel 1 pause
