# Windows Command Tools

`Sazgan.bat` in the repository root is the only user-facing command entry point.
All other Windows `.bat` files belong here.

## Naming
- `build-*` — build/release operations
- `install-*` — installation/service operations
- `prepare-*` — packaging/runtime preparation
- `update.bat` — update workflow

## Rules
1. Do not add `.bat` files to `desktop/`, `native_client/`, `installer/`, or `scripts/`.
2. Every script resolves the repository root from `%~dp0` before doing work.
3. Build manifests live under `config/`.
4. Native Client is built as `onedir` to reduce cold-start extraction delay.
5. The root `Sazgan.bat` delegates to these tools.
