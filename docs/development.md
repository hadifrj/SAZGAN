# Development

## Before changing code

1. Read the relevant module and its tests.
2. Keep logic in the existing package structure.
3. Reuse existing helpers and compatibility layers before adding new abstractions.
4. Add or update automated tests for behavior that can be verified locally.
5. Update documentation when a public workflow, configuration or architecture changes.

## Naming

Use names that describe the responsibility of a module or command. Avoid names tied to temporary implementation stages, internal work waves, prompts or one-off investigations.

- Python modules: `snake_case.py`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Batch files: concise action-oriented names
- Documentation: stable topic names such as `architecture.md`, `database.md`, `operations.md`

## Testing

From the project root:

```text
python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q core routes native_client scripts
```

For a controlled Windows test run:

```text
scripts\RUN_TEST_MODE.bat
```

`scripts/smoke_test.py` performs HTTP-level checks and requires a running test environment.

## Release

Use the release tools under `scripts/` rather than editing release metadata manually.

```text
python scripts/build_release.py --bump patch
python scripts/release_check.py
```

The release process updates `VERSION`, records release notes in the root `CHANGELOG.md`, creates the source archive and can generate a checksum.

## Repository hygiene

Do not commit local secrets, runtime databases, uploaded files, caches, build directories or temporary investigation output. `.gitignore` defines the excluded runtime/build paths.

## API work

When adding an endpoint:

1. Put it in the appropriate route module.
2. Reuse existing authentication and authorization helpers.
3. Return the established response format.
4. Add a test for the important success and failure paths.
5. Update `docs/architecture.md` only when the boundary or flow changes.
