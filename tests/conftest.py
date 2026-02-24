from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.cab_tools import create_cab_with_makecab, makecab_available


TMP_ROOT = Path("tmp")
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def pytest_runtest_setup(item):
    if item.get_closest_marker("requires_makecab") and not makecab_available():
        pytest.skip("makecab.exe is required for CAB fixture generation")


@pytest.fixture
def sample_single_cab() -> Iterator[Path]:
    work_dir = Path(tempfile.mkdtemp(prefix="cabfile-single-", dir=TMP_ROOT))
    try:
        yield create_cab_with_makecab(
            work_dir,
            "single.cab",
            {"hello.txt": b"hello from cabfile\n"},
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@pytest.fixture
def sample_multi_cab() -> Iterator[Path]:
    work_dir = Path(tempfile.mkdtemp(prefix="cabfile-multi-", dir=TMP_ROOT))
    try:
        yield create_cab_with_makecab(
            work_dir,
            "multi.cab",
            {
                "alpha.txt": b"alpha\n",
                "beta.txt": b"beta\n",
                "gamma.txt": b"gamma\n",
            },
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@pytest.fixture
def truncated_cab(sample_single_cab: Path) -> Iterator[Path]:
    work_dir = Path(tempfile.mkdtemp(prefix="cabfile-truncated-", dir=TMP_ROOT))
    try:
        output = work_dir / "truncated.cab"
        data = sample_single_cab.read_bytes()
        output.write_bytes(data[: max(1, len(data) // 3)])
        yield output
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@pytest.fixture(params=["path", "fileobj"], ids=["path", "fileobj"])
def cab_source_kind(request):
    return request.param


@pytest.fixture
def single_cab_source(sample_single_cab: Path, cab_source_kind: str):
    if cab_source_kind == "path":
        yield str(sample_single_cab)
        return

    file_obj = sample_single_cab.open("rb")
    try:
        yield file_obj
    finally:
        file_obj.close()


@pytest.fixture
def multi_cab_source(sample_multi_cab: Path, cab_source_kind: str):
    if cab_source_kind == "path":
        yield str(sample_multi_cab)
        return

    file_obj = sample_multi_cab.open("rb")
    try:
        yield file_obj
    finally:
        file_obj.close()
