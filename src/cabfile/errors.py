class CabFileError(RuntimeError):
    pass


class CabinetError(CabFileError):
    pass


class CabPlatformError(ImportError):
    pass


class CabStopIteration(CabFileError):
    pass
