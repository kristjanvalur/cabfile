from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def makecab_available() -> bool:
    return shutil.which("makecab") is not None or shutil.which("makecab.exe") is not None


def create_cab_with_makecab(work_dir: Path, cabinet_name: str, files: dict[str, bytes]) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    source_dir = work_dir / "src"
    source_dir.mkdir(parents=True, exist_ok=True)

    for filename, payload in files.items():
        source_file = source_dir / filename
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_bytes(payload)

    output_dir = work_dir / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    ddf_file = work_dir / "build.ddf"
    ddf_lines = [
        ".OPTION EXPLICIT",
        f".Set CabinetNameTemplate={cabinet_name}",
        f".Set DiskDirectoryTemplate={output_dir}",
        ".Set Cabinet=on",
        ".Set Compress=on",
        ".Set CompressionType=MSZIP",
        ".Set MaxDiskSize=0",
        ".Set CabinetFileCountThreshold=0",
        ".Set FolderFileCountThreshold=0",
        ".Set FolderSizeThreshold=0",
    ]
    for filename in files:
        ddf_lines.append(f'"{(source_dir / filename)}" "{filename}"')

    ddf_file.write_text("\n".join(ddf_lines) + "\n", encoding="utf-8")

    subprocess.run(["makecab", "/F", str(ddf_file)], check=True, capture_output=True, text=True)

    cabinet_path = output_dir / cabinet_name
    if not cabinet_path.exists():
        raise FileNotFoundError(f"makecab did not create expected cabinet: {cabinet_path}")

    return cabinet_path
