; Inno Setup Script for Atena Battery (.NET 11)
; 1. First publish the app:
;    dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
; 2. Place this file in the AtenaBattery project folder (next to AtenaBattery.csproj and app_icon.ico)
; 3. Compile with Inno Setup Compiler (6.x+)

#define MyAppName "Atena Battery"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "White-Wolf-dv"
#define MyAppURL "https://github.com/White-Wolf-dv/Atena-Battery"
#define MyAppExeName "AtenaBattery.exe"
#define PublishDir "bin\Release\net11.0-windows\win-x64\publish"

[Setup]
AppId={{471B611F-7D26-45E8-8031-A11F928C2BFD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Per-user install by default (no admin required), with option to install for all users
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Target Windows 10/11 64-bit
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; Output settings
OutputDir=installer_output
OutputBaseFilename=AtenaBattery-Setup-{#MyAppVersion}
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Maximum compression & modern wizard UI
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Automatically detect and close running widget during install/upgrade/uninstall
AppMutex=Global\AtenaBattery_SingleInstance_Mutex
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start {#MyAppName} automatically with Windows"; GroupDescription: "Startup:"

[Files]
Source: "{#PublishDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PublishDir}\*"; DestDir: "{app}"; Excludes: "*.pdb"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Synced with AppName ("BluetoothBatteryOverlay") in MainWindow.xaml.cs
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "BluetoothBatteryOverlay"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue

[UninstallDelete]
; Clean up saved widget configuration on uninstall
Type: filesandordirs; Name: "{userappdata}\BluetoothBattery"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
