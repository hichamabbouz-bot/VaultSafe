# Construit une seule version Windows, sans données personnelles.
[CmdletBinding()]
param([switch]$Setup, [string]$CompilateurInno = '', [switch]$SansInstallationDependances)
$ErrorActionPreference = 'Stop'
Remove-Item Env:PYTHONHOME,Env:PYTHONPATH,Env:TCL_LIBRARY,Env:TK_LIBRARY -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE = '1'
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Lanceur = Get-Command py -ErrorAction SilentlyContinue
    if ($null -eq $Lanceur) { throw 'Python 3.13 est nécessaire pour construire VaultSafe.' }
    & $Lanceur.Source -3.13 -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Création de .venv impossible.' }
}
$Dist = Join-Path $PSScriptRoot 'dist'
$Application = Join-Path $Dist 'VaultSafe'
function Verifier-CheminProjet([string]$Chemin) {
    $Complet = [IO.Path]::GetFullPath($Chemin)
    $Prefixe = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
    if (-not $Complet.StartsWith($Prefixe, [StringComparison]::OrdinalIgnoreCase)) { throw 'Chemin hors du projet.' }
    if ((Test-Path -LiteralPath $Complet) -and ((Get-Item -LiteralPath $Complet -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Un lien de dossier empêche le remplacement sûr.' }
}
function Verifier-Livraison([string]$Dossier) {
    Verifier-CheminProjet $Dossier
    if (-not (Test-Path -LiteralPath $Dossier)) { return }
    $Inattendus = @(Get-ChildItem -LiteralPath $Dossier -Force | Where-Object Name -notin @('VaultSafe.exe','_internal','extension','BUILDINFO.json','LICENSE','THIRD_PARTY_NOTICES.md','GUIDE_EXTENSION.txt'))
    $Personnels = @(Get-ChildItem -LiteralPath $Dossier -Recurse -File -Force | Where-Object { $_.Extension -in @('.db','.sqlite','.sqlite3','.vaultsafe','.csv') })
    $Liens = @(Get-ChildItem -LiteralPath $Dossier -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
    $Executables = @(Get-ChildItem -LiteralPath $Dossier -Recurse -File -Filter '*.exe')
    if ($Inattendus.Count -or $Personnels.Count -or $Liens.Count -or $Executables.Count -ne 1 -or $Executables[0].Name -ne 'VaultSafe.exe') { throw 'Le dossier de livraison contient des fichiers inattendus. Déplacez-les avant de reconstruire.' }
}
Verifier-CheminProjet $Dist
Verifier-Livraison $Application
$Travail = Join-Path $PSScriptRoot ('build\livraison-' + [Guid]::NewGuid().ToString('N'))
$Sortie = Join-Path $Travail 'sortie'
$Preparee = Join-Path $Sortie 'VaultSafe'
$Precedente = Join-Path $Travail 'precedente'
Verifier-CheminProjet $Travail
$Build = Join-Path $PSScriptRoot 'build'
Verifier-CheminProjet $Build
$ActualisationIcones = $null
$CheminRaccourci = Join-Path $PSScriptRoot 'VaultSafe Developpement.lnk'
Push-Location $PSScriptRoot
try {
    if (-not $SansInstallationDependances) {
        & $Python -B -m pip install --disable-pip-version-check -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw 'Installation des dépendances impossible.' }
    }
    & $Python -B tools\verifier_livraison.py --source $PSScriptRoot
    if ($LASTEXITCODE -ne 0) { throw 'Sources, version ou ressources incohérentes.' }
    $Icone = Join-Path $PSScriptRoot 'assets\vaultsafe.ico'
    $Ressources = Join-Path $PSScriptRoot 'assets' 
    $VersionWindows = Join-Path $Travail 'version-windows.txt'
    & $Python -B tools\verifier_livraison.py --source $PSScriptRoot --version-windows $VersionWindows
    if ($LASTEXITCODE -ne 0) { throw 'Génération de la version Windows impossible.' }
    $LicencePython = & $Python -B -c "import pathlib, sys; print(pathlib.Path(sys.base_prefix) / 'LICENSE.txt')"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $LicencePython)) { throw 'Licence du runtime Python absente.' }
    & $Python -B -m PyInstaller --noconfirm --onedir --windowed --name VaultSafe --icon $Icone --version-file $VersionWindows --exclude-module tkinter --exclude-module customtkinter --exclude-module pystray --exclude-module PIL --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml --exclude-module PySide6.QtNetwork --copy-metadata PySide6-Essentials --copy-metadata shiboken6 --copy-metadata cryptography --copy-metadata zxcvbn --copy-metadata cffi --copy-metadata pycparser --add-data "$Ressources;assets" --add-data "$LicencePython;licences/Python" --distpath $Sortie --workpath (Join-Path $Travail 'intermediaires') --specpath $Travail main.py
    if ($LASTEXITCODE -ne 0) { throw "Création de l'exécutable impossible." }
    if (-not (Test-Path -LiteralPath (Join-Path $Preparee 'VaultSafe.exe'))) { throw 'Exécutable absent après construction.' }
    # Qt utilise l'ABI ICU de Windows. Une ICU tierce trouvée dans PATH par
    # PyInstaller expose des symboles suffixés et empêcherait QtCore de charger.
    $VerifierIcu = @'
import ctypes, os, pathlib, pefile, sys
r = pathlib.Path(sys.argv[1]) / '_internal'
qt = pefile.PE(str(r / 'PySide6' / 'Qt6Core.dll'))
icu = ctypes.WinDLL(str(pathlib.Path(os.environ['SYSTEMROOT']) / 'System32' / 'icuuc.dll'))
for dependance in qt.DIRECTORY_ENTRY_IMPORT:
    if dependance.dll.lower() == b'icuuc.dll':
        for symbole in dependance.imports:
            if symbole.name:
                getattr(icu, symbole.name.decode('ascii'))
for fichier in [r / 'icuuc.dll', *r.glob('icudt*.dll')]:
    fichier.unlink(missing_ok=True)
print('ICU Windows compatible avec Qt.')
'@
    & $Python -B -c $VerifierIcu $Preparee
    if ($LASTEXITCODE -ne 0) { throw 'La version ICU de Windows est incompatible avec Qt.' }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'extension') -Destination $Preparee -Recurse
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'LICENSE'),(Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.md'),(Join-Path $PSScriptRoot 'packaging\GUIDE_EXTENSION.txt') -Destination $Preparee
    Verifier-Livraison $Preparee
    & $Python -B tools\verifier_livraison.py --source $PSScriptRoot --livraison $Preparee
    if ($LASTEXITCODE -ne 0) { throw 'La livraison de validation est incohérente.' }
    # Remplacer le programme seulement après une construction réussie.
    Verifier-Livraison $Application
    $ExecutablesActifs = @(Get-Process -Name VaultSafe -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $Application 'VaultSafe.exe') })
    if ($ExecutablesActifs.Count) { throw 'Fermez VaultSafe avant de remplacer la livraison. Les sources sont prêtes et la livraison existante est conservée.' }
    Verifier-CheminProjet $Precedente
    # Garder la clé du gestionnaire Shell et SYSICONINDEX de l'ancienne icône.
    # Le helper reste dans le même processus COM pendant le remplacement.
    try {
        $DemarrageIcones = New-Object System.Diagnostics.ProcessStartInfo
        $DemarrageIcones.FileName = $Python
        $HelperIcones = Join-Path $PSScriptRoot 'vaultsafe\windows_icones.py'
        $DemarrageIcones.Arguments = '-B "' + $HelperIcones + '" "' + (Join-Path $Application 'VaultSafe.exe') + '" "' + $CheminRaccourci + '"'
        $DemarrageIcones.UseShellExecute = $false
        $DemarrageIcones.CreateNoWindow = $true
        $DemarrageIcones.RedirectStandardInput = $true
        $DemarrageIcones.RedirectStandardOutput = $true
        $DemarrageIcones.RedirectStandardError = $true
        $ActualisationIcones = New-Object System.Diagnostics.Process
        $ActualisationIcones.StartInfo = $DemarrageIcones
        if (-not $ActualisationIcones.Start()) { throw "Le helper d'icônes ne démarre pas." }
        $ErreursIcones = $ActualisationIcones.StandardError.ReadToEndAsync()
        $LectureIcones = $ActualisationIcones.StandardOutput.ReadLineAsync()
        if (-not $LectureIcones.Wait(15000)) { throw "Le gestionnaire d'icônes ne répond pas." }
        $EtatIcones = $LectureIcones.Result | ConvertFrom-Json
        if ($EtatIcones.etat -ne 'PRET') { throw "La capture des références d'icônes a échoué." }
        if ($EtatIcones.erreurs.Count) { Write-Warning ($EtatIcones.erreurs -join ' ') }
    } catch {
        Write-Warning "L'actualisation ciblée des icônes n'a pas pu être préparée : $_"
        if ($null -ne $ActualisationIcones) {
            try { if (-not $ActualisationIcones.HasExited) { $ActualisationIcones.Kill(); $ActualisationIcones.WaitForExit() } } catch { }
            $ActualisationIcones.Dispose()
            $ActualisationIcones = $null
        }
    }
    if (Test-Path -LiteralPath $Application) {
        $Archives = Join-Path $PSScriptRoot 'archives'
        Verifier-CheminProjet $Archives
        New-Item -ItemType Directory -Path $Archives -Force | Out-Null
        Compress-Archive -LiteralPath $Application -DestinationPath (Join-Path $Archives ('livraison-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '.zip'))
        Move-Item -LiteralPath $Application -Destination $Precedente
    }
    New-Item -ItemType Directory -Path $Dist -Force | Out-Null
    try { Move-Item -LiteralPath $Preparee -Destination $Application }
    catch {
        if ((Test-Path -LiteralPath $Precedente) -and -not (Test-Path -LiteralPath $Application)) { Move-Item -LiteralPath $Precedente -Destination $Application }
        throw
    }
    # Le raccourci doit référencer l'ICO livré : Explorer peut garder l'ancienne image d'un EXE remplacé.
    if (Test-Path -LiteralPath $CheminRaccourci) {
        $ShellRaccourci = New-Object -ComObject WScript.Shell
        $Raccourci = $ShellRaccourci.CreateShortcut($CheminRaccourci)
        if ($Raccourci.TargetPath -eq (Join-Path $Application 'VaultSafe.exe')) {
            $Raccourci.IconLocation = (Join-Path $Application '_internal\assets\vaultsafe.ico') + ',0'
            $Raccourci.Save()
        }
    }
    if ($null -ne $ActualisationIcones) {
        try {
            $ActualisationIcones.StandardInput.WriteLine('ACTUALISER')
            $ActualisationIcones.StandardInput.Close()
            $ResultatIcones = $ActualisationIcones.StandardOutput.ReadToEndAsync()
            if (-not $ActualisationIcones.WaitForExit(15000)) { throw "L'actualisation des icônes a dépassé son délai." }
            if ($ActualisationIcones.ExitCode -ne 0) { throw $ErreursIcones.Result }
            $EtatFinalIcones = $ResultatIcones.Result | ConvertFrom-Json
            if ($EtatFinalIcones.etat -ne 'ACTUALISE') { throw "Le gestionnaire d'icônes n'a pas confirmé l'actualisation." }
            Write-Host "Icônes Signature actualisées dans Explorer."
        } catch { Write-Warning "L'actualisation ciblée des icônes n'a pas abouti : $_" }
    }
    Write-Host "Programme prêt : $Application\VaultSafe.exe"
    if ($Setup) {
        if (-not $CompilateurInno) {
            $InnoCommande = Get-Command ISCC.exe -ErrorAction SilentlyContinue
            if ($null -ne $InnoCommande) { $CompilateurInno = $InnoCommande.Source }
            elseif (Test-Path -LiteralPath 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe') { $CompilateurInno = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' }
            else { throw 'Installez Inno Setup 6.7.3 et indiquez -CompilateurInno chemin\ISCC.exe. La construction est conservée.' }
        }
        $VersionApp = & $Python -B tools\verifier_livraison.py --source $PSScriptRoot --version
        & $CompilateurInno /Q ('/DSourceRoot=' + $PSScriptRoot) ('/DAppVersion=' + $VersionApp.Trim()) (Join-Path $PSScriptRoot 'packaging\VaultSafe.iss')
        if ($LASTEXITCODE -ne 0) { throw 'Compilation du setup impossible. La livraison est conservée.' }
        $SetupPath = Join-Path $PSScriptRoot ('release\VaultSafe-Setup-' + $VersionApp.Trim() + '-x64.exe')
        $Hash = (Get-FileHash -LiteralPath $SetupPath -Algorithm SHA256).Hash.ToLowerInvariant()
        [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'release\SHA256SUMS.txt'), $Hash + '  ' + [IO.Path]::GetFileName($SetupPath) + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host "Installateur prêt (non signé) : $SetupPath"
    }
} finally {
    if ($null -ne $ActualisationIcones) {
        if (-not $ActualisationIcones.HasExited) {
            try { $ActualisationIcones.StandardInput.WriteLine('ANNULER'); $ActualisationIcones.StandardInput.Close() } catch { }
            if (-not $ActualisationIcones.WaitForExit(3000)) { $ActualisationIcones.Kill(); $ActualisationIcones.WaitForExit() }
        }
        $ActualisationIcones.Dispose()
    }
    Pop-Location
    Verifier-CheminProjet $Travail
    if (Test-Path -LiteralPath $Travail) { Remove-Item -LiteralPath $Travail -Recurse -Force }
    if ((Test-Path -LiteralPath $Build) -and @(Get-ChildItem -LiteralPath $Build -Force).Count -eq 0) { Remove-Item -LiteralPath $Build }
}
