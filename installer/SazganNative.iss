#define MyAppName "Sazgan Native Client"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "مهندسی سازگان گستر"

[Setup]
AppId={{SAZGAN-NATIVE-1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SazganNative
DefaultGroupName=Sazgan Native Client
OutputDir=output
OutputBaseFilename=SazganNative-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=..\static\icons\sazgan-app.ico
UninstallDisplayIcon={app}\SazganNative.exe
WizardStyle=modern
; Windows 7 SP1 and newer
MinVersion=6.1sp1

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Built by tools\windows\build-native-client.bat (PyInstaller --onedir --windowed
; output). The whole folder is packaged as-is: SazganNative.exe plus its bundled
; Python runtime, Qt libraries, and the fonts added via --add-data.
Source: "..\dist\SazganNative\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\سازگان"; Filename: "{app}\SazganNative.exe"
Name: "{group}\سازگان"; Filename: "{app}\SazganNative.exe"
Name: "{group}\حذف سازگان"; Filename: "{uninstallexe}"

[Run]
; The app itself asks for the server address on first launch (Connection
; Settings) and stores it under %APPDATA%\Sazgan - no admin rights needed
; at runtime, matching PrivilegesRequired=lowest above.
Filename: "{app}\SazganNative.exe"; Description: "اجرای سازگان"; Flags: nowait postinstall skipifsilent
