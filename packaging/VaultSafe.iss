; Compile only through Construire.ps1 -Setup. User data is never in {app}.
#ifndef SourceRoot
  #error SourceRoot is required
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif

[Setup]
AppId={{F69E558B-20F6-4916-A5C7-08A579551889}
AppName=VaultSafe
AppVersion={#AppVersion}
AppPublisher=VaultSafe
DefaultDirName={localappdata}\Programs\VaultSafe
DefaultGroupName=VaultSafe
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
DisableProgramGroupPage=yes
LicenseFile={#SourceRoot}\LICENSE
InfoBeforeFile={#SourceRoot}\packaging\AVANT_INSTALLATION.txt
SetupIconFile={#SourceRoot}\assets\vaultsafe.ico
UninstallDisplayIcon={app}\_internal\assets\vaultsafe.ico
OutputDir={#SourceRoot}\release
OutputBaseFilename=VaultSafe-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
Uninstallable=yes
SignedUninstaller=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; Flags: unchecked
Name: "extensionguide"; Description: "Configurer l'extension Chrome / Edge"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\dist\VaultSafe\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VaultSafe"; Filename: "{app}\VaultSafe.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\assets\vaultsafe.ico"
Name: "{group}\Guide de l'extension"; Filename: "{app}\GUIDE_EXTENSION.txt"
Name: "{autodesktop}\VaultSafe"; Filename: "{app}\VaultSafe.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\assets\vaultsafe.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\GUIDE_EXTENSION.txt"; Description: "Lire le guide Chrome / Edge"; Flags: shellexec postinstall skipifsilent; Tasks: extensionguide
Filename: "{app}\VaultSafe.exe"; Description: "Ouvrir VaultSafe"; Flags: nowait postinstall skipifsilent

[Code]
var
  ExtensionFolderButton, CopyPathButton: TNewButton;

function OpenClipboard(Owner: LongWord): Boolean; external 'OpenClipboard@user32.dll stdcall';
function EmptyClipboard(): Boolean; external 'EmptyClipboard@user32.dll stdcall';
function CloseClipboard(): Boolean; external 'CloseClipboard@user32.dll stdcall';
function SetClipboardData(Format, Memory: LongWord): LongWord; external 'SetClipboardData@user32.dll stdcall';
function GlobalAlloc(Flags, Bytes: LongWord): LongWord; external 'GlobalAlloc@kernel32.dll stdcall';
function GlobalLock(Memory: LongWord): LongWord; external 'GlobalLock@kernel32.dll stdcall';
function GlobalUnlock(Memory: LongWord): Boolean; external 'GlobalUnlock@kernel32.dll stdcall';
function GlobalFree(Memory: LongWord): LongWord; external 'GlobalFree@kernel32.dll stdcall';
function CopyWideString(Destination: LongWord; Source: String): LongWord; external 'lstrcpyW@kernel32.dll stdcall';

function CopyPublicPath(Value: String): Boolean;
var Memory, Pointer: LongWord;
begin
  Result := False;
  Memory := GlobalAlloc(2, (Length(Value) + 1) * 2);
  if Memory = 0 then Exit;
  Pointer := GlobalLock(Memory);
  if Pointer <> 0 then begin
    CopyWideString(Pointer, Value);
    GlobalUnlock(Memory);
    if OpenClipboard(WizardForm.Handle) then begin
      try
        if EmptyClipboard() then Result := SetClipboardData(13, Memory) <> 0;
      finally
        CloseClipboard();
      end;
    end;
  end;
  if not Result then GlobalFree(Memory);
end;

procedure OpenExtensionFolder(Sender: TObject);
var ResultCode: Integer;
begin
  ShellExec('open', ExpandConstant('{app}\extension'), '', '', SW_SHOWNORMAL, ewNoWait, ResultCode);
end;

procedure CopyExtensionPath(Sender: TObject);
begin
  if CopyPublicPath(ExpandConstant('{app}\extension')) then
    CopyPathButton.Caption := 'Chemin copié'
  else
    CopyPathButton.Caption := 'Réessayer la copie';
end;

procedure InitializeWizard();
begin
  ExtensionFolderButton := TNewButton.Create(WizardForm);
  ExtensionFolderButton.Parent := WizardForm.FinishedPage;
  ExtensionFolderButton.SetBounds(0, ScaleY(185), ScaleX(180), ScaleY(27));
  ExtensionFolderButton.Caption := 'Ouvrir le dossier extension';
  ExtensionFolderButton.OnClick := @OpenExtensionFolder;
  ExtensionFolderButton.Visible := False;
  CopyPathButton := TNewButton.Create(WizardForm);
  CopyPathButton.Parent := WizardForm.FinishedPage;
  CopyPathButton.SetBounds(ScaleX(190), ScaleY(185), ScaleX(145), ScaleY(27));
  CopyPathButton.Caption := 'Copier le chemin';
  CopyPathButton.OnClick := @CopyExtensionPath;
  CopyPathButton.Visible := False;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then begin
    ExtensionFolderButton.Visible := WizardIsTaskSelected('extensionguide');
    CopyPathButton.Visible := WizardIsTaskSelected('extensionguide');
  end;
end;

// No UninstallDelete section: never recursively delete a user vault or exports.
