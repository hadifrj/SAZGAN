#define MyAppName "Sazgan Client"
#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Sazgan"

[Setup]
AppId={{SAZGAN-CLIENT-1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SazganClient
DefaultGroupName=Sazgan Client
OutputDir=output
OutputBaseFilename=SazganClient-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\SazganClient.exe
WizardStyle=modern
; Windows 7 SP1 and newer
MinVersion=6.1sp1

[Files]
; Built by desktop\build_client_lite.bat (PyInstaller --onefile --windowed output).
; No webview/CEF/WebView2 - just tkinter + system default browser.
Source: "..\dist\SazganClientLite.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\Sazgan Client"; Filename: "{app}\SazganClientLite.exe"
Name: "{group}\Sazgan Client"; Filename: "{app}\SazganClientLite.exe"
Name: "{group}\تغییر آدرس سرور"; Filename: "{app}\SazganClientLite.exe"; Parameters: "--setup"

[Run]
; On first launch, SazganClientLite.exe asks for the server address, then opens
; it in the user's default browser (Chrome/Firefox/Edge/IE) - no embedded engine.
Filename: "{app}\SazganClientLite.exe"; Description: "اجرای Sazgan Client"; Flags: nowait postinstall skipifsilent
