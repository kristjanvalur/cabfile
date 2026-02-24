import cabfile


def test_module_imports():
    assert hasattr(cabfile, "CabinetFile")
    assert hasattr(cabfile, "CabFile")
