from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from cabfile.cli import main


pytestmark = pytest.mark.requires_makecab


def test_cli_list(sample_multi_cab: Path):
    stdout = StringIO()
    stderr = StringIO()

    rc = main(["-l", str(sample_multi_cab)], stdout=stdout, stderr=stderr)

    assert rc == 0
    text = stdout.getvalue()
    assert "File Name" in text
    assert "alpha.txt" in text
    assert "beta.txt" in text
    assert "gamma.txt" in text
    assert stderr.getvalue() == ""


def test_cli_test_ok(sample_single_cab: Path):
    stdout = StringIO()
    stderr = StringIO()

    rc = main(["-t", str(sample_single_cab)], stdout=stdout, stderr=stderr)

    assert rc == 0
    assert stdout.getvalue().strip() == "True"
    assert stderr.getvalue() == ""


def test_cli_extract(sample_multi_cab: Path, tmp_path: Path):
    out_dir = tmp_path / "extract"
    stdout = StringIO()
    stderr = StringIO()

    rc = main(["-e", str(sample_multi_cab), str(out_dir)], stdout=stdout, stderr=stderr)

    assert rc == 0
    assert (out_dir / "alpha.txt").read_bytes() == b"alpha\n"
    assert (out_dir / "beta.txt").read_bytes() == b"beta\n"
    assert (out_dir / "gamma.txt").read_bytes() == b"gamma\n"
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""


def test_cli_extract_requires_target(sample_multi_cab: Path):
    with pytest.raises(SystemExit) as exc:
        main(["-e", str(sample_multi_cab)])
    assert exc.value.code == 2


def test_cli_bad_cab_reports_error(tmp_path: Path):
    invalid = tmp_path / "invalid.cab"
    invalid.write_bytes(b"not a cabinet")
    stdout = StringIO()
    stderr = StringIO()

    rc = main(["-t", str(invalid)], stdout=stdout, stderr=stderr)

    assert rc == 1
    assert stdout.getvalue().strip() == "False"
    assert stderr.getvalue() == ""
