; TextGenius Installer (Inno Setup)
; Kein Admin nötig, installiert nach %LOCALAPPDATA%\TextGenius

#define MyAppName "TextGenius"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "TextGenius"
#define MyAppExeName "TextGenius.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Installiert nach %LOCALAPPDATA%\TextGenius (kein Admin nötig)
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=TextGenius-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Kein Admin nötig
PrivilegesRequired=lowest
; Kein UAC-Prompt
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Optionen:"
Name: "startmenu"; Description: "Startmenü-Eintrag erstellen"; GroupDescription: "Zusätzliche Optionen:"

[Files]
; Alle Dateien aus dem onedir-Build kopieren
Source: "..\dist\TextGenius\TextGenius.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\TextGenius\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenu
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "TextGenius starten"; Flags: nowait postinstall skipifsilent
