# cabfile

`cabfile` is a Python library for reading Windows `.cab` archives.

## Install

```bash
pip install cabfile
```

## API quick look

- `CabFile(source)` for listing, reading, and extracting members
- `is_cabinet(source)` for a fast cabinet check
- `probe(source)` for cabinet-level summary metadata

## CLI

The package includes a ZipFile-style CLI:

```bash
cabfile -l archive.cab
cabfile -t archive.cab
cabfile -e archive.cab output_dir
```

See the repository README for fuller examples and behavior notes.
