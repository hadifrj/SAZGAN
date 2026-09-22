#define MyAppName "Sazgan"
#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Sazgan"

[Setup]
AppId={{SAZGAN-SERVER-1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=C:\Sazgan
DefaultGroupName=Sazgan
OutputDir=output
OutputBaseFilename=Sazgan-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Sazgan.exe
WizardStyle=modern

[Files]
Source: "..\app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\VERSION"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Sazgan.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\core\*"; DestDir: "{app}\core"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\routes\*"; DestDir: "{app}\routes"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\scripts\update.py"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\scripts\migrate_db.py"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\tools\windows\install-service.bat"; DestDir: "{app}\tools\windows"; Flags: ignoreversion
Source: "..\tools\windows\install-service-silent.bat"; DestDir: "{app}\tools\windows"; Flags: ignoreversion
Source: "..\scripts\run_as_service.py"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "server_wizard.py"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "..\offline\*"; DestDir: "{app}\offline"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\offline_packages\README.txt"; DestDir: "{app}\offline_packages"; Flags: ignoreversion
Source: "..\migrations\*"; DestDir: "{app}\migrations"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\backups"
Name: "{app}\backups\updates"
Name: "{app}\data"
Name: "{app}\config"
Name: "{app}\logs"
Name: "{app}\static\uploads"

[Icons]
Name: "{autodesktop}\Sazgan"; Filename: "http://127.0.0.1:5000"
Name: "{group}\Sazgan (مرورگر)"; Filename: "http://127.0.0.1:5000"
Name: "{group}\Sazgan (پنل مدیریت/سرویس)"; Filename: "{app}\Sazgan.bat"

[Run]
Filename: "{app}\tools\windows\install-service-silent.bat"; WorkingDir: "{app}\tools\windows"; Flags: runhidden waituntilterminated
Filename: "http://127.0.0.1:5000"; Description: "باز کردن Sazgan در مرورگر"; Flags: postinstall shellexec skipifsilent
