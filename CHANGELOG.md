# Changelog

All notable changes to this project are documented in this file.

## 2.0.0 - 2026-02-24

### Release

- Promote `2.0.0rc1` to stable `2.0.0`.

### Highlights

- Modernized API centered on `CabFile` for Python 3.11+.
- Added ZipFile-style compatibility APIs and CLI (`cabfile`, `python -m cabfile`).
- Added modern CI, publishing, and docs pipelines with MkDocs API reference generation.

## 2.0.0rc1 - 2026-02-24

### Modernization highlights

- Modernized the library around a new high-level `CabFile` API for Python 3.11+.
- Added member-centric read/extract workflows with richer metadata support.
- Added ZipFile-compatible surface (`read`, `extract`, `extractall`, `namelist`, `infolist`, `getinfo`, `printdir`).
- Standardized timestamp metadata on `datetime` values.
- Added cabinet probes via `is_cabinet()` and `probe()`.

### CLI and packaging

- Added a ZipFile-style CLI and module entrypoint (`cabfile`, `python -m cabfile`).
- Updated project metadata and typed-package marker support.
- Switched documentation to Markdown and added MkDocs + API docs generated from docstrings.

### Quality and CI

- Added/expanded Ruff, mypy, and test coverage with uv-centric workflows.
- Added release/publish and docs workflows, including GitHub Pages deployment support.
- Improved Windows-native test execution stability for ctypes crash-dialog behavior.
