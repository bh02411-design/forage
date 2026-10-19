#ifndef PayloadDir
  #error PayloadDir must identify the clean staged installation
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif

[Setup]
AppId={{5193D786-288A-4A58-A297-AE1F98BF6E9F}
AppName=Forage
AppVersion={#AppVersion}
AppPublisher=Forage
AppPublisherURL=https://github.com/bh02411-design/forage
DefaultDirName={localappdata}\Programs\Forage
DefaultGroupName=Forage
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
DisableDirPage=yes
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
SetupIconFile={#PayloadDir}\Forage.ico
UninstallDisplayIcon={app}\Forage.ico
OutputDir=..\dist
OutputBaseFilename=Forage-Setup
CloseApplications=no
InfoAfterFile={#PayloadDir}\Getting-started.txt

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: checkedonce

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Forage"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"" --tray --open --data-dir ""{localappdata}\Forage\data"""; WorkingDir: "{app}"; IconFilename: "{app}\Forage.ico"
Name: "{userdesktop}\Forage"; Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"" --tray --open --data-dir ""{localappdata}\Forage\data"""; WorkingDir: "{app}"; IconFilename: "{app}\Forage.ico"; Tasks: desktopicon
Name: "{userprograms}\Forage - Getting started"; Filename: "{app}\Getting-started.txt"

[Run]
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\launcher.py"" --tray --open --data-dir ""{localappdata}\Forage\data"""; Description: "Open Forage"; Flags: nowait postinstall skipifsilent

; Workspace files live outside {app}. Never delete user data on uninstall.
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "ForageLocalDeckBuilder"; Flags: uninsdeletevalue
