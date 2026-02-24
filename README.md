# cabfile

Read Windows `.cab` archives with a small, practical API.

The modern API is centered on `CabFile` and two helpers:

- `CabFile(source)` for member listing, reading, and extraction
- `is_cabinet(source) -> bool` for safe type checks
- `probe(source) -> CabSummary` for fast cabinet-level metadata

## Quick start

```python
import cabfile

with cabfile.CabFile("archive.cab") as cab:
        print(cab.namelist())
        payload = cab.read("hello.txt")

print(cabfile.is_cabinet("archive.cab"))
summary = cabfile.probe("archive.cab")
print(summary.file_count)
```

## API shape

`CabFile` exposes two complementary layers:

- Member-centric methods for metadata + payload workflows:
    - `read_members(names=None)`
    - `extract_members(target_dir, names=None)`
- ZipFile-compatible methods/properties for drop-in usage patterns:
    - `read`, `extract`, `extractall`, `namelist`, `infolist`, `getinfo`, `printdir`, `filelist`, `NameToInfo`

## Compatibility

Note: This project uses `ctypes` with Windows `cabinet.dll` APIs.
It is intended for Windows environments.

Note: CAB decryption/password handling is not supported.
ZipFile-shaped `pwd` parameters are accepted for compatibility but raise `NotImplementedError` when provided.

## Background

Based on the Microsoft Cabinet SDK API surface (FDI), with compatibility ideas borrowed from `zipfile.py`.
