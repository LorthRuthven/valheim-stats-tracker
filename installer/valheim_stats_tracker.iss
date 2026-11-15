; Valheim Stats Tracker — véritable installateur Windows sans scripts cachés
; Installation utilisateur, pas de droits administrateur ni de tâche planifiée.
#define AppVersion "2.4.2"

[Setup]
AppId={{4C58AF5F-7A0F-4255-9F6E-05FB89829C73}
AppName=Valheim Stats Tracker
AppVersion={#AppVersion}
AppVerName=Valheim Stats Tracker {#AppVersion}
AppPublisher=Valheim Stats Tracker (projet communautaire)
AppPublisherURL=https://github.com/LorthRuthven/valheim-stats-tracker
AppSupportURL=https://github.com/LorthRuthven/valheim-stats-tracker/issues
DefaultDirName={localappdata}\Programs\ValheimStatsTracker
DefaultGroupName=Valheim Stats Tracker
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\ValheimStatsTracker.exe
OutputDir=..\dist\installer
OutputBaseFilename=Valheim_Stats_Tracker_v{#AppVersion}_Setup_Windows
Compression=lzma2
SolidCompression=yes
SetupLogging=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis"; Flags: unchecked

[Files]
Source: "..\dist\ValheimStatsTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Valheim Stats Tracker"; Filename: "{app}\ValheimStatsTracker.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Valheim Stats Tracker"; Filename: "{app}\ValheimStatsTracker.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\ValheimStatsTracker.exe"; Description: "Lancer Valheim Stats Tracker"; Flags: nowait postinstall skipifsilent
