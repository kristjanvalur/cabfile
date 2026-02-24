class CabinetInfo(object):
    """A simple class to encapsulate information about cabinet members"""

    def __init__(self, filename=None, date_time=None):
        self.filename, self.date_time = filename, date_time
        self.file_size = 0
        self.external_attr = 0

    def __repr__(self):
        return "<CabinetInfo %s, size=%s, date=%r, attrib=%x>" % (
            self.filename,
            self.file_size,
            self.date_time,
            self.external_attr,
        )


def DecodeFATTime(FATdate, FATtime):
    """Convert the 2x16 bits of time in the FAT system to a tuple"""
    day = FATdate & 0x1F
    month = (FATdate >> 5) & 0xF
    year = 1980 + (FATdate >> 9)
    sec = 2 * (FATtime & 0x1F)
    minute = (FATtime >> 5) & 0x3F
    hour = FATtime >> 11
    return (year, month, day, hour, minute, sec)
