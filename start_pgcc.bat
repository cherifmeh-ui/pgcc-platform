@echo off
echo ==========================================
echo DEMARRAGE PLATEFORME PGCC
echo ==========================================

REM 1. Vérifier/Lancer Ollama
echo [1/3] Verification Ollama...
ollama list >nul 2>&1
if errorlevel 1 (
    echo Ollama non detecte. Veuillez lancer 'ollama serve' manuellement.
    pause
    exit /b
) else (
    echo Ollama OK.
)

REM 2. Lancer Docker
echo [2/3] Demarrage Docker Compose...
cd /d "%~dp0"
docker-compose up -d
timeout /t 5 /nobreak >nul

REM 3. Lancer Frontend (dans une nouvelle fenetre)
echo [3/3] Demarrage Frontend Vite...
start cmd /k "cd /d %~dp0frontend && npm run dev"

echo ==========================================
echo SYSTEME PRET !
echo Backend: http://localhost:8000/docs
echo Frontend: http://localhost:5173
echo ==========================================
pause