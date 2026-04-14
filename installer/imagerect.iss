; ImageRect Inno Setup Script
; Requires: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

#define MyAppName "ImageRect"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "Andre Stiebitz"
#define MyAppURL "https://github.com/andremadstop/imagerect"
#define MyAppExeName "ImageRect.exe"

[Setup]
AppId={{B8A7E3F1-4C2D-4E5F-9A1B-6D8C0F3E2A7B}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=ImageRect-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\ImageRect.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\ImageRect-cli.exe"; DestDir: "{app}"; Flags: ignoreversion
; If --onedir mode is used instead of --onefile, use:
; Source: "..\dist\ImageRect\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
