# Architecture

Sazgan is a Python/Flask service-management application with web, desktop and Android WebView clients.

## Project structure

```text
app.py                 Application entry point
app/                   Compatibility and application helpers
core/                  Business logic, persistence, security and shared services
routes/                HTTP routes and API endpoints
templates/             Jinja templates
static/                Web assets
native_client/         Native desktop client
android-webview/       Android WebView client
desktop/               Desktop client entry points
scripts/               Maintenance, migration, testing and release utilities
tests/                 Automated tests
tools/windows/         Windows build and installation commands
deploy/                Deployment configuration
config/                Environment-specific dependency lists
docs/                  Maintainer and user documentation
```

## Application layers

- `core/` contains reusable business and infrastructure logic.
- `routes/` contains web views and HTTP APIs and should remain thin where possible.
- `templates/` contains presentation only; business rules belong in Python modules.
- `static/` contains browser assets and client-side behavior.
- `native_client/` and `desktop/` provide client applications over the service/API layer.
- `scripts/` contains operational commands rather than application logic.

## Access control

Access decisions are centralized through the existing access helpers and route guards. New routes should use the existing access-control functions instead of hard-coded role checks.

## Database boundary

`core/db.py` is the primary database access layer. Schema changes are handled through `migrations/` and the migration engine. Do not add ad-hoc schema changes to request handlers.

## API and client boundary

The browser, native client and desktop clients communicate with the server through the existing route/API layer. Keep client-specific presentation concerns out of server business logic.

## Native client navigation

Native screens use the same functional areas as the web application: customers, service, warehouse, finance, reports, support and settings. Navigation should be added through the existing hub and screen structure rather than creating parallel application flows.

## Design system

Shared UI tokens are maintained in `design_tokens/` and the corresponding static assets. New UI should reuse the existing design system before introducing new one-off styles.

## Architectural decisions

- Keep business logic in `core/` and route handlers focused on HTTP concerns.
- Prefer existing compatibility modules when maintaining older imports.
- Keep migration files immutable after they have been applied.
- Keep generated/runtime data outside the source package.
