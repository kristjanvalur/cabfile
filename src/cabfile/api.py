from __future__ import annotations

from collections.abc import Iterable, Iterator
from ctypes import byref
import os.path
import sys
from os import PathLike
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
    fdintCOPY_FILE,
    fdintENUMERATE,
    is_cabinetfile,
    main,
)
from .errors import CabFileError, CabPlatformError, CabinetError
from .models import CabMember, CabinetInfo, DecodeFATTime

CabSource = str | PathLike[str] | BinaryIO
CabTargetDir = str | PathLike[str]


class CabFile:
    def __init__(self, source: CabSource):
        self._archive: CabinetFile
        self._archive = CabinetFile(source)
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
            self._f.close,
            self._f.seek,
            0,
            byref(self._e),
        )

    def _close_native(self) -> None:
        hfdi = getattr(self, "_hfdi", None)
        if hfdi:
            FDIDestroy(hfdi)
            self._hfdi = None

    def _fdicopy_native(self, callback) -> int:
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
        result = FDICopy(self._hfdi, self._tail, self._head, 0, notify_callback, None, None)
        if not result:
            if excinfo:
                raise excinfo[1]
            self._f.raise_error()
            self._e.raise_error()
        return result

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
        if FDIDestroy and (hasattr(self, "_archive") or hasattr(self, "_hfdi")):
            self.close()

    def close(self) -> None:
        self._close_native()
        archive = getattr(self, "_archive", None)
        if archive is not None:
            archive.close()

    def names(self) -> Iterator[str]:
        names: list[str] = []

        def callback(fdint, pnotify):
            notify = pnotify.contents
            if fdint in [fdintCABINET_INFO, fdintENUMERATE]:
                return 0
            if fdint == fdintCOPY_FILE:
                names.append(_to_text(notify.psz1))
                return 0
            return -1

        self._fdicopy_native(callback)
        return iter(names)

    def members(self) -> Iterator[CabMember]:
        infos: list[CabMember] = []

        def callback(fdint, pnotify):
            notify = pnotify.contents
            if fdint in [fdintCABINET_INFO, fdintENUMERATE]:
                return 0
            if fdint == fdintCOPY_FILE:
                info = CabinetInfo(_to_text(notify.psz1), DecodeFATTime(notify.date, notify.time))
                info.file_size = notify.cb
                info.external_attr = notify.attribs
                infos.append(info)
                return 0
            return -1

        self._fdicopy_native(callback)
        return iter(infos)

    def get_member(self, name: str) -> CabMember | None:
        return self._archive.getinfo(name)

    def read(self, name: str) -> bytes:
        return self._archive.read(name)

    def read_many(self, names: Iterable[str]) -> Iterator[tuple[str, bytes]]:
        requested_names = list(names)
        if not requested_names:
            return iter(())

        requested_set = set(requested_names)
        archive_order_names = [
            name for name in self._archive.namelist() if name in requested_set
        ]
        payloads = self._archive.read(archive_order_names)
        by_name = dict(zip(archive_order_names, payloads))

        return iter((name, by_name[name]) for name in requested_names if name in by_name)

    def extract(self, name: str, target_dir: CabTargetDir) -> None:
        self._archive.extract(target_dir, names=[name])

    def extract_all(self, target_dir: CabTargetDir, members: Iterable[str] | None = None) -> None:
        selected = list(members) if members is not None else None
        self._archive.extract(target_dir, names=selected)

    def test(self) -> bool:
        return self._archive.testcabinet()

__all__ = [
    "CabinetError",
    "CabFileError",
    "CabFile",
    "CabPlatformError",
    "CabinetFile",
    "CabinetInfo",
    "DecodeFATTime",
    "is_cabinetfile",
    "main",
]
