from __future__ import annotations

from io import BytesIO
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


def test_cabfile_visit_with_and_without_data_and_abort(sample_multi_cab: Path):
    with cabfile.CabFile(str(sample_multi_cab)) as archive:
        seen_names: list[str] = []

        def on_copy_name(member):
            assert member.name is not None
            seen_names.append(member.name)
            return None

        assert archive.visit(on_copy_name) is True
        assert seen_names == ["alpha.txt", "beta.txt", "gamma.txt"]

        seen_with_data: list[tuple[str, bytes]] = []

        def on_copy_file(member):
            assert member.name is not None
            sink = BytesIO()

            def on_done():
                seen_with_data.append((member.name, sink.getvalue()))
                sink.close()

            return sink, on_done

        assert archive.visit(on_copy_file) is True
        assert seen_with_data == [
            ("alpha.txt", b"alpha\n"),
            ("beta.txt", b"beta\n"),
            ("gamma.txt", b"gamma\n"),
        ]

        seen_abort: list[str] = []

        def aborting_copy(member):
            assert member.name is not None
            seen_abort.append(member.name)
            if member.name == "beta.txt":
                raise cabfile.CabStopIteration()
            return None

        assert archive.visit(aborting_copy) is False
        assert seen_abort == ["alpha.txt", "beta.txt"]


def test_cabfile_visit_cab_stop_iteration(sample_multi_cab: Path):
    with cabfile.CabFile(str(sample_multi_cab)) as archive:
        seen: list[str] = []

        def on_copy_file(member):
            assert member.name is not None
            seen.append(member.name)
            if member.name == "beta.txt":
                raise cabfile.CabStopIteration()
            return None

        assert archive.visit(on_copy_file) is False
        assert seen == ["alpha.txt", "beta.txt"]


def test_cabfile_visit_low_level_and_file_manager(sample_multi_cab: Path):
    with cabfile.CabFile(str(sample_multi_cab)) as archive:
        names: list[str] = []

        def on_copy_file(member):
            assert member.name is not None
            names.append(member.name)
            return None

        assert archive.visit(on_copy_file) is True
        assert names == ["alpha.txt", "beta.txt", "gamma.txt"]

        payloads: dict[str, bytes] = {}

        class CaptureSink(BytesIO):
            def __init__(self, member_name: str):
                super().__init__()
                self.member_name = member_name

            def close(self):
                if not self.closed:
                    payloads[self.member_name] = self.getvalue()
                super().close()

        def on_copy_file_with_data(member):
            assert member.name is not None
            if member.name != "beta.txt":
                return None

            sink = CaptureSink(member.name)

            def on_done():
                sink.close()

            return sink, on_done

        assert archive.visit(on_copy_file_with_data) is True
        assert payloads == {"beta.txt": b"beta\n"}

        manager = archive.file_manager
        temp = BytesIO()
        with manager.mapped(temp) as fd:
            assert fd in manager.filemap
        assert fd not in manager.filemap
        assert temp.closed


def test_cabfile_visit_filelike_auto_mapping(sample_multi_cab: Path):
    class CaptureSink(BytesIO):
        def __init__(self):
            super().__init__()
            self.captured = b""

        def close(self):
            if not self.closed:
                self.captured = self.getvalue()
            super().close()

    with cabfile.CabFile(str(sample_multi_cab)) as archive:
        sink = CaptureSink()

        def on_copy_file(member):
            if member.name == "gamma.txt":
                return sink, sink.close
            return None

        assert archive.visit(on_copy_file) is True
        assert sink.closed
        assert sink.captured == b"gamma\n"


def test_cabfile_visit_filelike_with_on_close(sample_multi_cab: Path):
    class CaptureSink(BytesIO):
        def __init__(self):
            super().__init__()
            self.captured = b""

        def close(self):
            if not self.closed:
                self.captured = self.getvalue()
            super().close()

    with cabfile.CabFile(str(sample_multi_cab)) as archive:
        sink = CaptureSink()
        closed = False

        def on_copy_file(member):
            if member.name != "alpha.txt":
                return None

            def on_close():
                nonlocal closed
                closed = True
                sink.close()

            return sink, on_close

        assert archive.visit(on_copy_file) is True
        assert sink.closed
        assert sink.captured == b"alpha\n"
        assert closed is True
