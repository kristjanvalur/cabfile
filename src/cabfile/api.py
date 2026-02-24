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
DispatchOnDone = Callable[[], None]
DispatchCopyResult = tuple[BinaryIO, DispatchOnDone] | None
DispatchCopyCallback = Callable[[CabMember], DispatchCopyResult]
VisitCallback = Callable[[CabMember, bytes | None], bool | None]


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

    def dispatch(
        self,
        on_copy_file: DispatchCopyCallback,
    ) -> bool:
        """Low-level FDICopy dispatch API.

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
                mapped = self.file_manager.unmap(fd)
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

    def _fdicopy_visit(
        self,
        callback: VisitCallback,
        *,
        with_data: bool,
        predicate: Callable[[CabMember], bool] | None = None,
    ) -> bool:
        def on_copy_file(member: CabMember):
            if predicate is not None and not predicate(member):
                return None

            if not with_data:
                if callback(member, None) is False:
                    raise CabStopIteration()
                return None

            sink = BytesIO()

            def on_done() -> None:
                try:
                    if callback(member, sink.getvalue()) is False:
                        raise CabStopIteration()
                finally:
                    sink.close()

            return sink, on_done

        return self.dispatch(on_copy_file)

    def visit(
        self,
        callback: VisitCallback,
        *,
        with_data: bool = False,
    ) -> bool:
        """Visit each member and invoke ``callback(member, data_or_none)``.

        Returns ``False`` when traversal is stopped early (callback returns
        ``False`` or raises ``CabStopIteration``), otherwise ``True``.
        """
        return self._fdicopy_visit(callback, with_data=with_data)

    def walk(
        self,
        callback: VisitCallback,
        *,
        with_data: bool = False,
    ) -> bool:
        """Alias for ``visit()``."""
        return self.visit(callback, with_data=with_data)

    def __iter__(self) -> Iterator[str]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self.keys())

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        found = False

        def callback(member: CabMember, _data: bytes | None) -> bool:
            nonlocal found
            found = member.name == name
            return not found

        self._fdicopy_visit(
            callback,
            with_data=False,
            predicate=lambda member: member.name == name,
        )
        return found

    def __getitem__(self, name: str) -> CabMember:
        member: CabMember | None = None

        def callback(current: CabMember, _data: bytes | None) -> bool:
            nonlocal member
            member = current
            return False

        self._fdicopy_visit(
            callback,
            with_data=False,
            predicate=lambda current: current.name == name,
        )
        if member is None:
            raise KeyError(name)
        return member

    def keys(self) -> Iterable[str]:
        """Return member names in cabinet order."""
        names: list[str] = []

        def callback(member: CabMember, _data: bytes | None) -> bool:
            if member.name is not None:
                names.append(member.name)
            return True

        self.visit(callback)
        return names

    def values(self) -> Iterable[CabMember]:
        """Return member metadata objects in cabinet order."""
        members: list[CabMember] = []

        def callback(member: CabMember, _data: bytes | None) -> bool:
            members.append(member)
            return True

        self.visit(callback)
        return members

    def items(self) -> Iterable[tuple[str, CabMember]]:
        """Return ``(name, member)`` pairs in cabinet order."""
        items: list[tuple[str, CabMember]] = []

        def callback(member: CabMember, _data: bytes | None) -> bool:
            if member.name is not None:
                items.append((member.name, member))
            return True

        self.visit(callback)
        return items

    def read(self, name: str) -> bytes:
        """Read a single member payload by name.

        Raises ``KeyError`` when the member is not present.
        """
        payload: bytes | None = None

        def callback(_member: CabMember, data: bytes | None) -> bool:
            nonlocal payload
            payload = data
            return False

        self._fdicopy_visit(
            callback,
            with_data=True,
            predicate=lambda member: member.name == name,
        )
        if payload is None:
            raise KeyError(name)
        return payload

    def read_many(self, names: Iterable[str]) -> Iterator[tuple[str, bytes]]:
        """Yield ``(name, payload)`` for requested names that exist.

        Output preserves the caller-provided ``names`` ordering.
        """
        requested_names = list(names)
        if not requested_names:
            return iter(())

        requested_set = set(requested_names)
        by_name: dict[str, bytes] = {}

        def callback(member: CabMember, data: bytes | None) -> bool:
            if member.name is not None and data is not None:
                by_name[member.name] = data
            return True

        self._fdicopy_visit(
            callback,
            with_data=True,
            predicate=lambda member: member.name in requested_set,
        )

        return iter((name, by_name[name]) for name in requested_names if name in by_name)

    def extract(self, name: str, target_dir: CabTargetDir) -> None:
        """Extract one member to ``target_dir``.

        Raises ``KeyError`` when the member is not present.
        """
        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        wrote = False

        def callback(member: CabMember, data: bytes | None) -> bool:
            nonlocal wrote
            if member.name is None or data is None:
                return True
            destination = out_dir / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            wrote = True
            return False

        self._fdicopy_visit(
            callback,
            with_data=True,
            predicate=lambda member: member.name == name,
        )
        if not wrote:
            raise KeyError(name)

    def extract_all(self, target_dir: CabTargetDir, members: Iterable[str] | None = None) -> None:
        """Extract all members, or only the selected ``members``, to ``target_dir``."""
        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        selected = set(members) if members is not None else None

        def callback(member: CabMember, data: bytes | None) -> bool:
            if member.name is None or data is None:
                return True
            destination = out_dir / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            return True

        self._fdicopy_visit(
            callback,
            with_data=True,
            predicate=None if selected is None else (lambda member: member.name in selected),
        )

    def test(self) -> bool:
        """Test cabinet readability by visiting all members with data."""
        try:
            return self.visit(lambda _member, _data: True, with_data=True)
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
