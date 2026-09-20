## [v1.0.15] — 1405/06/15

### Bug Fix
- (Add details here)

---

## [v1.0.14] — 1405/06/14

### Bug Fix
- (Add details here)

---

## [v1.0.13] — 1405/06/12

### Bug Fix
- (Add details here)

---

## [v1.0.12] — 1405/06/10

### Bug Fix
- (Add details here)

---

## [v1.0.11] — 1405/06/09

### Bug Fix
- (Add details here)

---

## [v1.0.10] — 1405/06/07

### Bug Fix
- (Add details here)

---

## 1.0.9 — 2026-08-29

### Fixed
- Fixed a `NameError` in the central workflow authorization path for finance users viewing inspection requests (`FINANCE_VISIT_STATUSES`).
- Aligned finance inspection action authorization with inspection-specific finance statuses.
- Added a regression test for finance inspection visibility and proforma decision authorization.
- Full automated test suite: 20 passed.

## 1.0.8 — 2026-08-29

### Changed
- Unified installation and inspection status transitions under the central workflow service.
- Added database guards for installation and inspection state transitions.
- Enforced object-level access for installation/inspection HTML and Native API detail screens.
- Added Native API action authorization before delegating to legacy HTML handlers.
- Removed technician-name matching as an authorization source; assigned_technician_id is canonical.
- Made technician assignment validation fail closed for installation and inspection forms.
- Added phase-2 workflow integrity tests; 19 critical tests pass.
- Raised schema registry/migration target to version 17.


## 1.0.1 — 2026-08-28

### Changed
- Consolidated the project root and removed obsolete duplicate release notes and audit artifacts.
- Moved historical implementation notes out of the active source tree.
- Removed duplicated legacy compatibility copies that were no longer referenced.
- Added a consistent `RUN_TEST_MODE` entry point for local verification.
- Removed environment-specific credentials and generated upload files from the source package.
- Updated developer documentation and repository hygiene rules.

## 1.0.0 — Baseline

- Established centralized version and release metadata.
- Added release validation and packaging tools.
- Consolidated the application source under the current package structure.
