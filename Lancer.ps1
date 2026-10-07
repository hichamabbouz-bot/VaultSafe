param([switch]$Developpement)
$ErrorActionPreference = "Stop"

Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Environnement Python absent. Lancez d'abord .\Construire.ps1 pour le creer et installer les dependances."
}

Remove-Item Env:TCL_LIBRARY,Env:TK_LIBRARY -ErrorAction SilentlyContinue

Push-Location $PSScriptRoot
try {
    if ($Developpement) { & $Python -B 'main.py' --developpement }
    else { & $Python -B 'main.py' }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
