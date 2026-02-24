# Copilot Instructions for cabfile

## Environment and tooling

- Use `uv` for Python environment and command execution.
- Prefer `uv run ...` for tests and scripts.
- Keep changes small, focused, and commit in logical steps.

## Native crash debugging on Windows

This project uses `ctypes` and can trigger native access violations during test runs.
To avoid intrusive Windows/JIT crash dialog popups and get immediate terminal feedback, run tests via:

```powershell
uv run python -c "import ctypes, sys, pytest; ctypes.windll.kernel32.SetErrorMode(0x0002); raise SystemExit(pytest.main(['-q']))"
```

- `0x0002` is `SEM_NOGPFAULTERRORBOX`.
- Use this wrapper for focused test targets as well, e.g. `['-q', 'tests/test_cab_functional.py']`.

## Test guidance

- Prefer targeted tests first, then broader suite runs.
- When creating CAB fixtures for tests, use test-only tooling under `tests/`.
- If native crashes occur, isolate whether fixture generation or CAB reading is at fault by validating generated `.cab` with native tools (e.g. `expand -D`).
