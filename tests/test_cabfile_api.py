from __future__ import annotations

from pathlib import Path

import pytest

import cabfile


pytestmark = pytest.mark.requires_makecab


def test_cabfile_context_manager_and_read(sample_single_cab: Path):
    with cabfile.CabFile(str(sample_single_cab)) as archive:
        assert list(archive) == ["hello.txt"]
        assert archive.read("hello.txt") == b"hello from cabfile\n"
        member = archive["hello.txt"]
        assert member is not None
        assert member.file_size == len(b"hello from cabfile\n")


def test_cabfile_members_and_read_many(sample_multi_cab: Path):
    with cabfile.CabFile(str(sample_multi_cab)) as archive:
        members = list(archive.values())
        assert [item.name for item in members] == ["alpha.txt", "beta.txt", "gamma.txt"]
        assert [item.filename for item in members] == ["alpha.txt", "beta.txt", "gamma.txt"]
        assert [item.size for item in members] == [len(b"alpha\n"), len(b"beta\n"), len(b"gamma\n")]
        assert [item.file_size for item in members] == [len(b"alpha\n"), len(b"beta\n"), len(b"gamma\n")]
        assert list(archive.read_many(["alpha.txt", "gamma.txt"])) == [
            ("alpha.txt", b"alpha\n"),
            ("gamma.txt", b"gamma\n"),
        ]
        assert archive.test() is True


def test_cabfile_extract_and_extract_all(sample_multi_cab: Path, tmp_path: Path):
    selected_out = tmp_path / "selected"
    all_out = tmp_path / "all"

    with cabfile.CabFile(str(sample_multi_cab)) as archive:
        archive.extract("beta.txt", str(selected_out))
        archive.extract_all(str(all_out), members=["alpha.txt", "gamma.txt"])

    assert not (selected_out / "alpha.txt").exists()
    assert (selected_out / "beta.txt").read_bytes() == b"beta\n"
    assert not (selected_out / "gamma.txt").exists()

    assert (all_out / "alpha.txt").read_bytes() == b"alpha\n"
    assert not (all_out / "beta.txt").exists()
    assert (all_out / "gamma.txt").read_bytes() == b"gamma\n"


def test_cabfile_mapping_metadata_interface(sample_multi_cab: Path):
    with cabfile.CabFile(str(sample_multi_cab)) as archive:
        assert list(archive.keys()) == ["alpha.txt", "beta.txt", "gamma.txt"]
        assert list(archive) == ["alpha.txt", "beta.txt", "gamma.txt"]
        assert len(archive) == 3

        values = list(archive.values())
        assert [item.name for item in values] == ["alpha.txt", "beta.txt", "gamma.txt"]

        items = list(archive.items())
        assert [name for name, _ in items] == ["alpha.txt", "beta.txt", "gamma.txt"]

        assert "beta.txt" in archive
        assert "missing.txt" not in archive

        member = archive["beta.txt"]
        assert member.name == "beta.txt"
        assert member.size == len(b"beta\n")

        with pytest.raises(KeyError):
            _ = archive["missing.txt"]
