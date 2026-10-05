; ==============================================================================
; QuantOS Windows installer (Inno Setup 6.7+)
;
; Build with scripts\build-windows-installer.ps1 after the PyInstaller bundle exists in
; dist\quantos. Produces dist\QuantOS_v<version>_Setup.exe.
;
; What this gives the user, all native to Inno Setup:
;   - DPI-aware wizard that follows the Windows light/dark setting (windows11 style)
;   - Start menu entry, optional desktop shortcut on the *real* desktop (OneDrive-aware)
;   - Registration in Settings > Installed apps, with a real uninstaller
;   - Rollback if the install fails or is cancelled
;   - Asks to close QuantOS if it is running (Restart Manager)
;   - Silent install for IT: /VERYSILENT /SUPPRESSMSGBOXES /DIR="D:\QuantOS" /LOG="setup.log"
;
; The bundle holds two programs: quantos-studio.exe (the desktop app every shortcut opens)
; and quantos.exe (the command-line server). Runtime folders tmp\, data\ and logs\ live
; inside the install folder. data\ and logs\ are never removed by the uninstaller.
; ==============================================================================

#if Ver < EncodeVer(6, 7, 0)
  #error "Inno Setup 6.7 or newer is required (windows11 wizard style, dark mode)."
#endif

#define MyAppName "QuantOS"
#define MyAppPublisher "QuantOS Quantitative Technologies"
#define MyAppURL "https://github.com/quant-system/quantos"
#define MyAppExeName "quantos-studio.exe"

#ifndef SourceDir
  #define SourceDir AddBackslash(SourcePath) + "..\dist\quantos"
#endif
#define StudioExe SourceDir + "\" + MyAppExeName

#if !FileExists(StudioExe)
  #error "dist\quantos\quantos-studio.exe not found. Run scripts\build-windows-release.ps1 first."
#endif

; Version comes from the exe's own version resource, which comes from quant_system.__version__.
#ifndef MyAppVersion
  #define MyAppVersion GetFileProductVersion(StudioExe)
#endif
#define MyAppNumericVersion GetVersionNumbersString(StudioExe)

[Setup]
AppId={{D6F9A5A4-9E3B-4C67-B44E-626F7C8A9B1C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright=Copyright (C) {#MyAppPublisher}

VersionInfoVersion={#MyAppNumericVersion}
VersionInfoProductVersion={#MyAppNumericVersion}
VersionInfoProductTextVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoCopyright=Copyright (C) {#MyAppPublisher}

; Per-user install: no admin prompt. Default folder is chosen in [Code] below.
PrivilegesRequired=lowest
DefaultDirName={code:DefaultInstallDir}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; Look and feel
WizardStyle=modern dynamic windows11
SetupIconFile=assets\quantos.ico
WizardImageFile=assets\wizard-large-164.png,assets\wizard-large-410.png
WizardSmallImageFile=assets\wizard-small-55.png,assets\wizard-small-69.png,assets\wizard-small-83.png,assets\wizard-small-110.png
UninstallDisplayIcon={app}\assets\quantos.ico
UninstallDisplayName={#MyAppName}

; Behaviour
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

; Output
OutputDir=..\dist
OutputBaseFilename=QuantOS_v{#MyAppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes

; Optional Authenticode signing: build-windows-installer.ps1 -SignCommand "<signtool ...> $f"
#ifdef SignToolName
SignTool={#SignToolName}
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Leftovers from the old hand-made setup wizard: its batch uninstaller would delete this
; install without unregistering it, and its shortcut used a different name.
Type: files; Name: "{app}\uninstall.bat"
Type: files; Name: "{autodesktop}\QuantOS Studio.lnk"
Type: files; Name: "{%USERPROFILE}\Desktop\QuantOS Studio.lnk"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\shariah\*"; DestDir: "{app}\data\shariah"; Flags: ignoreversion onlyifdoesntexist recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\data"; Flags: uninsneveruninstall
Name: "{app}\logs"; Flags: uninsneveruninstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\quantos.ico"; IconIndex: 0; AppUserModelID: "QuantOS.Desktop.Studio.2.0"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\assets\quantos.ico"; IconIndex: 0; AppUserModelID: "QuantOS.Desktop.Studio.2.0"

[Run]
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Caches only. data\ and logs\ (research data and evidence) are kept.
Type: filesandordirs; Name: "{app}\tmp"

[Code]
const
  DRIVE_FIXED = 3;
  MinFreeBytes = 2147483648; { 2 GB: room for market-data caches to grow }

function GetDriveType(lpRootPathName: String): Cardinal;
  external 'GetDriveTypeW@kernel32.dll stdcall';

function CanCreateFolderIn(const Root: String): Boolean;
var
  Probe: String;
begin
  Probe := Root + '.quantos-setup-probe';
  Result := CreateDir(Probe);
  if Result then
    RemoveDir(Probe);
end;

{ Keep QuantOS and its growing data off the system drive when the PC has another
  internal drive with room; otherwise use the standard per-user Programs folder.
  USB sticks, card readers and network drives are never chosen. }
function DefaultInstallDir(Param: String): String;
var
  I: Integer;
  Root, SystemDrive: String;
  FreeBytes, TotalBytes: Int64;
begin
  Result := ExpandConstant('{autopf}\{#MyAppName}');
  SystemDrive := Uppercase(ExtractFileDrive(ExpandConstant('{win}')));
  for I := Ord('D') to Ord('Z') do
  begin
    Root := Chr(I) + ':\';
    if (Chr(I) + ':' <> SystemDrive) and (GetDriveType(Root) = DRIVE_FIXED) and
       GetSpaceOnDisk64(Root, FreeBytes, TotalBytes) and (FreeBytes >= MinFreeBytes) and
       CanCreateFolderIn(Root) then
    begin
      Result := Root + '{#MyAppName}';
      Exit;
    end;
  end;
end;
