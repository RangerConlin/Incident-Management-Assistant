; Inno Setup script for the SARApp (ICS Command Assistant) desktop client.
; Build the PyInstaller dist first: python -m PyInstaller packaging/SARApp.spec --noconfirm --distpath dist --workpath build/pyinstaller
; Then compile: "C:\Users\Brendan\AppData\Local\Programs\Inno Setup 6\ISCC.exe" packaging\SARApp.iss

#define MyAppName "SARApp"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Arcadia Command Solutions"
#define MyAppExeName "SARApp.exe"

[Setup]
AppId={{6F1B8C2E-6B2C-4E6A-9C1B-7B6D7E0E6F31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=SARApp-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\SARApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
