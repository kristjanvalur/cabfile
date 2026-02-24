from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

import cabfile


pytestmark = pytest.mark.requires_makecab


def test_zipfile_read_and_extract_wrappers(multi_cab_source, tmp_path: Path):
    selected_out = tmp_path / "selected"
    all_out = tmp_path / "all"

    with cabfile.CabFile(multi_cab_source) as archive:
        assert archive.read("alpha.txt") == b"alpha\n"

        zip_path = archive.extract("beta.txt", str(selected_out))
        assert Path(zip_path).name == "beta.txt"

        assert archive.extractall(str(all_out), members=["alpha.txt", "gamma.txt"]) is None

    assert not (selected_out / "alpha.txt").exists()
    assert (selected_out / "beta.txt").read_bytes() == b"beta\n"
    assert not (selected_out / "gamma.txt").exists()

    assert (all_out / "alpha.txt").read_bytes() == b"alpha\n"
    assert not (all_out / "beta.txt").exists()
    assert (all_out / "gamma.txt").read_bytes() == b"gamma\n"


def test_zipfile_discovery_aliases_and_properties(multi_cab_source):
    with cabfile.CabFile(multi_cab_source) as archive:
        assert archive.namelist() == ["alpha.txt", "beta.txt", "gamma.txt"]

        infos = archive.infolist()
        assert [item.name for item in infos] == ["alpha.txt", "beta.txt", "gamma.txt"]

        info = archive.getinfo("beta.txt")
        assert info.name == "beta.txt"
        assert info.size == len(b"beta\n")

        filelist = archive.filelist
        assert [member.name for member in filelist] == ["alpha.txt", "beta.txt", "gamma.txt"]

        name_to_info = archive.NameToInfo
        assert list(name_to_info.keys()) == ["alpha.txt", "beta.txt", "gamma.txt"]
        assert name_to_info["beta.txt"].name == "beta.txt"
        assert name_to_info["beta.txt"].size == len(b"beta\n")

        with pytest.raises(KeyError):
            _ = archive.getinfo("missing.txt")


def test_zipfile_printdir(multi_cab_source):
    with cabfile.CabFile(multi_cab_source) as archive:
        output = StringIO()
        archive.printdir(file=output)

    text = output.getvalue()
    assert "File Name" in text
    assert "Modified" in text
    assert "Size" in text
    assert "alpha.txt" in text
    assert "beta.txt" in text
    assert "gamma.txt" in text
