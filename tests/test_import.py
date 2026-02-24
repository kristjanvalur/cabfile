import cabfile


def test_module_imports():
    assert hasattr(cabfile, "CabFile")
    assert not hasattr(cabfile, "CabinetFile")
    assert hasattr(cabfile, "is_cabinet")
    assert hasattr(cabfile, "probe")
    assert not hasattr(cabfile, "is_cabinetfile")
