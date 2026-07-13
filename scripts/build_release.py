#!/usr/bin/env python3
"""Build six standalone Lab ZIPs and the complete course release archive."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = SCRIPT_DIR.parent
EXPECTED_LABS = (
    "Lab01_W1_W2",
    "Lab02_W3_W4",
    "Lab03_W5_W6",
    "Lab04_W7_W8",
    "Lab05_W9_W10",
    "Lab06_W11_W12",
)
EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    ".Xil",
    "__pycache__",
    "artifacts",
    "build",
    "demo_results",
}
EXCLUDED_SUFFIXES = {
    ".bit",
    ".dcp",
    ".hwh",
    ".jou",
    ".log",
    ".pyc",
    ".pyo",
    ".str",
    ".vvp",
    ".wdb",
    ".xsa",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def eligible(path: Path, base: Path, *, include_lab_packages: bool) -> bool:
    relative = path.relative_to(base)
    if any(part in EXCLUDED_DIRS for part in relative.parts[:-1]):
        return False
    if not include_lab_packages and "lab_packages" in relative.parts:
        return False
    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    if path.name.endswith(".orig") or path.name.endswith("~"):
        return False
    return path.is_file()


def add_tree(
    archive: zipfile.ZipFile,
    source: Path,
    archive_root: Path,
    *,
    include_lab_packages: bool,
) -> int:
    count = 0
    for path in sorted(source.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not eligible(path, source, include_lab_packages=include_lab_packages):
            continue
        archive.write(path, (archive_root / path.relative_to(source)).as_posix())
        count += 1
    return count


def checked_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP CRC check failed at {bad}: {path}")
        if not archive.namelist():
            raise RuntimeError(f"ZIP is empty: {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"project root not found: {root}")
    if output_dir == root or root in output_dir.parents:
        raise SystemExit("--output-dir must be outside the project root to avoid ZIP recursion")

    labs_dir = root / "labs"
    actual_labs = tuple(sorted(path.name for path in labs_dir.iterdir() if path.is_dir()))
    if actual_labs != EXPECTED_LABS:
        raise SystemExit(
            "expected exactly six Labs: " + ", ".join(EXPECTED_LABS)
        )

    packages_dir = root / "lab_packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    for stale in packages_dir.glob("*.zip"):
        stale.unlink()

    lab_archives: list[Path] = []
    for lab_name in EXPECTED_LABS:
        lab_path = labs_dir / lab_name
        archive_path = packages_dir / f"{lab_name}.zip"
        with zipfile.ZipFile(
            archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            count = add_tree(
                archive,
                lab_path,
                Path(lab_name),
                include_lab_packages=False,
            )
        checked_zip(archive_path)
        lab_archives.append(archive_path)
        print(f"[PASS] {archive_path.name}: {count} files")

    output_dir.mkdir(parents=True, exist_ok=True)
    full_archive = output_dir / "FPGA_AI加速器_6日完整專案.zip"
    with zipfile.ZipFile(
        full_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        count = add_tree(
            archive,
            root,
            Path(root.name),
            include_lab_packages=True,
        )
    checked_zip(full_archive)

    document_source = root / "docs" / "專案教學文件.md"
    document_output = output_dir / "FPGA_AI加速器專案教學文件.md"
    shutil.copy2(document_source, document_output)

    checksums = output_dir / "SHA256SUMS.txt"
    checksum_targets = [full_archive, document_output]
    lines = [f"{sha256(path)}  {path.name}" for path in checksum_targets]
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[PASS] complete archive: {count} files")
    print(f"[PASS] ZIP CRC: {full_archive}")
    print(f"[PASS] SHA-256: {sha256(full_archive)}")
    print(f"[PASS] standalone document: {document_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
