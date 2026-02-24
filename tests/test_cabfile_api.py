from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

import cabfile


pytestmark = pytest.mark.requires_makecab


def test_cabfile_context_manager_and_read(single_cab_source):
    with cabfile.CabFile(single_cab_source) as archive:
        assert list(archive) == ["hello.txt"]
        read_member, payload = next(archive.read_members(["hello.txt"]))
        assert read_member.name == "hello.txt"
        assert payload == b"hello from cabfile\n"
        member = archive["hello.txt"]
        assert member is not None
        assert member.file_size == len(b"hello from cabfile\n")


def test_cabfile_members_and_read_many(multi_cab_source):
    with cabfile.CabFile(multi_cab_source) as archive:
        members = list(archive.values())
        assert [item.name for item in members] == ["alpha.txt", "beta.txt", "gamma.txt"]
        assert [item.filename for item in members] == ["alpha.txt", "beta.txt", "gamma.txt"]
        assert [item.size for item in members] == [len(b"alpha\n"), len(b"beta\n"), len(b"gamma\n")]
        assert [item.file_size for item in members] == [len(b"alpha\n"), len(b"beta\n"), len(b"gamma\n")]
        read_many = list(archive.read_members(["alpha.txt", "gamma.txt"]))
        assert [(member.name, data) for member, data in read_many] == [
            ("alpha.txt", b"alpha\n"),
            ("gamma.txt", b"gamma\n"),
        ]

        read_all = list(archive.read_members())
        assert [(member.name, data) for member, data in read_all] == [
            ("alpha.txt", b"alpha\n"),
            ("beta.txt", b"beta\n"),
            ("gamma.txt", b"gamma\n"),
        ]
        assert archive.test() is True


def test_cabfile_extract_and_extract_all(multi_cab_source, tmp_path: Path):
    selected_out = tmp_path / "selected"
    all_out = tmp_path / "all"

    with cabfile.CabFile(multi_cab_source) as archive:
        extracted_one = list(archive.extract_members(str(selected_out), ["beta.txt"]))
        extracted_many = list(archive.extract_members(str(all_out), ["alpha.txt", "gamma.txt"]))

    assert [member.name for member in extracted_one] == ["beta.txt"]
    assert [member.name for member in extracted_many] == ["alpha.txt", "gamma.txt"]

    assert not (selected_out / "alpha.txt").exists()
    assert (selected_out / "beta.txt").read_bytes() == b"beta\n"
    assert not (selected_out / "gamma.txt").exists()

    assert (all_out / "alpha.txt").read_bytes() == b"alpha\n"
    assert not (all_out / "beta.txt").exists()
    assert (all_out / "gamma.txt").read_bytes() == b"gamma\n"


def test_cabfile_mapping_metadata_interface(multi_cab_source):
    with cabfile.CabFile(multi_cab_source) as archive:
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


def test_cabfile_visit_with_and_without_data_and_abort(multi_cab_source):
    with cabfile.CabFile(multi_cab_source) as archive:
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


def test_cabfile_visit_cab_stop_iteration(multi_cab_source):
    with cabfile.CabFile(multi_cab_source) as archive:
        seen: list[str] = []

        def on_copy_file(member):
            assert member.name is not None
            seen.append(member.name)
            if member.name == "beta.txt":
                raise cabfile.CabStopIteration()
            return None

        assert archive.visit(on_copy_file) is False
        assert seen == ["alpha.txt", "beta.txt"]


def test_cabfile_visit_low_level_and_file_manager(multi_cab_source):
    with cabfile.CabFile(multi_cab_source) as archive:
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


def test_cabfile_visit_filelike_auto_mapping(multi_cab_source):
    class CaptureSink(BytesIO):
        def __init__(self):
            super().__init__()
            self.captured = b""

        def close(self):
            if not self.closed:
                self.captured = self.getvalue()
            super().close()

    with cabfile.CabFile(multi_cab_source) as archive:
        sink = CaptureSink()

        def on_copy_file(member):
            if member.name == "gamma.txt":
                return sink, sink.close
            return None

        assert archive.visit(on_copy_file) is True
        assert sink.closed
        assert sink.captured == b"gamma\n"


def test_cabfile_visit_filelike_with_on_close(multi_cab_source):
    class CaptureSink(BytesIO):
        def __init__(self):
            super().__init__()
            self.captured = b""

        def close(self):
            if not self.closed:
                self.captured = self.getvalue()
            super().close()

    with cabfile.CabFile(multi_cab_source) as archive:
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


def test_probe_and_is_cabinet(sample_single_cab: Path, truncated_cab: Path):
    assert cabfile.is_cabinet(str(sample_single_cab)) is True

    with sample_single_cab.open("rb") as source:
        assert cabfile.is_cabinet(source) is True

    summary = cabfile.probe(str(sample_single_cab))
    assert summary.file_count == 1
    assert summary.folder_count >= 1
    assert summary.set_id >= 0
    assert summary.cabinet_index >= 0

    assert cabfile.is_cabinet(str(truncated_cab)) is False
    with pytest.raises(cabfile.CabinetError):
        cabfile.probe(str(truncated_cab))
