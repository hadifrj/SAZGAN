# سازگان — سامانه مدیریت خدمات پس از فروش

Sazgan is a service-management application built with Python and Flask, with web, desktop, and Android WebView clients.

## Quick start — Windows

Run `Sazgan.bat` and select the required command from the menu.

For a normal local run, open:

```text
http://127.0.0.1:5000
```

For a controlled test run, use `scripts/RUN_TEST_MODE.bat`.

## Project layout

```text
app.py                 Application entry point
app/                   Application compatibility modules
core/                  Business logic, persistence, security, and shared services
routes/                HTTP routes and API endpoints
templates/             Jinja templates
static/                CSS, JavaScript, icons, fonts, and web assets
native_client/         Native desktop client
android-webview/       Android WebView client
desktop/               Desktop client entry points
scripts/               Release, maintenance, migration, and test utilities
tests/                 Automated tests
tools/windows/         Windows build and installation commands
deploy/                Deployment configuration
docs/                  Maintainer and user documentation
config/                Environment-specific dependency lists
data/                  Runtime data directory (local files are ignored)
```

## Documentation

Start with [`docs/README.md`](docs/README.md).

## Version and release

The current project version is stored in `VERSION`. Release metadata is stored in `RELEASE.json` and `BUILD_INFO.json`.

Use the release tooling under `scripts/` instead of editing release metadata ad hoc.

## Testing

From the project root:

```text
python -m unittest discover -s tests -p "test_*.py"
```

## Source hygiene

Local secrets, databases, uploaded files, and build artifacts are intentionally excluded from the source package. See `.gitignore` for the complete list.
