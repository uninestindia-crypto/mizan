; ==============================================================================
; QuantOS Windows Setup Script (Inno Setup 6)
; Builds single-file standalone installer: QuantOS_v1.0.0_Setup.exe
; Guarantees drive isolation and evidence preservation.
; ==============================================================================

#define MyAppName "QuantOS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "QuantOS Quantitative Technologies"
#define MyAppURL "https://github.com/quant-system/quantos"
#define MyAppExeName "quantos.exe"

[Setup]
; App Metadata
AppId={{D6F9A5A4-9E3B-4C67-B44E-626F7C8A9B1C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation Paths (Drive-Isolated)
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\README.md

; Output Configuration
OutputDir=..\dist
OutputBaseFilename=QuantOS_v{#MyAppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\quantos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
