from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as DateTime


@dataclass(slots=True)
class CabMember:
    """Metadata for a cabinet member."""

    name: str | None = None
    datetime: DateTime | None = None
    size: int = 0
    attributes: int = 0

    @property
    def filename(self):
        return self.name

    @filename.setter
    def filename(self, value):
        self.name = value

    @property
    def file_size(self):
        return self.size

    @file_size.setter
    def file_size(self, value):
        self.size = value

    @property
    def external_attr(self):
        return self.attributes

    @external_attr.setter
    def external_attr(self, value):
        self.attributes = value

    def __repr__(self):
        return "<CabinetInfo %s, size=%s, date=%r, attrib=%x>" % (
            self.filename,
            self.file_size,
            self.datetime,
            self.external_attr,
        )


CabinetInfo = CabMember


@dataclass(slots=True)
class CabSummary:
    file_count: int
    folder_count: int
    set_id: int
    cabinet_index: int


def DecodeFATTime(FATdate, FATtime):
    """Convert FAT date/time bitfields to a ``datetime`` object."""
    day = FATdate & 0x1F
    month = (FATdate >> 5) & 0xF
    year = 1980 + (FATdate >> 9)
    sec = 2 * (FATtime & 0x1F)
    minute = (FATtime >> 5) & 0x3F
    hour = FATtime >> 11
    try:
        return DateTime(year, month, day, hour, minute, sec)
    except ValueError:
        return None
