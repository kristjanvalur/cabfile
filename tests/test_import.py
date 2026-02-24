import cabfile


def test_module_imports():
    assert hasattr(cabfile, "CabFile")
    assert not hasattr(cabfile, "CabinetFile")
