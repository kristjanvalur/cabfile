# cabfile 1.0.0 API Reference (Legacy)

This document describes the legacy API surface originally published as version `1.0.0`.
It is intended for side-by-side comparison with the 2.0 modernization plan.

> Note (current 2.0 branch): the active public API has moved to `CabFile` plus
> `is_cabinet`/`probe`, with optional ZipFile-compatible aliases layered on top.
> This file remains a historical reference.

## Module

Single-module implementation:

- `cabinet.py` (legacy distribution name `cabinet`)

In this repository modernization branch, the same code currently lives at:

- `src/cabfile/core.py` (implementation)
- `src/cabfile/api.py` and `src/cabfile/__init__.py` (public exports)

Suggested modernization:

Split the monolithic module into `api.py`, `core.py`, `models.py`, and `errors.py`, then expose a curated public surface from `__init__.py`. This keeps low-level ctypes details internal and makes the public API easier to maintain and document.

## Platform behavior

- Windows-only runtime.
- Imports `cabinet.dll` through `ctypes`.
- Raises `ImportError` at import time on non-Windows systems.

Suggested modernization:

Keep Windows-only support explicit, but raise a dedicated `CabPlatformError` with a clear message and remediation steps (for example, "cabfile requires Windows because it uses cabinet.dll"). Also add this platform constraint to README and CI to avoid ambiguous runtime failures.

## Public classes

### `CabinetFile`

Zip-like reader class for cabinet archives (read/extract only).

Constructor:

- `CabinetFile(filename, mode='r')`
  - `filename` accepts either a path-like value or file-like object.
  - `mode` exists but effective behavior is read-only.

Suggested modernization:

Replace `CabinetFile` with `CabFile(source)` and remove the unused `mode` parameter. Require explicit lifecycle control via context manager (`with CabFile(...) as cab:`) and keep `close()` for manual control.

Methods:

- `close()`
  - Releases internal FDI handle.

Suggested modernization:

Keep `close()` but make it idempotent and guaranteed safe to call multiple times. Prefer context-manager usage in examples and docs.

- `namelist()`
  - Returns member names list.

Suggested modernization:

Rename to `names()` and return `list[str]` with deterministic ordering. Optionally provide `iter_names()` for stream-style usage.

- `infolist()`
  - Returns list of `CabinetInfo` objects.

Suggested modernization:

Rename to `members()` or `iter_members()` and return typed dataclass instances (`CabMember`) with normalized metadata types.

- `printdir()`
  - Prints a formatted table of archive contents to stdout.

Suggested modernization:

Drop or demote `printdir()` from core API. Prefer returning structured data and letting CLI/UI layers handle presentation.

- `getinfo(name)`
  - Returns matching `CabinetInfo` for `name`, or `None`.

Suggested modernization:

Rename to `get_member(name)` and raise `KeyError` (or `CabFormatError`) when missing instead of returning `None`, reducing ambiguous branching in callers.

- `read(name)`
  - If `name` is a string, returns one member payload.
  - If `name` is a sequence, returns payload list.

Suggested modernization:

Make behavior unambiguous: `read(name: str) -> bytes` for one member only. Add explicit batch API (`read_many(names: Iterable[str]) -> dict[str, bytes]`) if needed.

- `extract(target, names=[])`
  - Extracts all files to `target` when `names` is empty.
  - Extracts selected members when `names` is provided.

Suggested modernization:

Split into `extract(name, target_dir)` and `extract_all(target_dir, members=None)`. Avoid mutable default arguments, use `pathlib.Path`, and enforce path traversal protections.

- `testcabinet()`
  - Returns `True` when archive can be fully read; else `False`.

Suggested modernization:

Rename to `test()` and provide predictable error semantics (return bool for integrity check failures, raise typed exceptions for operational/runtime failures).

Notes:

- Includes `__del__` finalizer that attempts to call `close()`.
- Designed around callback-driven decompression (`FDICopy`).

Suggested modernization:

Remove destructor-driven cleanup and rely on explicit close/context-manager semantics. Keep callback internals private and expose only high-level synchronous methods.

### `CabinetInfo`

Simple metadata container for archive members.

Fields:

- `filename`
- `date_time`
- `file_size`
- `external_attr`

Suggested modernization:

Replace `CabinetInfo` with `@dataclass(frozen=True, slots=True)` named `CabMember` and normalize field names/types:

- `filename` → `name: str`  
  Suggested modernization: Use a single decoded, normalized member name type (`str`) and document path separator behavior.

- `date_time` → `modified: datetime`  
  Suggested modernization: Return timezone-naive local `datetime` or documented UTC policy, instead of raw tuples.

- `file_size` → `size: int`  
  Suggested modernization: Keep as integer byte count and ensure consistency with extraction/read lengths.

