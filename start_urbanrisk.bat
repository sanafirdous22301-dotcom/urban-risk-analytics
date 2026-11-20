@echo off
title URBANRISK - Integrated Urban Risk Analytics Platform
cls
echo ======================================================================
echo  URBANRISK -- Integrated Urban Risk Analytics & Resource Prioritization
echo  Local Offline Demonstration Launcher (Hyderabad, Telangana)
echo ======================================================================
echo.

:: 1. Check if MongoDB is already active
echo [1/3] Verifying local MongoDB service (port 27017)...
netstat -ano | findstr ":27017" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo       MongoDB is active and listening on port 27017.
) else (
    echo       MongoDB not detected on port 27017. Attempting to start Windows service...
    net start MongoDB >nul 2>&1
    if %errorlevel% equ 0 (
        echo       MongoDB Windows service started successfully.
    ) else (
        echo       [NOTICE] Could not start MongoDB service automatically.
        echo       Ensure MongoDB is installed and running on port 27017.
    )
)

:: 2. Launch default web browser
echo.
echo [2/3] Opening Urban Risk Analytics Dashboard in your web browser...
start "" http://127.0.0.1:8000/app

:: 3. Start FastAPI application server
echo.
echo [3/3] Starting FastAPI application server (port 8000)...
echo       Application URL: http://127.0.0.1:8000/app
echo       API Docs:        http://127.0.0.1:8000/docs
echo.
echo ======================================================================
echo  Server is active. Press Ctrl+C in this window to stop the application.
echo ======================================================================
python scripts\serve_ml.py
pause
