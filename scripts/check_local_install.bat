@echo off
rem ============================================================
rem  LogistikoCRM - Έλεγχος υπάρχουσας τοπικής εγκατάστασης
rem  ΔΕΝ σβήνει τίποτα - μόνο αναφορά + οδηγίες καθαρισμού.
rem  Διπλό κλικ ή: scripts\check_local_install.bat
rem ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion
title LogistikoCRM - Έλεγχος εγκατάστασης

echo.
echo  =============================================
echo   LogistikoCRM - Έλεγχος τοπικής εγκατάστασης
echo  =============================================
echo.

set FOUND=0

rem --- 1. Python ---
echo  [1] Python:
where python >nul 2>&1
if errorlevel 1 (
    echo      - Δεν βρέθηκε python στο PATH.
) else (
    for /f "delims=" %%v in ('python --version 2^>^&1') do echo      - %%v ^(where: ^)
    for /f "delims=" %%p in ('where python') do echo        %%p
)
echo.

rem --- 2. Γνωστές τοποθεσίες εγκατάστασης ---
echo  [2] Αναζήτηση φακέλων LogistikoCRM σε συνηθισμένες τοποθεσίες:
for %%D in (
    "%USERPROFILE%\LogistikoCRM"
    "%USERPROFILE%\Desktop\LogistikoCRM"
    "%USERPROFILE%\Documents\LogistikoCRM"
    "%USERPROFILE%\Downloads\LogistikoCRM"
    "C:\LogistikoCRM"
) do (
    if exist "%%~D\manage.py" (
        if exist "%%~D\webcrm" (
            set FOUND=1
            echo      [!] ΒΡΕΘΗΚΕ εγκατάσταση: %%~D
            if exist "%%~D\venv"                  echo          - venv\               ^(Python περιβάλλον^)
            if exist "%%~D\db.sqlite3"            echo          - db.sqlite3          ^(ΒΑΣΗ ΔΕΔΟΜΕΝΩΝ - πιθανά πραγματικά στοιχεία πελατών!^)
            if exist "%%~D\media"                 echo          - media\              ^(ΑΡΧΕΙΑ ΠΕΛΑΤΩΝ - πιθανά πραγματικά έγγραφα!^)
            if exist "%%~D\staticfiles"           echo          - staticfiles\
            if exist "%%~D\frontend\node_modules" echo          - frontend\node_modules\
            if exist "%%~D\backups"               echo          - backups\            ^(αντίγραφα βάσης^)
        )
    )
)
if "%FOUND%"=="0" echo      - Δεν βρέθηκε εγκατάσταση στις συνηθισμένες τοποθεσίες.
echo      ^(Αν την είχες βάλει αλλού, ψάξε στην Εξερεύνηση για φάκελο που
echo       περιέχει manage.py και webcrm μαζί.^)
echo.

rem --- 3. Τρέχουν servers στα ports 8000 / 5173; ---
echo  [3] Ενεργές διεργασίες στα ports 8000 ^(Django^) και 5173 ^(React^):
set PORTBUSY=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r ":8000 .*LISTENING"') do (
    set PORTBUSY=1
    echo      [!] Port 8000 σε χρήση από PID %%p
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r ":5173 .*LISTENING"') do (
    set PORTBUSY=1
    echo      [!] Port 5173 σε χρήση από PID %%p
)
if "%PORTBUSY%"=="0" echo      - Κανένας server δεν τρέχει τώρα.
echo.

rem --- 4. Οδηγίες καθαρισμού ---
echo  =============================================
echo   Πώς σβήνεις με ασφάλεια μια παλιά εγκατάσταση
echo  =============================================
echo.
echo   ΠΡΟΣΟΧΗ: Τα db.sqlite3 και media\ μπορεί να περιέχουν ΠΡΑΓΜΑΤΙΚΑ
echo   στοιχεία και έγγραφα πελατών. Πριν σβήσεις οτιδήποτε:
echo     1. Αντέγραψε τα db.sqlite3 και τον φάκελο media\ σε ασφαλές
echo        σημείο ^(π.χ. εξωτερικό δίσκο^), εκτός αν είσαι σίγουρος ότι
echo        ήταν μόνο δοκιμαστικά δεδομένα.
echo     2. Κλείσε τα ανοιχτά παράθυρα "LogistikoCRM Backend"/"Frontend"
echo        ^(ή τερμάτισε τα PID του βήματος [3] από τη Διαχείριση Εργασιών^).
echo     3. Σβήσε ολόκληρο τον φάκελο της παλιάς εγκατάστασης από την
echo        Εξερεύνηση ^(δεξί κλικ - Διαγραφή^). Δεν υπάρχουν άλλα ίχνη:
echo        η εγκατάσταση δεν γράφει στο μητρώο ούτε σε Program Files.
echo.
pause
