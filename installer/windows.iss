; Inno Setup script for the Windows installer. CI passes the version:
;   iscc /DAppVersion=1.0.0a1 installer\windows.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{A3C7E9D1-5B2F-4E6A-8C41-9D0B7F2E3A55}
AppName=Stem Lift
AppVersion={#AppVersion}
AppPublisher=ROMMUSER
AppPublisherURL=https://github.com/axelfj/stem-lift
DefaultDirName={autopf}\Stem Lift
DefaultGroupName=Stem Lift
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE
OutputDir=Output
OutputBaseFilename=StemLift-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\StemLift.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\StemLift\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Stem Lift"; Filename: "{app}\StemLift.exe"
Name: "{group}\Uninstall Stem Lift"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Stem Lift"; Filename: "{app}\StemLift.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StemLift.exe"; Description: "{cm:LaunchProgram,Stem Lift}"; Flags: nowait postinstall skipifsilent
