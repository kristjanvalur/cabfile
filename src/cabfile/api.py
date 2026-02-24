from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from ctypes import byref
from io import BytesIO
import sys
from os import PathLike
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Self

from .core import (
    CabinetFile,
    ERF,
    FDICopy,
    FDICreate,
    FDIDestroy,
    FDIAllocator,
    FDIFileManager,
    FileManager,
    PFNFDINOTIFY,
    _to_text,
    fdintCABINET_INFO,
    fdintCLOSE_FILE_INFO,
    fdintCOPY_FILE,
    fdintENUMERATE,
    is_cabinetfile,
    main,
)
from .errors import CabFileError, CabPlatformError, CabStopIteration, CabinetError
from .models import CabMember, CabinetInfo, DecodeFATTime

CabSource = str | PathLike[str] | BinaryIO
CabTargetDir = str | PathLike[str]
VisitOnDone = Callable[[], None]
VisitCopyResult = tuple[BinaryIO, VisitOnDone] | None
VisitCopyCallback = Callable[[CabMember], VisitCopyResult]


class CabFile:
    def __init__(self, source: CabSource):
        self._source = source
        self._allocator: FDIAllocator = FDIAllocator()
        self._error_state: ERF = ERF()
        self._file_manager: FDIFileManager
        self._file_manager = FileManager(self._source)
        self._fdi_handle = None

    def _open(self) -> None:
        if self._fdi_handle:
            return

        self._fdi_handle = FDICreate(
            self._allocator.malloc,
            self._allocator.free,
            self._file_manager.open,
            self._file_manager.read,
            self._file_manager.write,
            self._file_manager.close_cb,
            self._file_manager.seek,
            0,
            byref(self._error_state),
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        self.close()
        return False

    def __del__(self):
        if FDIDestroy and hasattr(self, "_fdi_handle"):
            self.close()

    def close(self) -> None:
        if self._fdi_handle:
            FDIDestroy(self._fdi_handle)
            self._fdi_handle = None

    @property
    def file_manager(self):
        """Low-level FDI file manager for map/unmap and callback-backed I/O."""
        return self._file_manager

    def visit(
        self,
        on_copy_file: VisitCopyCallback,
    ) -> bool:
        """Low-level FDICopy visit API.

        For each member (``fdintCOPY_FILE``), ``on_copy_file`` is called with a
        ``CabMember`` instance.

        - Return ``None`` to skip member data copy.
        - Return ``(file_like, on_done)`` where ``file_like`` is writable and
                    ``on_done()`` runs after data is written and unmapped. The callback
                    owns finalization, including closing/reusing the file-like object.

        Raise ``CabStopIteration`` to stop traversal early. Returns ``False`` for
        early-stop, ``True`` otherwise.
        """
        self._open()
        pending_by_fd: dict[int, tuple[BinaryIO, Callable[[], None]]] = {}
        callback_exception = []

        def on_notify(fdint, pnotify):
            notify = pnotify.contents
            if fdint in [fdintCABINET_INFO, fdintENUMERATE]:
                return 0
            if fdint == fdintCOPY_FILE:
                member = CabMember(_to_text(notify.psz1), DecodeFATTime(notify.date, notify.time))
                member.file_size = notify.cb
                member.external_attr = notify.attribs

                result = on_copy_file(member)

                if result is None:
                    return 0

                file_like, on_done = result

                fd = self.file_manager.map(file_like)
                pending_by_fd[int(fd)] = (file_like, on_done)
                return fd

            if fdint == fdintCLOSE_FILE_INFO:
                fd = int(notify.hf)
                pending_entry = pending_by_fd.pop(fd, None)
                if pending_entry is None:
                    return 1
                self.file_manager.unmap(fd)
                _, on_done = pending_entry
                on_done()
                return 1
            return -1

        def wrap(fdint, pnotify):
            try:
                return on_notify(fdint, pnotify)
            except Exception:
                callback_exception[:] = sys.exc_info()
                return -1

        self._error_state.clear()
        notify_callback = PFNFDINOTIFY(wrap)
        try:
            result = FDICopy(
                self._fdi_handle,
                self.file_manager.encoded_cabinet_name,
                self.file_manager.encoded_cabinet_dir,
                0,
                notify_callback,
                None,
                None,
            )
            if not result:
                if callback_exception:
                    if isinstance(callback_exception[1], CabStopIteration):
                        return False
                    raise callback_exception[1]
                self.file_manager.raise_error()
                self._error_state.raise_error()
            return True
        finally:
            self.file_manager.close()

    def __iter__(self) -> Iterator[str]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self.keys())

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        found = False

        def on_copy_file(member: CabMember):
            nonlocal found
            if member.name != name:
                return None
            found = True
            raise CabStopIteration()

        self.visit(on_copy_file)
        return found

    def __getitem__(self, name: str) -> CabMember:
        member: CabMember | None = None

        def on_copy_file(current: CabMember):
            nonlocal member
            if current.name != name:
                return None
            member = current
            raise CabStopIteration()

        self.visit(on_copy_file)
        if member is None:
            raise KeyError(name)
        return member

    def keys(self) -> Iterable[str]:
        """Return member names in cabinet order."""
        names: list[str] = []

        def on_copy_file(member: CabMember):
            if member.name is not None:
                names.append(member.name)
            return None

        self.visit(on_copy_file)
        return names

    def values(self) -> Iterable[CabMember]:
        """Return member metadata objects in cabinet order."""
        members: list[CabMember] = []

        def on_copy_file(member: CabMember):
            members.append(member)
            return None

        self.visit(on_copy_file)
        return members

    def items(self) -> Iterable[tuple[str, CabMember]]:
        """Return ``(name, member)`` pairs in cabinet order."""
        items: list[tuple[str, CabMember]] = []

        def on_copy_file(member: CabMember):
            if member.name is not None:
                items.append((member.name, member))
            return None

        self.visit(on_copy_file)
        return items

    def read(self, name: str) -> tuple[CabMember, bytes]:
        """Read a single member payload by name.

        Raises ``KeyError`` when the member is not present.
        """
        result: tuple[CabMember, bytes] | None = None

        def on_copy_file(member: CabMember):
            if member.name != name:
                return None

            sink = BytesIO()

            def on_done() -> None:
                nonlocal result
                result = (member, sink.getvalue())
                sink.close()
                raise CabStopIteration()

            return sink, on_done

        self.visit(on_copy_file)
        if result is None:
            raise KeyError(name)
        return result

    def read_many(self, names: Iterable[str]) -> Iterator[tuple[CabMember, bytes]]:
        """Yield ``(member, payload)`` for requested names that exist.

        Output follows cabinet traversal order.
        """
        requested_set = set(names)
        if not requested_set:
            return iter(())

        entries: list[tuple[CabMember, bytes]] = []

        def on_copy_file(member: CabMember):
            if member.name is None or member.name not in requested_set:
                return None

            sink = BytesIO()

            def on_done() -> None:
                entries.append((member, sink.getvalue()))
                sink.close()

            return sink, on_done

        self.visit(on_copy_file)

        return iter(entries)

    def read_all(self) -> Iterator[tuple[CabMember, bytes]]:
        """Yield ``(member, payload)`` for all members in cabinet order."""
        entries: list[tuple[CabMember, bytes]] = []

        def on_copy_file(member: CabMember):
            sink = BytesIO()

            def on_done() -> None:
                entries.append((member, sink.getvalue()))
                sink.close()

            return sink, on_done

        self.visit(on_copy_file)
        return iter(entries)

    def extract(self, name: str, target_dir: CabTargetDir) -> CabMember:
        """Extract one member to ``target_dir``.

        Raises ``KeyError`` when the member is not present.
        """
        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        extracted: CabMember | None = None

        def on_copy_file(member: CabMember):
            if member.name != name:
                return None

            destination = out_dir / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            output_file = destination.open("wb")

            def on_done() -> None:
                nonlocal extracted
                extracted = member
                output_file.close()
                raise CabStopIteration()

            return output_file, on_done

        self.visit(on_copy_file)
        if extracted is None:
            raise KeyError(name)
        return extracted

    def extract_all(self, target_dir: CabTargetDir, members: Iterable[str] | None = None) -> Iterable[CabMember]:
        """Extract all members, or only selected ``members``, and return extracted metadata."""
        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        selected = set(members) if members is not None else None
        extracted_members: list[CabMember] = []

        def on_copy_file(member: CabMember):
            if member.name is None:
                return None
            if selected is not None and member.name not in selected:
                return None

            destination = out_dir / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            output_file = destination.open("wb")

            def on_done() -> None:
                extracted_members.append(member)
                output_file.close()

            return output_file, on_done

        self.visit(on_copy_file)
        return iter(extracted_members)

    def test(self) -> bool:
        """Test cabinet readability by copying all member data to a null sink."""
        try:
            def on_copy_file(_member: CabMember):
                sink = BytesIO()

                def on_done() -> None:
                    sink.close()

                return sink, on_done

            self.visit(on_copy_file)
            return True
        except (CabinetError, IOError, OSError):
            return False

__all__ = [
    "CabinetError",
    "CabFileError",
    "CabFile",
    "CabPlatformError",
    "CabStopIteration",
    "CabinetFile",
    "CabinetInfo",
    "DecodeFATTime",
    "is_cabinetfile",
    "main",
]
