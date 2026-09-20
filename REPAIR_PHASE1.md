# Sazgan — Repair Phase 1

This package contains the first repair/integrity pass for the empty-database installation.

## Implemented

- Centralized internal/external repair status transitions in `core/workflow.py`.
- Atomic compare-and-swap status transitions with status history and case timeline.
- Database-level guards for illegal repair status transitions.
- Object-level view/action authorization for repair records.
- Strict technician assignment by active role and province.
- Positive part-quantity validation at application and SQLite trigger level.
- Cross-field serial uniqueness enforcement, including legacy serial aliases.
- Soft-delete (`is_void`) consistency for repair parts; runtime `ALTER TABLE` for this field removed.
- Dedicated invoice/proforma actions instead of generic status/field mutation.
- Legacy generic repair status endpoints removed from web/native client.
- Generic case-status helper blocked from direct repair status mutation.
- Reception-review dashboard restricted so repair cases use the canonical repair workflow.
- Technician cartable restricted to explicitly assigned technicians.
- Migration registry advanced to workflow integrity migration 16.
- Removed runtime schema mutation for `request_parts.is_void` from warehouse/service paths.
- Added permanent SQLite integrity tests in `tests/test_workflow_integrity.py`.

## Validation

- Python AST parse: PASS for all Python source files.
- Python compileall: PASS.
- Workflow/SQLite integrity tests: 6 passed.
- Old generic repair status endpoint references: none found.
- Runtime `ALTER TABLE ... is_void` references in routes/core: none found.

## Environment limitation

A full Flask application startup/integration test could not be executed in this analysis environment because Flask/Werkzeug dependencies are not installed. The source package itself is syntax-clean, and the SQLite workflow/migration integrity layer was tested directly.

## Remaining phase-2 work

- Split large route modules (`routes/service.py`, `routes/native_api.py`, `core/helpers.py`).
- Move remaining installation/inspection workflow transitions to the same domain-service pattern.
- Remove the remaining legacy runtime `ALTER TABLE` calls from general schema helpers by consolidating startup migrations.
- Replace remaining broad exception swallowing in business-critical paths with explicit logging/rollback semantics.
