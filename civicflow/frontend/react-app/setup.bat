@echo off
echo ========================================
echo CivicFlow - React Conversion Setup
echo ========================================
echo.

cd /d "%~dp0"

echo [Step 1/5] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found!
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)
echo ✓ Node.js found

echo.
echo [Step 2/5] Installing dependencies...
if not exist "node_modules\" (
    call npm install
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
) else (
    echo ✓ Dependencies already installed
)

echo.
echo [Step 3/5] Copying CSS styles...
copy /Y ..\..\css\styles.css src\App.css >nul
echo ✓ CSS copied

echo.
echo [Step 4/5] Creating component files from COMPONENTS_GUIDE.md...
echo Please manually copy the component code from COMPONENTS_GUIDE.md
echo into the following files in src/components/:
echo.
echo   - Dashboard.jsx
echo   - FormSearch.jsx
echo   - FormReview.jsx
echo   - ExecutionView.jsx
echo   - ProfileSetup.jsx
echo   - SessionDetail.jsx
echo   - FloatingCounsellor.jsx
echo.
echo Or run this PowerShell command to auto-extract:
echo   Get-Content COMPONENTS_GUIDE.md | Select-String -Pattern "### [0-9]" -Context 0,999
echo.

echo [Step 5/5] Setup Complete!
echo.
echo ========================================
echo Quick Start:
echo ========================================
echo 1. Make sure backend is running on port 8000
echo 2. Run: npm run dev
echo 3. Open: http://localhost:3000
echo ========================================
echo.

pause
