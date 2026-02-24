from __future__ import annotations

from pathlib import Path

import pytest

import cabfile
from tests.cab_tools import create_cab_with_makecab, makecab_available


pytestmark = pytest.mark.skipif(not makecab_available(), reason="makecab.exe is required for CAB fixture generation")


def test_generated_cab_list_and_read(tmp_path: Path):
    cab_path = create_cab_with_makecab(
        tmp_path / "fixture1",
        "sample.cab",
        {"hello.txt": b"hello from cabfile\n"},
    )

    archive = cabfile.CabinetFile(str(cab_path))
    try:
        names = archive.namelist()
        assert names == ["hello.txt"]

        payload = archive.read("hello.txt")
        assert payload == b"hello from cabfile\n"

        assert cabfile.is_cabinetfile(str(cab_path)) is not False
    finally:
        archive.close()


def test_generated_cab_extract(tmp_path: Path):
    cab_path = create_cab_with_makecab(
        tmp_path / "fixture2",
        "extract.cab",
        {
            "one.txt": b"one\n",
            "two.txt": b"two\n",
        },
    )

    out_dir = tmp_path / "extracted"

    archive = cabfile.CabinetFile(str(cab_path))
    try:
        archive.extract(str(out_dir))
    finally:
        archive.close()

    assert (out_dir / "one.txt").read_bytes() == b"one\n"
    assert (out_dir / "two.txt").read_bytes() == b"two\n"
