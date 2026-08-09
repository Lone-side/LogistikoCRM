# ============================================================
#  LogistikoCRM - Έλεγχος υπάρχουσας τοπικής εγκατάστασης
#  ΔΕΝ σβήνει τίποτα - μόνο αναφορά + οδηγίες καθαρισμού.
#  Εκτελείται από το check_local_install.bat (διπλό κλικ).
# ============================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host " ============================================="
Write-Host "  LogistikoCRM - Έλεγχος τοπικής εγκατάστασης"
Write-Host " ============================================="
Write-Host ""

# --- 1. Python ---
Write-Host " [1] Python:"
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $ver = & python --version 2>&1
    Write-Host "     - $ver  ($($py.Source))"
} else {
    Write-Host "     - Δεν βρέθηκε python στο PATH."
}
Write-Host ""

# --- 2. Γνωστές τοποθεσίες εγκατάστασης ---
Write-Host " [2] Αναζήτηση φακέλων LogistikoCRM σε συνηθισμένες τοποθεσίες:"
$candidates = @(
    "$env:USERPROFILE\LogistikoCRM",
    "$env:USERPROFILE\Desktop\LogistikoCRM",
    "$env:USERPROFILE\Documents\LogistikoCRM",
    "$env:USERPROFILE\Downloads\LogistikoCRM",
    "C:\LogistikoCRM"
)
# Και ο φάκελος όπου βρίσκεται το ίδιο το script (../ από το scripts/)
$here = Split-Path -Parent $PSScriptRoot
if ($here) { $candidates += $here }

$found = @()
foreach ($dir in ($candidates | Select-Object -Unique)) {
    if ((Test-Path "$dir\manage.py") -and (Test-Path "$dir\webcrm")) {
        $found += $dir
        Write-Host "     [!] ΒΡΕΘΗΚΕ εγκατάσταση: $dir"
        $artifacts = @(
            @{Path="venv";                   Note="Python περιβάλλον"},
            @{Path="db.sqlite3";             Note="ΒΑΣΗ ΔΕΔΟΜΕΝΩΝ - πιθανά πραγματικά στοιχεία πελατών!"},
            @{Path="media";                  Note="ΑΡΧΕΙΑ ΠΕΛΑΤΩΝ - πιθανά πραγματικά έγγραφα!"},
            @{Path="staticfiles";            Note=""},
            @{Path="frontend\node_modules";  Note=""},
            @{Path="backups";                Note="αντίγραφα βάσης"}
        )
        foreach ($a in $artifacts) {
            $p = Join-Path $dir $a.Path
            if (Test-Path $p) {
                $size = ""
                try {
                    $bytes = (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue |
                              Measure-Object Length -Sum).Sum
                    if ($bytes) { $size = " [{0:N0} MB]" -f ($bytes / 1MB) }
                } catch { }
                $note = if ($a.Note) { "  <-- " + $a.Note } else { "" }
                Write-Host ("         - {0}{1}{2}" -f $a.Path, $size, $note)
            }
        }
    }
}
if ($found.Count -eq 0) {
    Write-Host "     - Δεν βρέθηκε εγκατάσταση στις συνηθισμένες τοποθεσίες."
    Write-Host "       Αν την είχες βάλει αλλού, ψάξε στην Εξερεύνηση για φάκελο"
    Write-Host "       που περιέχει manage.py και webcrm μαζί."
}
Write-Host ""

# --- 3. Τρέχουν servers στα ports 8000 / 5173; ---
Write-Host " [3] Ενεργές διεργασίες στα ports 8000 [Django] και 5173 [React]:"
$busy = $false
foreach ($port in 8000, 5173) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $busy = $true
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        Write-Host "     [!] Port $port σε χρήση από PID $($c.OwningProcess) ($($proc.ProcessName))"
    }
}
if (-not $busy) { Write-Host "     - Κανένας server δεν τρέχει τώρα." }
Write-Host ""

# --- 4. Οδηγίες καθαρισμού ---
Write-Host " ============================================="
Write-Host "  Πώς σβήνεις με ασφάλεια μια παλιά εγκατάσταση"
Write-Host " ============================================="
Write-Host ""
Write-Host "  ΠΡΟΣΟΧΗ: Τα db.sqlite3 και media\ μπορεί να περιέχουν ΠΡΑΓΜΑΤΙΚΑ"
Write-Host "  στοιχεία και έγγραφα πελατών. Πριν σβήσεις οτιδήποτε:"
Write-Host "    1. Αντέγραψε τα db.sqlite3 και τον φάκελο media\ σε ασφαλές"
Write-Host "       σημείο [π.χ. εξωτερικό δίσκο], εκτός αν είσαι σίγουρος ότι"
Write-Host "       ήταν μόνο δοκιμαστικά δεδομένα."
Write-Host "    2. Κλείσε τα ανοιχτά παράθυρα LogistikoCRM Backend/Frontend"
Write-Host "       [ή τερμάτισε τα PID του βήματος 3 από τη Διαχείριση Εργασιών]."
Write-Host "    3. Σβήσε ολόκληρο τον φάκελο της παλιάς εγκατάστασης από την"
Write-Host "       Εξερεύνηση. Δεν υπάρχουν άλλα ίχνη: η εγκατάσταση δεν"
Write-Host "       γράφει στο μητρώο ούτε σε Program Files."
Write-Host ""
Read-Host " Πάτησε Enter για κλείσιμο"
