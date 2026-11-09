; Inno Setup script - turns dist\HazeAudio into a normal Windows installer (Setup.exe)
#define AppName "HazeAudio"
#define AppVersion "1.2.0"

[Setup]
AppId={{B7C2D1A4-5E3F-4A9B-8C21-6D4F0A1E9B73}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\HazeAudio
DefaultGroupName={#AppName}
OutputDir=installer
OutputBaseFilename=HazeAudio-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\HazeAudio.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\HazeAudio\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\HazeAudio.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\HazeAudio.exe"; Tasks: desktopicon

; Makes "Open with > HazeAudio" appear for common audio files
[Registry]
Root: HKA; Subkey: "Software\Classes\Applications\HazeAudio.exe\shell\open\command"; ValueType: string; ValueData: """{app}\HazeAudio.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithList\HazeAudio.exe"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithList\HazeAudio.exe"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithList\HazeAudio.exe"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithList\HazeAudio.exe"; ValueType: none; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithList\HazeAudio.exe"; ValueType: none; Flags: uninsdeletekey

[Run]
Filename: "{app}\HazeAudio.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
