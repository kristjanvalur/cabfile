from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CabMember:
    """Metadata for a cabinet member."""

    name: str | None = None
    date_time: tuple[int, int, int, int, int, int] | None = None
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
            self.date_time,
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
    """Convert the 2x16 bits of time in the FAT system to a tuple"""
    day = FATdate & 0x1F
    month = (FATdate >> 5) & 0xF
    year = 1980 + (FATdate >> 9)
    sec = 2 * (FATtime & 0x1F)
    minute = (FATtime >> 5) & 0x3F
    hour = FATtime >> 11
    return (year, month, day, hour, minute, sec)
