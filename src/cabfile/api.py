from __future__ import annotations

from collections.abc import Iterable, Iterator
from os import PathLike
from types import TracebackType
from typing import BinaryIO, Self

from .core import CabinetFile, is_cabinetfile, main
from .errors import CabFileError, CabPlatformError, CabinetError
from .models import CabinetInfo, DecodeFATTime

CabSource = str | PathLike[str] | BinaryIO
CabTargetDir = str | PathLike[str]


class CabFile:
    def __init__(self, source: CabSource):
        self._archive: CabinetFile
        self._archive = CabinetFile(source)

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

    def close(self) -> None:
        self._archive.close()

    def names(self) -> Iterator[str]:
        return iter(self._archive.namelist())

    def members(self) -> Iterator[CabinetInfo]:
        return iter(self._archive.infolist())

    def get_member(self, name: str) -> CabinetInfo | None:
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
