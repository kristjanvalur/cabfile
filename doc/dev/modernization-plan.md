# cabfile 2.0 Modernization Plan

## Scope and assumptions

This plan targets a **breaking 2.0 release** (`2.0.0pre1` already set) and assumes:

- No Python backward compatibility is required.
- No API backward compatibility is required.
- Target runtime is Python 3.11+ only.
- Windows remains the only supported platform (dependency on `cabinet.dll`).

## Current status (implemented)

- Project migrated to `pyproject.toml` + `src/` layout.
- Package/module renamed to `cabfile`.
- Python 2 compatibility branches removed.
- 64-bit ctypes binding issues fixed for FDI callbacks/handles.
- Core module split into `api.py`, `core.py`, `errors.py`, and `models.py`.
- Generated-CAB functional tests added (with `makecab`-gated fixtures).
- Public `CabFile` API now includes:
  - member-centric methods: `read_members(names=None)`, `extract_members(target_dir, names=None)`
  - ZipFile-compatible layer: `read`, `extract`, `extractall`, `namelist`, `infolist`, `getinfo`, `printdir`, `filelist`, `NameToInfo`
- Public helpers implemented:
  - `is_cabinet(source) -> bool`
  - `probe(source) -> CabSummary`
- `CabMember` now uses `datetime` values for timestamps.
- Tests are organized into API, ZipFile-compatibility, and functional suites, with path + file-like source parameterization.

## Goals

1. Deliver a clean, typed, Python 3.11+ API.
2. Separate low-level ctypes/FDI internals from user-facing API.
3. Improve correctness for bytes/text handling and path behavior.
4. Provide deterministic resource management and clearer exceptions.
5. Ship with practical tests and CI for long-term maintainability.

## Proposed package structure

```text
doc/
  dev/
    modernization-plan.md
src/
  cabfile/
    __init__.py
    api.py
    errors.py
    models.py
    core.py
tests/
  conftest.py
  test_import.py
  test_cab_functional.py
  cab_tools.py
```

### Module responsibilities

- `api.py`: Public classes/functions and exports.
- `errors.py`: Exception hierarchy.
- `models.py`: Dataclasses (e.g., member metadata).
- `core.py`: ctypes declarations, callback plumbing, and current legacy-compatible reader implementation.
- `__init__.py`: curated public exports and package metadata.

## Public API (current 2.0 state)

### Primary class

- `CabFile(source: str | os.PathLike[str] | BinaryIO)`
- Context manager required by design:
  - `with CabFile(path) as cab:`

### Member-centric methods

- mapping-style metadata: `keys`, `values`, `items`, `__getitem__`, `__contains__`, iteration/length
- `visit(on_copy_file) -> bool`
- `read_members(names: Iterable[str] | None = None) -> Iterator[tuple[CabMember, bytes]]`
- `extract_members(target_dir: str | os.PathLike[str], names: Iterable[str] | None = None) -> Iterator[CabMember]`
- `test() -> bool`
- `close() -> None`

### ZipFile-compatible layer

- `read(name: str, pwd: bytes | None = None) -> bytes`
- `extract(member, path=None, pwd=None) -> str`
- `extractall(path=None, members=None, pwd=None) -> None`
- `namelist()`, `infolist()`, `getinfo(name)`, `printdir(file=None)`
- `filelist` and `NameToInfo` properties

### Top-level helpers

- `is_cabinet(source: str | os.PathLike[str] | BinaryIO) -> bool`
- `probe(source: str | os.PathLike[str] | BinaryIO) -> CabSummary`

### Data models

Use dataclasses with slots:

- `CabMember`:
  - `name: str | None`
  - `size: int`
  - `datetime: datetime | None`
  - `attributes: int`
- `CabSummary`:
  - `file_count: int`
  - `folder_count: int`
  - `set_id: int`
  - `cabinet_index: int`

## Exception model

Define explicit typed errors:

- `CabFileError(Exception)` (base)
- `CabPlatformError(ImportError)`
- `CabFormatError(CabFileError)`
- `CabApiError(CabFileError)`
- `CabExtractionError(CabFileError)`

Rules:

- Convert low-level FDI/ctypes failures into typed exceptions.
- Avoid returning ambiguous sentinel values (`False`/`None`) for error conditions.

## Behavioral improvements

1. **Bytes/text correctness**
   - Decode FDI-provided filenames once at callback boundary.
   - Use `io.BytesIO` for binary payloads.
2. **Path safety**
   - Prevent path traversal during extraction (reject absolute paths and `..` escapes).
3. **Time conversion correctness**
   - Normalize FAT time decoding and emit `datetime` objects.
4. **Resource lifecycle**
   - Remove reliance on `__del__`; require explicit close/context manager.
5. **Type hints**
   - Add complete typing for all public APIs and internal boundaries.

## CLI modernization

Add module CLI entrypoint:

- `python -m cabfile list archive.cab`
- `python -m cabfile test archive.cab`
- `python -m cabfile extract archive.cab --out target/`

Use `argparse` with structured exit codes and concise error messages.

## Testing strategy

### Unit tests

- Import smoke test.
- API behavior (names/read/extract/test).
- Path safety checks for extraction traversal attempts.
- Exception mapping tests.

### Integration tests

- Include at least one small fixture `.cab` in `tests/fixtures/`.
- Validate extraction outputs and metadata.

### CI matrix

- Python 3.11, 3.12, 3.13
- Windows runner required for functional tests.

## Tooling and quality gates

- Formatter/linter: `ruff` (format + lint).
- Type checking: `mypy` (or `pyright`; choose one and enforce).
- Test runner: `pytest`.
- Enforce checks in CI before release tagging.

## Implementation phases

### Phase 1: Internal split and cleanup

- Split monolithic implementation into `api.py`, `core.py`, `errors.py`, `models.py`.
- Remove Python 2 code paths and legacy compatibility branches.
- Fix bytes/text and FAT time handling.

Status: largely complete, with remaining cleanup items.

### Phase 2: New API surface

- Implement `CabFile`, top-level `is_cabinet` and `probe`, dataclass models, and typed exceptions.
- Add `python -m cabfile` CLI commands.

Status: mostly complete for API shape; CLI modernization still pending.

### Phase 3: Validation and release prep

- Add fixture-based tests and CI matrix.
- Update README to 2.0 API and migration notes.
- Publish `2.0.0pre1`/subsequent pre-releases for feedback.

Status: fixture-based tests are in place and currently passing; docs/CI/release polish remains.

## 1.x to 2.0 migration notes

Because 2.0 is intentionally breaking:

- `CabinetFile` should be considered replaced by `CabFile`.
- `CabinetInfo` replaced by `CabMember` dataclass.
- `is_cabinetfile()` replaced by `is_cabinet()` / `probe()`.
- Legacy CLI flags (`-l/-t/-e`) replaced by subcommands (`list/test/extract`).

## Definition of done for 2.0.0

- Public API is fully typed and documented.
- No Python 2 compatibility code remains.
- No legacy API compatibility shims remain.
- Tests pass on supported Python versions on Windows.
- README and project metadata match the new API and repository URLs.
