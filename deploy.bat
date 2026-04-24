@echo off
setlocal enabledelayedexpansion
echo =========================================
echo Deploying Golden Plate Recorder Locally
echo =========================================

REM Change to the directory where the script is located
cd /d "%~dp0"

REM Handle the case where the script is placed right next to the folder instead of inside it
if not exist "requirements.txt" (
    if exist "goldenplatewebsite\requirements.txt" (
        echo Found project folder next to script. Navigating into 'goldenplatewebsite'...
        cd goldenplatewebsite
    ) else (
        echo ERROR: Cannot find requirements.txt or the goldenplatewebsite folder. 
        echo Please ensure this script is either inside the project folder or directly next to it.
        pause
        exit /b 1
    )
)

echo.
echo [1/7] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    echo Attempting to install Python via winget...
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    if !errorlevel! neq 0 (
        echo Failed to install Python. Please install it manually from https://www.python.org/
        pause
        exit /b 1
    )
    echo ====================================================================
    echo Python installed! 
    echo PLEASE CLOSE THIS TERMINAL AND RUN deploy.bat AGAIN to update PATH.
    echo ====================================================================
    pause
    exit /b 0
) else (
    echo Python is installed.
)

echo.
echo [2/7] Checking for Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Node.js is not installed or not in PATH.
    echo Attempting to install Node.js via winget...
    winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements
    if !errorlevel! neq 0 (
        echo Failed to install Node.js. Please install it manually from https://nodejs.org/
        pause
        exit /b 1
    )
    echo ====================================================================
    echo Node.js installed! 
    echo PLEASE CLOSE THIS TERMINAL AND RUN deploy.bat AGAIN to update PATH.
    echo ====================================================================
    pause
    exit /b 0
) else (
    echo Node.js is installed.
)

echo.
echo [3/7] Setting up Python Virtual Environment...
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Python dependencies...
REM It is safe and fast to run pip install every time, which prevents broken states if a previous install failed.
pip install -r requirements.txt

echo.
echo [4/7] Setting up Frontend Dependencies...
if not exist "frontend" (
    echo ERROR: Cannot find 'frontend' folder.
    pause
    exit /b 1
)

REM Use pushd/popd to ensure we always return to the correct folder even if a command fails
pushd frontend
echo Installing frontend dependencies...
REM It is safe to run npm install every time; this repairs partial node_modules folders after interrupted installs or cleanup.
call npm install --legacy-peer-deps

echo.
echo [5/7] Building Frontend...
call npm run build
popd

echo.
echo [6/7] Verifying Frontend Build Output...
if exist "src\static\index.html" (
    echo Frontend build emitted successfully into src\static.
) else (
    echo ERROR: Frontend build output was not generated in src\static.
    pause
    exit /b 1
)

echo.
echo [7/7] Starting the Application...
echo The application will be running at http://127.0.0.1:5000 (default Flask port)
echo Press Ctrl+C to stop the server.
echo.
python src\main.py

pause
