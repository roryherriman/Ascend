; Ascend Windows Installer — Inno Setup 6
; Build: scripts\build_installer.bat  (passes /DAppVersion=x.y.z on the CLI)
; Requires the portable build to exist at ..\dist\Ascend\ first.
;
; Installer technology decision:
;   Inno Setup 6 was chosen over WiX and NSIS for the initial release:
;   - Zero configuration required for basic installs under Program Files
;   - Built-in upgrade handling without MSI complexities
;   - Clean Add/Remove Programs integration
;   - Free, actively maintained, widely used for PySide6 / Qt Windows apps
;   WiX may be evaluated if enterprise deployment (GPO, MSI) is needed later.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "Ascend"
#define AppPublisher "Rory Herriman"
#define AppURL "https://github.com/roryherriman/Ascende"
#define AppExeName "Ascend.exe"
#define SourceDir "..\dist\Ascend"

[Setup]
AppId={{F4A2B3C1-7D8E-4F0A-B1C2-D3E4F5A6B7C8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Preserve user data across upgrades - never touch %LOCALAPPDATA%\Ascend
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=Output
OutputBaseFilename=Ascend-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
; Enable High-DPI awareness
DPIAware=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The entire portable build folder
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Do NOT include .env, *.db, logs/, exports/, or user data here.
; User data lives in {localappdata}\Ascend and is never touched by the installer.

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} (Demo Mode)"; Filename: "{app}\{#AppExeName}"; Parameters: "--demo"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Nothing — user data in %LOCALAPPDATA%\Ascend is intentionally preserved.
; Users can manually delete %LOCALAPPDATA%\Ascend if they want a full clean removal.

[Code]
// Warn on downgrade
function InitializeSetup(): Boolean;
var
  PrevVersion: String;
begin
  Result := True;
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{F4A2B3C1-7D8E-4F0A-B1C2-D3E4F5A6B7C8}_is1',
    'DisplayVersion', PrevVersion) then
  begin
    if CompareStr(PrevVersion, '{#AppVersion}') > 0 then
    begin
      if MsgBox('You are installing version {#AppVersion} over a newer version (' + PrevVersion + '). Continue?',
        mbConfirmation, MB_YESNO) = IDNO then
        Result := False;
    end;
  end;
end;

// Show user data location note at end of install
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedLabel.Caption :=
      'Ascend has been installed successfully.' + #13#10 + #13#10 +
      'Your raid analysis data is stored in:' + #13#10 +
      ExpandConstant('{localappdata}\Ascend\') + #13#10 + #13#10 +
      'This folder is never deleted by the uninstaller.' + #13#10 +
      'Use File → Back Up Ascend Data within the app to create backups.';
  end;
end;
