# cabfile

This is a Python module for reading Windows `.cab` files.

The modern API is centered on `CabFile` and a small set of helpers:

- `CabFile(source)`: context-managed cabinet reader
- `is_cabinet(source) -> bool`
- `probe(source) -> CabSummary`

`CabFile` provides two layers:

- member-centric APIs (for metadata + payload workflows)
- ZipFile-compatible aliases (`read`, `extract`, `extractall`, `namelist`, `infolist`, `getinfo`, `printdir`, `filelist`, `NameToInfo`)

## Example

```python
import cabfile

with cabfile.CabFile("archive.cab") as cab:
    print(cab.namelist())
    data = cab.read("hello.txt")

print(cabfile.is_cabinet("archive.cab"))
summary = cabfile.probe("archive.cab")
print(summary.file_count)
```

Based on the cabinet SDK, available from http://support.microsoft.com/kb/310618.
Also reuses some code from `zipfile.py`.

Since it uses `ctypes` to interface with `cabinet.dll` included with Windows,
this code works on Windows only.
