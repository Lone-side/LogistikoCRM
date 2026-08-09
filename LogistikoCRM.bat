@echo off
rem ============================================================
rem  LogistikoCRM Launcher - διπλό κλικ για εκκίνηση
rem  Ξεκινά backend (Django) + frontend (Vite) και ανοίγει browser
rem ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title LogistikoCRM

echo.
echo  ==============================
echo   LogistikoCRM - Εκκίνηση...
echo  ==============================
echo.

rem --- Έλεγχος virtual environment ---
if not exist "venv\Scripts\python.exe" (
    echo  [!] Δεν βρέθηκε το venv. Δημιουργία...
    python -m venv venv
    if errorlevel 1 (
        echo  [X] Αποτυχία: βεβαιώσου ότι η Python είναι εγκατεστημένη.
        pause
        exit /b 1
    )
    echo  [*] Εγκατάσταση dependencies ^(μία φορά, θα πάρει λίγα λεπτά^)...
    venv\Scripts\python.exe -m pip install -r requirements.txt
)

rem --- Ρυθμίσεις .env ---
if not exist ".env" (
    if exist ".env.development" (
        copy /y ".env.development" ".env" >nul
        echo  [*] Δημιουργήθηκε .env από το .env.development
    )
)

rem --- Migrations + αρχικό setup ---
rem Πρώτη εγκατάσταση (χωρίς βάση): μετά το migrate χρειάζονται
rem createcachetable (database cache) και setupdata (ρόλοι + superuser
rem IamSUPER) — ΜΕ ΑΥΤΗ τη σειρά, ποτέ createsuperuser πριν το setupdata.
set FIRST_RUN=0
if not exist "db.sqlite3" set FIRST_RUN=1
echo  [*] Έλεγχος βάσης δεδομένων...
venv\Scripts\python.exe manage.py migrate --no-input >nul 2>&1
if "%FIRST_RUN%"=="1" (
    echo  [*] Πρώτη εγκατάσταση: cache table + ρόλοι/χρήστης IamSUPER...
    venv\Scripts\python.exe manage.py createcachetable >nul 2>&1
    venv\Scripts\python.exe manage.py setupdata
)

rem --- Εκκίνηση Django backend σε νέο παράθυρο ---
echo  [*] Εκκίνηση backend ^(Django, port 8000^)...
start "LogistikoCRM Backend" cmd /k "chcp 65001 >nul && venv\Scripts\python.exe manage.py runserver 8000"

rem --- Εκκίνηση React frontend (αν υπάρχει εγκατεστημένο) ---
set FRONTEND_URL=http://localhost:8000/el/456-admin/
if exist "frontend\node_modules" (
    echo  [*] Εκκίνηση frontend ^(React, port 5173^)...
    start "LogistikoCRM Frontend" cmd /k "chcp 65001 >nul && cd frontend && npm run dev"
    set FRONTEND_URL=http://localhost:5173/
) else (
    if exist "frontend\package.json" (
        echo  [i] Το frontend δεν είναι εγκατεστημένο. Για το React UI τρέξε μία φορά:
        echo      cd frontend ^&^& npm install
        echo      Προς το παρόν θα ανοίξει το Django admin.
    )
)

rem --- Αναμονή να σηκωθεί ο server και άνοιγμα browser ---
echo  [*] Αναμονή εκκίνησης server...
timeout /t 6 /nobreak >nul
start "" "%FRONTEND_URL%"

echo.
echo  [OK] Το LogistikoCRM ξεκίνησε!
echo       Frontend/UI: %FRONTEND_URL%
echo       Admin:       http://localhost:8000/el/456-admin/
echo.
echo  Για τερματισμό: κλείσε τα παράθυρα "LogistikoCRM Backend/Frontend".
echo  Αυτό το παράθυρο μπορείς να το κλείσεις.
pause
