@echo off
REM Πλήρης αρχική εγκατάσταση LogistikoCRM για development (Windows)
REM Χρήση: setup_dev.bat
REM Μετά την ολοκλήρωση: venv\Scripts\activate ^&^& python manage.py runserver
chcp 65001 >nul
setlocal

echo 🚀 Αρχική εγκατάσταση LogistikoCRM
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REM 1. Έλεγχος Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Δεν βρέθηκε Python. Εγκατέστησε Python 3.10+ από https://www.python.org/downloads/
    echo    ^(τσέκαρε το "Add Python to PATH" στην εγκατάσταση^)
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo ✅ %%v

REM 2. Virtual environment
if not exist "venv" (
    echo 📦 Δημιουργία virtual environment...
    python -m venv venv
    if errorlevel 1 exit /b 1
)
call venv\Scripts\activate
echo ✅ Virtual environment ενεργό

REM 3. Dependencies
echo 📦 Εγκατάσταση dependencies ^(μπορεί να πάρει λίγα λεπτά^)...
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo ❌ Η εγκατάσταση dependencies απέτυχε.
    exit /b 1
)
echo ✅ Dependencies εγκαταστάθηκαν

REM 4. .env από το σωστό template
if not exist ".env" (
    if exist ".env.development" (
        copy /y .env.development .env >nul
        echo ✅ Δημιουργήθηκε .env από το .env.development
    ) else (
        echo ⚠️  Δεν βρέθηκε .env.development — συνέχεια χωρίς .env
    )
) else (
    echo ✅ Το .env υπάρχει ήδη
)

REM 5. Βάση δεδομένων — Η ΣΕΙΡΑ ΕΧΕΙ ΣΗΜΑΣΙΑ (migrate → createcachetable → setupdata)
echo 🗄️  Εκτέλεση migrations...
python manage.py migrate
if errorlevel 1 exit /b 1

echo 🗄️  Δημιουργία cache table...
python manage.py createcachetable
if errorlevel 1 exit /b 1

REM Το setupdata φτιάχνει groups/fixtures + superuser IamSUPER.
REM ΠΡΟΣΟΧΗ: όχι createsuperuser πριν από αυτό — χαλάει τα pk των groups.
echo 👤 Αρχικοποίηση δεδομένων ^(groups + superuser IamSUPER^)...
echo ⚠️  ΣΗΜΕΙΩΣΕ τον κωδικό ^(PASSWORD^) που θα εμφανιστεί παρακάτω!
python manage.py setupdata
if errorlevel 1 exit /b 1

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ✅ Η εγκατάσταση ολοκληρώθηκε!
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo Εκκίνηση server:
echo    venv\Scripts\activate
echo    python manage.py runserver
echo.
echo URLs:
echo    • Admin: http://localhost:8000/el/456-admin/
echo    • CRM:   http://localhost:8000/el/123/
echo.
echo Σύνδεση: χρήστης IamSUPER ^(ο κωδικός τυπώθηκε παραπάνω στα SUPERUSER Credentials^)

endlocal
