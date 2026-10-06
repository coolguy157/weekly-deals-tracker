@echo off
setlocal

:: Navigate to deals_tracker directory
cd /d "%~dp0"

:: Ensure logs directory exists
if not exist "logs" mkdir "logs"

set LOGFILE=%~dp0logs\giant_weekly_sync.log

:: Rotate log if larger than 5MB
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

echo ================================================================== >> "%LOGFILE%"
echo --- Starting Giant Lewisburg Weekly Deals Sync: %DATE% %TIME% --- >> "%LOGFILE%"
echo ================================================================== >> "%LOGFILE%"

:: Locate Python interpreter (prefer virtualenv with Playwright)
set PYTHON_EXE=py
if exist "%~dp0..\app_automation\.venv\Scripts\python.exe" (
    set PYTHON_EXE="%~dp0..\app_automation\.venv\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set PYTHON_EXE="%~dp0.venv\Scripts\python.exe"
)

:: 1. Sync Giant weekly ad and calculate BxGy prices into database
%PYTHON_EXE% -u -m src.cli sync --store giant >> "%LOGFILE%" 2>&1
set SYNC_CODE=%ERRORLEVEL%

if %SYNC_CODE% neq 0 (
    echo [ERROR] Giant sync failed with exit code %SYNC_CODE% >> "%LOGFILE%"
    exit /b %SYNC_CODE%
)

:: 2. Export latest evaluated deals to web/deals.json
%PYTHON_EXE% -u -m src.cli export --store giant --format json --output web/deals.json >> "%LOGFILE%" 2>&1

:: 3. Git commit and push if web/deals.json changed
git add web/deals.json src/giant_grid_fetcher.py src/cli.py >> "%LOGFILE%" 2>&1
git diff --staged --quiet
if errorlevel 1 (
    echo Staged changes detected in web/deals.json. Committing and pushing to main and gh-pages... >> "%LOGFILE%"
    git commit -m "chore(web): auto-update Giant Lewisburg deals with solved BxGy prices [skip ci]" >> "%LOGFILE%" 2>&1
    git push origin main >> "%LOGFILE%" 2>&1
    
    :: Push web folder directly to gh-pages branch for instant live web app update
    for /f "tokens=*" %%T in ('git subtree split --prefix web main') do set SUBTREE_HASH=%%T
    git push origin %SUBTREE_HASH%:gh-pages --force >> "%LOGFILE%" 2>&1
    echo Successfully pushed updated deals to main and gh-pages. >> "%LOGFILE%"
) else (
    echo web/deals.json is already up to date. No push needed. >> "%LOGFILE%"
)

echo --- Finished Giant Sync at %DATE% %TIME% --- >> "%LOGFILE%"
exit /b 0