- `external_attr` → `attributes: int`  
  Suggested modernization: Keep raw integer plus optional helper properties for common Windows file flags.

## Public functions

### `is_cabinetfile(filename)`

Checks whether a file is a cabinet.

- Accepts path or file-like object.
- Returns a low-level `FDICABINETINFO` structure on success.
- Returns `False` on failure paths.

Suggested modernization:

Replace with two clear APIs: `is_cabinet(source) -> bool` and `probe(source) -> CabinetSummary`. Avoid mixed return types and keep low-level ctypes structures internal.

### `DecodeFATTime(FATdate, FATtime)`

Decodes FAT date/time bitfields into a tuple.

Suggested modernization:

Make this an internal helper and return `datetime` directly. Add tests for date-component ordering and boundary values.

### `main(args=None)`

Legacy CLI entrypoint.

Supported options:

- `-l <cabinet.cab>`: list
- `-t <cabinet.cab>`: test
- `-e <cabinet.cab> <target>`: extract

Suggested modernization:

Move CLI to `python -m cabfile` with `argparse` subcommands (`list`, `test`, `extract`) and explicit exit codes. Keep CLI separate from core API.

## Public exceptions

### `CabinetError`

Raised for FDI error states via `ERF.raise_error()`.

Suggested modernization:

Adopt a small exception hierarchy: `CabFileError` (base), `CabPlatformError`, `CabFormatError`, `CabApiError`, and `CabExtractionError`. Convert low-level errors at boundaries.

## Notable legacy API characteristics

- Mixed return conventions (`False`, `None`, structures) for failure cases.
- Minimal typing/documented contracts.
- Python 2 compatibility constructs are present in source (e.g. `basestring`, `cStringIO` fallback).
- Some APIs are convenience-oriented rather than strictly typed/structured.
- Callback + global-constant design exposes many low-level symbols in module namespace.

Suggested modernization:

Standardize method contracts, fully type the public API, and eliminate mixed return patterns. Keep internals internal, publish a small intentional API, and document strict behavior for errors and edge cases.

## Low-level symbols exposed in module namespace

The legacy module exposes numerous FDI constants, ctypes structures, and helper functions,
including but not limited to:

- compression helpers (`CompressionTypeFromTCOMP`, etc.)
- structures (`ERF`, `FDICABINETINFO`, `FDINOTIFICATION`, ...)
- callback signatures (`PFNOPEN`, `PFNREAD`, ...)

These are implementation-facing and not a cleanly curated public API.

Suggested modernization:

Move low-level symbols to implementation modules (`core.py` or a future dedicated low-level module) and expose only user-facing API in `__init__.py`. If advanced users need internals, provide a clearly unsupported/internal import path.

## FDI callback contract (reference)

The decompression/enumeration path is driven by `FDICopy` with a notify callback:

- Signature: `callback(fdint, pnotify) -> INT_PTR`
- `fdint` is a `FDINOTIFICATIONTYPE` opcode.
- `pnotify.contents` contains member/cabinet metadata fields (`psz1`, `cb`, `date`, `time`, `attribs`, `hf`, ...).

Common opcodes and expected callback behavior:

- `fdintCABINET_INFO`
  - Cabinet metadata notification.
  - Typical return: `0` (continue).

- `fdintENUMERATE`
  - Enumeration-stage notification.
  - Typical return: `0` (continue).

- `fdintCOPY_FILE`
  - Fired once per member discovered.
  - Inspect metadata from `pnotify.contents`.
  - Return values:
    - `0`: skip member data copy (enumeration only)
    - file handle/int fd: request decompression into that handle
    - `-1`: abort traversal

- `fdintCLOSE_FILE_INFO`
  - Fired after a previously accepted member finishes writing.
  - `pnotify.contents.hf` is the handle previously returned from `fdintCOPY_FILE`.
  - Typical return values:
    - `1`: close/finalize succeeded; continue
    - `-1`: abort

- `fdintNEXT_CABINET`
  - Request to continue in next cabinet (multi-cabinet set).
  - Single-cab workflows generally do not support this and abort.

- `fdintPARTIAL_FILE`
  - Notification for partial file conditions across cabinet boundaries.

Notes:

- Exceptions raised in Python callbacks are trapped and translated to callback abort (`-1`) in wrapper code.
- In this project, early-stop semantics are modeled by returning `False` from higher-level visitors, which then map to callback abort internally.

## Summary

Version `1.0.0` provides a functional Windows CAB reader/extractor API centered on
`CabinetFile`, but with legacy conventions, limited typing, and mixed high-/low-level exposure.
This baseline is the comparison target for 2.0 redesign work.

Suggested modernization:

For 2.0, favor a small typed API (`CabFile`, `CabMember`, `is_cabinet`, `probe`), explicit error hierarchy, private ctypes internals, and modern CLI separation. This yields a maintainable foundation for post-2.0 improvements.
