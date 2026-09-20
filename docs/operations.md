# Operations

## Start on Windows

Run `Sazgan.bat` from the project root and select the required command. For a normal local server, open:

```text
http://127.0.0.1:5000
```

For a controlled test environment, use `scripts\RUN_TEST_MODE.bat`.

## Dependencies

```text
pip install -r requirements.txt
python app.py
```

Use the Windows control menu for dependency installation when available.

## LAN access

The server can listen on `0.0.0.0:5000`. From another device on the same network, open the server's LAN address, for example:

```text
http://192.168.1.10:5000
```

If Windows Firewall blocks access, allow TCP port 5000 as appropriate for the local network.

## Health and diagnostics

Use the diagnostics options in `Sazgan.bat`, or check:

```text
http://127.0.0.1:5000/health
```

The scripts `health_check.py` and `smoke_test.py` provide additional checks.

## Windows service

Use the service tools under `tools/windows/` or the installation wizard. The service should run the production WSGI configuration rather than Flask's development server.

## Update

Use the updater with a release package. The update process is designed to preserve runtime data, apply pending database migrations and run health checks after the application files are replaced.

## Build a release

```text
python scripts/build_release.py --bump patch
python scripts/release_check.py
```

Release output belongs in `dist/` and is not part of the source tree.

## Offline installation

The project includes offline/runtime helpers under `offline/`, `offline_packages/` and the Windows tools. Use the corresponding preparation/install commands when the target machine has no internet access.

## Runtime data

Keep databases, backups, uploads, logs, generated files and local configuration outside the source archive. A release package contains application code and required static resources, not live customer data.
