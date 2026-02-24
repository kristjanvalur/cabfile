from __future__ import annotations

from pathlib import Path

import pytest

import cabfile


pytestmark = pytest.mark.requires_makecab


def test_generated_cab_list_and_read(sample_single_cab: Path):
    cab_path = sample_single_cab

    archive = cabfile.CabFile(str(cab_path))
    with archive:
        names = list(archive)
        assert names == ["hello.txt"]

        assert archive.read("hello.txt") == b"hello from cabfile\n"
        member, payload = next(archive.read_members(["hello.txt"]))
        assert member.name == "hello.txt"
        assert payload == b"hello from cabfile\n"


def test_generated_cab_extract(sample_multi_cab: Path, tmp_path: Path):
    cab_path = sample_multi_cab

    out_dir = tmp_path / "extracted"

    archive = cabfile.CabFile(str(cab_path))
    with archive:
        archive.extractall(str(out_dir))
        extracted = list(archive.extract_members(str(out_dir)))

    assert [member.name for member in extracted] == ["alpha.txt", "beta.txt", "gamma.txt"]

    assert (out_dir / "alpha.txt").read_bytes() == b"alpha\n"
    assert (out_dir / "beta.txt").read_bytes() == b"beta\n"
    assert (out_dir / "gamma.txt").read_bytes() == b"gamma\n"


def test_infolist_getinfo_and_multi_read(sample_multi_cab: Path):
    cab_path = sample_multi_cab

    archive = cabfile.CabFile(str(cab_path))
    with archive:
        infos = list(archive.values())
        assert len(infos) == 3

        names = [info.name for info in infos]
        assert names == ["alpha.txt", "beta.txt", "gamma.txt"]

        info_alpha = archive["alpha.txt"]
        assert info_alpha.size == len(b"alpha\n")

        assert "missing.txt" not in archive

        payloads = list(archive.read_members(["alpha.txt", "beta.txt", "gamma.txt"]))
        assert [(member.name, data) for member, data in payloads] == [
            ("alpha.txt", b"alpha\n"),
            ("beta.txt", b"beta\n"),
            ("gamma.txt", b"gamma\n"),
        ]

        all_payloads = list(archive.read_members())
        assert [(member.name, data) for member, data in all_payloads] == [
            ("alpha.txt", b"alpha\n"),
            ("beta.txt", b"beta\n"),
            ("gamma.txt", b"gamma\n"),
        ]


def test_extract_selected_names_only(sample_multi_cab: Path, tmp_path: Path):
    cab_path = sample_multi_cab

    out_dir = tmp_path / "selected"

    archive = cabfile.CabFile(str(cab_path))
    with archive:
        extracted = list(archive.extract_members(str(out_dir), ["beta.txt"]))

    assert [member.name for member in extracted] == ["beta.txt"]

    assert not (out_dir / "alpha.txt").exists()
    assert (out_dir / "beta.txt").read_bytes() == b"beta\n"
    assert not (out_dir / "gamma.txt").exists()


def test_file_object_inputs_and_testcabinet(sample_single_cab: Path):
    cab_path = sample_single_cab

    with cab_path.open("rb") as file_obj:
        archive = cabfile.CabFile(file_obj)
        with archive:
            assert list(archive) == ["hello.txt"]
            assert archive.read("hello.txt") == b"hello from cabfile\n"
            member, payload = next(archive.read_members(["hello.txt"]))
            assert member.name == "hello.txt"
            assert payload == b"hello from cabfile\n"
            assert archive.test() is True


def test_testcabinet_returns_false_for_truncated_file(truncated_cab: Path):
    truncated_path = truncated_cab

    archive = cabfile.CabFile(str(truncated_path))
    with archive:
        assert archive.test() is False
