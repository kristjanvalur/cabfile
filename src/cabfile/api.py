from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from ctypes import byref
from io import BytesIO
import os.path
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


class CabFile:
    def __init__(self, source: CabSource):
        self._source = source
        self._a: FDIAllocator | None = None
        self._e: ERF | None = None
        self._f = None
        self._head: bytes | None = None
        self._tail: bytes | None = None
        self._hfdi = None

    def _open(self) -> None:
        if self._hfdi:
            return

        self._a = FDIAllocator()
        self._e = ERF()
        self._f, filename = FileManager(self._source)

        head, tail = os.path.split(os.path.normpath(filename))
        if head:
            head += "\\"
        if isinstance(head, str):
            head = head.encode(sys.getfilesystemencoding(), errors="surrogateescape")
        if isinstance(tail, str):
            tail = tail.encode(sys.getfilesystemencoding(), errors="surrogateescape")

        self._head = head
        self._tail = tail
        self._hfdi = FDICreate(
            self._a.malloc,
            self._a.free,
            self._f.open,
            self._f.read,
            self._f.write,
            self._f.close_cb,
            self._f.seek,
            0,
            byref(self._e),
        )

    def _close_native(self) -> None:
        hfdi = getattr(self, "_hfdi", None)
        if hfdi:
            FDIDestroy(hfdi)
            self._hfdi = None

    def _fdicopy_native(self, callback, err_success: Callable[[], bool] | None = None) -> int:
        self._open()
        excinfo = []

        def wrap(fdint, pnotify):
            try:
                return callback(fdint, pnotify)
            except Exception:
                excinfo[:] = sys.exc_info()
                return -1

        self._e.clear()
        notify_callback = PFNFDINOTIFY(wrap)
        try:
            result = FDICopy(self._hfdi, self._tail, self._head, 0, notify_callback, None, None)
            if not result:
                if excinfo:
                    raise excinfo[1]
                self._f.raise_error()
                if err_success is not None and err_success():
                    return result
                self._e.raise_error()
            return result
        finally:
            self._f.close()

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
        if FDIDestroy and hasattr(self, "_hfdi"):
            self.close()

    def close(self) -> None:
        self._close_native()

    def _fdicopy_dispatch(
        self,
        on_copy_file: Callable[[CabMember], tuple[int, Callable[[], None]] | None],
    ) -> bool:
        aborted = False
        pending: dict[int, Callable[[], None]] = {}

        def on_notify(fdint, pnotify):
            nonlocal aborted
            notify = pnotify.contents
            if fdint in [fdintCABINET_INFO, fdintENUMERATE]:
                return 0
            if fdint == fdintCOPY_FILE:
                member = CabMember(_to_text(notify.psz1), DecodeFATTime(notify.date, notify.time))
                member.file_size = notify.cb
                member.external_attr = notify.attribs

                try:
                    result = on_copy_file(member)
                except CabStopIteration:
                    aborted = True
                    return -1

                if result is None:
                    return 0

                fd, on_close_file = result
                pending[int(fd)] = on_close_file
                return fd

            if fdint == fdintCLOSE_FILE_INFO:
                fd = int(notify.hf)
                on_close_file = pending.pop(fd, None)
                if on_close_file is None:
                    return 1
                try:
                    on_close_file()
                except CabStopIteration:
                    aborted = True
                    return -1
                return 1
            return -1

        self._fdicopy_native(on_notify, err_success=lambda: aborted)
        return not aborted

    def _fdicopy_visit_native(
        self,
        callback: Callable[[CabMember, bytes | None], bool | None],
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
            fd = self._f.map(sink)

            def on_close_file() -> None:
                mapped_sink = self._f.unmap(fd)
                data = mapped_sink.getvalue()
                mapped_sink.close()
                if callback(member, data) is False:
                    raise CabStopIteration()

            return fd, on_close_file

        return self._fdicopy_dispatch(on_copy_file)

    def visit(
        self,
        callback: Callable[[CabMember, bytes | None], bool | None],
        *,
        with_data: bool = False,
    ) -> bool:
        return self._fdicopy_visit_native(callback, with_data=with_data)

    def walk(
        self,
        callback: Callable[[CabMember, bytes | None], bool | None],
        *,
        with_data: bool = False,
    ) -> bool:
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

        self._fdicopy_visit_native(
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

        self._fdicopy_visit_native(
            callback,
            with_data=False,
            predicate=lambda current: current.name == name,
        )
        if member is None:
            raise KeyError(name)
        return member

    def keys(self) -> Iterable[str]:
        names: list[str] = []

        def callback(member: CabMember, _data: bytes | None) -> bool:
            if member.name is not None:
                names.append(member.name)
            return True

        self.visit(callback)
        return names

    def values(self) -> Iterable[CabMember]:
        members: list[CabMember] = []

        def callback(member: CabMember, _data: bytes | None) -> bool:
            members.append(member)
            return True

        self.visit(callback)
        return members

    def items(self) -> Iterable[tuple[str, CabMember]]:
        items: list[tuple[str, CabMember]] = []

        def callback(member: CabMember, _data: bytes | None) -> bool:
            if member.name is not None:
                items.append((member.name, member))
            return True

        self.visit(callback)
        return items

    def read(self, name: str) -> bytes:
        payload: bytes | None = None

        def callback(_member: CabMember, data: bytes | None) -> bool:
            nonlocal payload
            payload = data
            return False

        self._fdicopy_visit_native(
            callback,
            with_data=True,
            predicate=lambda member: member.name == name,
        )
        if payload is None:
            raise KeyError(name)
        return payload

    def read_many(self, names: Iterable[str]) -> Iterator[tuple[str, bytes]]:
        requested_names = list(names)
        if not requested_names:
            return iter(())

        requested_set = set(requested_names)
        by_name: dict[str, bytes] = {}

        def callback(member: CabMember, data: bytes | None) -> bool:
            if member.name is not None and data is not None:
                by_name[member.name] = data
            return True

        self._fdicopy_visit_native(
            callback,
            with_data=True,
            predicate=lambda member: member.name in requested_set,
        )

        return iter((name, by_name[name]) for name in requested_names if name in by_name)

    def extract(self, name: str, target_dir: CabTargetDir) -> None:
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

        self._fdicopy_visit_native(
            callback,
            with_data=True,
            predicate=lambda member: member.name == name,
        )
        if not wrote:
            raise KeyError(name)

    def extract_all(self, target_dir: CabTargetDir, members: Iterable[str] | None = None) -> None:
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

        self._fdicopy_visit_native(
            callback,
            with_data=True,
            predicate=None if selected is None else (lambda member: member.name in selected),
        )

    def test(self) -> bool:
        return self.visit(lambda _member, _data: True, with_data=True)

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
