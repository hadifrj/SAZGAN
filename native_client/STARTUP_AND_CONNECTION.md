# Native Client Startup & Connection

## Server address
The login form intentionally does **not** contain an IP/server field.

Configure the server once from **Settings > Connection** or from the **Connection Settings** button on the login screen. The value is stored in the user's `%APPDATA%\Sazgan\sazgan_native_client.json` file.

## Startup performance
The Native Client is built as a PyInstaller **onedir** application. This avoids the extraction overhead of `--onefile` on every launch.

The application also lazy-loads feature pages until after login and defers non-critical font loading until the Qt event loop starts.

## Recommended launch
Run:

`dist\SazganNative\SazganNative.exe`

For deployment, copy the entire `SazganNative` folder rather than only the EXE.
