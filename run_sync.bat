@echo off
setlocal

:: Navigate to script directory
cd /d "%~dp0"

:: Ensure logs directory exists
if not exist "logs" mkdir "logs"

:: Define log file path
set LOGFILE=%~dp0logs\weekly_deals_task.log

:: Rotate weekly_deals_task.log if larger than 5MB
if exist "%LOGFILE%" (
    for %%I in ("%LOGFILE%") do (
        if %%~zI gtr 5242880 (
            if exist "%LOGFILE%.4" del "%LOGFILE%.5" 2>nul & move /y "%LOGFILE%.4" "%LOGFILE%.5" 2>nul
            if exist "%LOGFILE%.3" move /y "%LOGFILE%.3" "%LOGFILE%.4" 2>nul
            if exist "%LOGFILE%.2" move /y "%LOGFILE%.2" "%LOGFILE%.3" 2>nul
            if exist "%LOGFILE%.1" move /y "%LOGFILE%.1" "%LOGFILE%.2" 2>nul
            move /y "%LOGFILE%" "%LOGFILE%.1" 2>nul
        )
    )
)

echo --- Starting Tom Thumb Weekly Deals Sync: %DATE% %TIME% --- >> "%LOGFILE%"

:: Run Python CLI sync with unbuffered stdout (reads TRACKER_ZIP from local .env)
py -u -m src.cli sync >> "%LOGFILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

echo --- Finished with exit code: %EXIT_CODE% at %DATE% %TIME% --- >> "%LOGFILE%"

exit /b %EXIT_CODE%
