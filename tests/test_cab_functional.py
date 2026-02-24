from __future__ import annotations

from pathlib import Path

import pytest

import cabfile


pytestmark = pytest.mark.requires_makecab


def test_generated_cab_list_and_read(sample_single_cab: Path):
    cab_path = sample_single_cab

    archive = cabfile.CabinetFile(str(cab_path))
    try:
        names = archive.namelist()
        assert names == ["hello.txt"]

        payload = archive.read("hello.txt")
        assert payload == b"hello from cabfile\n"

        assert cabfile.is_cabinetfile(str(cab_path)) is not False
    finally:
        archive.close()


def test_generated_cab_extract(sample_multi_cab: Path, tmp_path: Path):
    cab_path = sample_multi_cab

    out_dir = tmp_path / "extracted"

    archive = cabfile.CabinetFile(str(cab_path))
    try:
        archive.extract(str(out_dir))
    finally:
        archive.close()

    assert (out_dir / "alpha.txt").read_bytes() == b"alpha\n"
    assert (out_dir / "beta.txt").read_bytes() == b"beta\n"
    assert (out_dir / "gamma.txt").read_bytes() == b"gamma\n"


def test_infolist_getinfo_and_multi_read(sample_multi_cab: Path):
    cab_path = sample_multi_cab

    archive = cabfile.CabinetFile(str(cab_path))
    try:
        infos = archive.infolist()
        assert len(infos) == 3

        names = [info.filename for info in infos]
        assert names == ["alpha.txt", "beta.txt", "gamma.txt"]

        info_alpha = archive.getinfo("alpha.txt")
        assert info_alpha is not None
        assert info_alpha.file_size == len(b"alpha\n")

        assert archive.getinfo("missing.txt") is None

        payloads = archive.read(["alpha.txt", "beta.txt", "gamma.txt"])
        assert payloads == [b"alpha\n", b"beta\n", b"gamma\n"]
    finally:
        archive.close()


def test_extract_selected_names_only(sample_multi_cab: Path, tmp_path: Path):
    cab_path = sample_multi_cab

    out_dir = tmp_path / "selected"

    archive = cabfile.CabinetFile(str(cab_path))
    try:
        archive.extract(str(out_dir), names=["beta.txt"])
    finally:
        archive.close()

    assert not (out_dir / "alpha.txt").exists()
    assert (out_dir / "beta.txt").read_bytes() == b"beta\n"
    assert not (out_dir / "gamma.txt").exists()


@pytest.mark.xfail(reason="Known bytes/str mismatch in file-object path of FDIObjectFileManager", strict=False)
def test_file_object_inputs_and_testcabinet(sample_single_cab: Path):
    cab_path = sample_single_cab

    with cab_path.open("rb") as file_obj:
        assert cabfile.is_cabinetfile(file_obj) is not False

    with cab_path.open("rb") as file_obj:
        archive = cabfile.CabinetFile(file_obj)
        try:
            assert archive.namelist() == ["hello.txt"]
            assert archive.read("hello.txt") == b"hello\n"
            assert archive.testcabinet() is True
        finally:
            archive.close()


def test_testcabinet_returns_false_for_truncated_file(truncated_cab: Path):
    truncated_path = truncated_cab

    archive = cabfile.CabinetFile(str(truncated_path))
    try:
        assert archive.testcabinet() is False
    finally:
        archive.close()
