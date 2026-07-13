#!/usr/bin/env python3
"""Verify the static deliverables of the six-day FPGA AI course project.

The checker intentionally uses only the Python standard library so it can run
before Vivado, Icarus Verilog, NumPy, or any other course dependency is set up.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


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
EXPECTED_WARMUPS = (
    "01_parameterized_adder",
    "02_valid_ready_mac",
    "03_sync_fifo",
    "04_testbench_basics",
)
WARMUP_FILES = {
    "01_parameterized_adder": ("parameterized_adder.sv", "tb_parameterized_adder.sv"),
    "02_valid_ready_mac": ("valid_ready_mac.sv", "tb_valid_ready_mac.sv"),
    "03_sync_fifo": ("sync_fifo.sv", "tb_sync_fifo.sv"),
    "04_testbench_basics": ("tiny_counter.sv", "tb_tiny_counter.sv"),
}

FORBIDDEN_MAIN_DOCUMENT_TEXT = "給指導教授/口試委員看的一頁式專案摘要"
ILLUSTRATIVE_MARKER = "ILLUSTRATIVE_ONLY_DO_NOT_REPORT"
TODO_TOKEN = re.compile(r"(?<![A-Za-z0-9_])TODO(?![A-Za-z0-9_])")


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


class CheckCollector:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.checks: list[Check] = []

    def add(self, name: str, passed: bool, success: str, failure: str) -> None:
        self.checks.append(Check(name, "PASS" if passed else "FAIL", success if passed else failure))

    def required_files(self, name: str, relative_paths: Iterable[str]) -> None:
        missing: list[str] = []
        empty: list[str] = []
        paths = tuple(relative_paths)
        for relative in paths:
            path = self.root / relative
            if not path.is_file():
                missing.append(relative)
                continue
            try:
                if path.stat().st_size == 0:
                    empty.append(relative)
            except OSError:
                missing.append(relative)
        passed = not missing and not empty
        problems: list[str] = []
        if missing:
            problems.append("missing: " + ", ".join(missing))
        if empty:
            problems.append("empty: " + ", ".join(empty))
        self.add(
            name,
            passed,
            f"{len(paths)} required file(s) found and non-empty",
            "; ".join(problems),
        )


def configure_console() -> None:
    """Keep Traditional Chinese output readable on redirected Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (LookupError, OSError):
                pass


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None


def describe_exact(actual: list[str], expected: tuple[str, ...]) -> str:
    missing = [name for name in expected if name not in actual]
    extra = [name for name in actual if name not in expected]
    details: list[str] = []
    if missing:
        details.append("missing: " + ", ".join(missing))
    if extra:
        details.append("unexpected: " + ", ".join(extra))
    return "; ".join(details) or "names or ordering do not match"


def lab_required_files() -> dict[str, tuple[str, ...]]:
    return {
        "專案入口與共用文件": (
            "README.md",
            "ASSUMPTIONS.md",
            "MANIFEST.md",
            "TEST_REPORT.md",
            "docs/專案教學文件.md",
            "docs/需求對照表.md",
            "docs/程式碼與XDC索引.md",
            "docs/開始前檢查表.md",
            "docs/除錯指南.md",
            "common/constraints/pynq_z2_user_io.xdc",
            "common/docs/XDC使用說明.md",
            "scripts/verify_project.py",
            "scripts/run_all_tests.py",
            "scripts/build_release.py",
        ),
        "Lab01 Python 與教材": (
            "labs/Lab01_W1_W2/README.md",
            "labs/Lab01_W1_W2/requirements.txt",
            "labs/Lab01_W1_W2/warmups/README.md",
            "labs/Lab01_W1_W2/src/__init__.py",
            "labs/Lab01_W1_W2/src/data.py",
            "labs/Lab01_W1_W2/src/hex_utils.py",
            "labs/Lab01_W1_W2/src/prune_utils.py",
            "labs/Lab01_W1_W2/src/quant_utils.py",
            "labs/Lab01_W1_W2/src/tiny_cnn.py",
            "labs/Lab01_W1_W2/scripts/check_env.py",
            "labs/Lab01_W1_W2/scripts/train_baseline.py",
            "labs/Lab01_W1_W2/scripts/prune_2to4.py",
            "labs/Lab01_W1_W2/scripts/quantize_ptq.py",
            "labs/Lab01_W1_W2/scripts/export_hex.py",
            "labs/Lab01_W1_W2/scripts/smoke_test.py",
            "labs/Lab01_W1_W2/board_demo/README.md",
            "labs/Lab01_W1_W2/board_demo/rtl/pynq_z2_adder_demo.sv",
            "labs/Lab01_W1_W2/board_demo/tb/tb_pynq_z2_adder_demo.sv",
            "labs/Lab01_W1_W2/board_demo/sim/files.f",
            "labs/Lab01_W1_W2/board_demo/sim/run_iverilog.sh",
            "labs/Lab01_W1_W2/board_demo/constraints/pynq_z2_adder_demo.xdc",
        ),
        "Lab02 RTL/TB/XDC/Tcl": (
            "labs/Lab02_W3_W4/README.md",
            "labs/Lab02_W3_W4/rtl/dense_int_pe.sv",
            "labs/Lab02_W3_W4/tb/tb_dense_int_pe.sv",
            "labs/Lab02_W3_W4/sim/files.f",
            "labs/Lab02_W3_W4/constraints/pynq_z2_lab02.xdc",
            "labs/Lab02_W3_W4/vivado/create_project.tcl",
        ),
        "Lab03 RTL/TB/XDC/Tcl": (
            "labs/Lab03_W5_W6/README.md",
            "labs/Lab03_W5_W6/rtl/sparse_2of4_decoder.sv",
            "labs/Lab03_W5_W6/rtl/sparse_pe.sv",
            "labs/Lab03_W5_W6/rtl/requantize.sv",
            "labs/Lab03_W5_W6/rtl/sparse_array_4x4.sv",
            "labs/Lab03_W5_W6/tb/tb_sparse_array.sv",
            "labs/Lab03_W5_W6/sim/files.f",
            "labs/Lab03_W5_W6/constraints/pynq_z2_lab03.xdc",
            "labs/Lab03_W5_W6/vivado/create_project.tcl",
        ),
        "Lab04 RTL/TB/XDC/Tcl/PYNQ driver": (
            "labs/Lab04_W7_W8/README.md",
            "labs/Lab04_W7_W8/rtl/axis_dot_accelerator.sv",
            "labs/Lab04_W7_W8/tb/tb_axis_dot_accelerator.sv",
            "labs/Lab04_W7_W8/sim/files.f",
            "labs/Lab04_W7_W8/constraints/pynq_z2_lab04.xdc",
            "labs/Lab04_W7_W8/vivado/create_project.tcl",
            "labs/Lab04_W7_W8/vivado/create_bd.tcl",
            "labs/Lab04_W7_W8/python/axis_accel.py",
        ),
        "Lab05 RTL/TB/XDC/Tcl/PPA": (
            "labs/Lab05_W9_W10/README.md",
            "labs/Lab05_W9_W10/rtl/ai_accel_top.sv",
            "labs/Lab05_W9_W10/tb/tb_ai_accel_top.sv",
            "labs/Lab05_W9_W10/sim/files.f",
            "labs/Lab05_W9_W10/constraints/lab05_timing.xdc",
            "labs/Lab05_W9_W10/scripts/collect_ppa.py",
            "labs/Lab05_W9_W10/vivado/run_config.tcl",
            "labs/Lab05_W9_W10/vivado/configs/dense_int8.tcl",
            "labs/Lab05_W9_W10/vivado/configs/dense_int4.tcl",
            "labs/Lab05_W9_W10/vivado/configs/int8_2to4.tcl",
            "labs/Lab05_W9_W10/vivado/configs/int4_2to4.tcl",
        ),
        "Lab06 分析與報告": (
            "labs/Lab06_W11_W12/README.md",
            "labs/Lab06_W11_W12/REPORT_TEMPLATE.md",
            "labs/Lab06_W11_W12/requirements.txt",
            "labs/Lab06_W11_W12/data/ppa_results_template.csv",
            "labs/Lab06_W11_W12/data/ppa_results_sample.csv",
            "labs/Lab06_W11_W12/scripts/analyze_tradeoffs.py",
            "labs/Lab06_W11_W12/scripts/check_repo.py",
        ),
    }


def run_checks(root: Path) -> list[Check]:
    collector = CheckCollector(root)

    labs_dir = root / "labs"
    actual_labs = sorted(path.name for path in labs_dir.iterdir() if path.is_dir()) if labs_dir.is_dir() else []
    collector.add(
        "精確六個 Lab",
        actual_labs == list(EXPECTED_LABS),
        "exactly " + ", ".join(EXPECTED_LABS),
        describe_exact(actual_labs, EXPECTED_LABS),
    )

    for name, relative_paths in lab_required_files().items():
        collector.required_files(name, relative_paths)

    lab01_scripts = root / "labs" / "Lab01_W1_W2" / "scripts"
    sparse_exporters = []
    if lab01_scripts.is_dir():
        for path in lab01_scripts.glob("*.py"):
            folded = path.stem.casefold().replace("_", "")
            text = read_text(path) or ""
            implements_sparse_export = bool(
                re.search(r"(?:sparse[_-]?2to4|pack_sparse_2to4|--sparse-2to4)", text, re.IGNORECASE)
            )
            if "export" in folded and (
                "sparse" in folded or "2to4" in folded or implements_sparse_export
            ):
                sparse_exporters.append(path)
    collector.add(
        "Lab01 2:4 sparse 匯出程式",
        bool(sparse_exporters),
        "found: " + ", ".join(str(path.relative_to(root)) for path in sorted(sparse_exporters)),
        "missing a Python export entry point that implements sparse 2:4 packing",
    )

    warmup_root = root / "labs" / "Lab01_W1_W2" / "warmups"
    actual_warmups = (
        sorted(path.name for path in warmup_root.iterdir() if path.is_dir())
        if warmup_root.is_dir()
        else []
    )
    collector.add(
        "精確四個暖身題",
        actual_warmups == list(EXPECTED_WARMUPS),
        "exactly " + ", ".join(EXPECTED_WARMUPS),
        describe_exact(actual_warmups, EXPECTED_WARMUPS),
    )

    for warmup, (dut_name, tb_name) in WARMUP_FILES.items():
        base = warmup_root / warmup
        required = [
            base / "README.md",
            base / "starter" / "files.f",
            base / "starter" / dut_name,
            base / "starter" / tb_name,
            base / "solution" / "files.f",
            base / "solution" / dut_name,
            base / "solution" / tb_name,
        ]
        missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
        collector.add(
            f"{warmup} 教材/DUT/TB",
            not missing,
            "README, starter, solution, DUT and TB found",
            "missing: " + ", ".join(missing),
        )

        starter_results: list[tuple[Path, bool]] = []
        for path in (base / "starter" / dut_name, base / "starter" / tb_name):
            text = read_text(path)
            starter_results.append((path, text is not None and TODO_TOKEN.search(text) is not None))
        starter_without_todo = [
            str(path.relative_to(root)) for path, has_todo in starter_results if not has_todo
        ]
        collector.add(
            f"{warmup} starter TODO",
            not starter_without_todo,
            "both starter DUT and TB contain TODO",
            "missing TODO in: " + ", ".join(starter_without_todo),
        )

        solution_dir = base / "solution"
        contaminated: list[str] = []
        if solution_dir.is_dir():
            for path in solution_dir.rglob("*"):
                if path.is_file():
                    text = read_text(path)
                    if text is not None and TODO_TOKEN.search(text):
                        contaminated.append(str(path.relative_to(root)))
        collector.add(
            f"{warmup} solution 無 TODO",
            solution_dir.is_dir() and not contaminated,
            "solution contains no TODO token",
            (
                "solution directory missing"
                if not solution_dir.is_dir()
                else "TODO found in: " + ", ".join(contaminated)
            ),
        )

    main_document = root / "docs" / "專案教學文件.md"
    main_text = read_text(main_document)
    collector.add(
        "主教材已移除一頁式摘要",
        main_text is not None and FORBIDDEN_MAIN_DOCUMENT_TEXT not in main_text,
        "forbidden section title not found",
        (
            "main document is unreadable"
            if main_text is None
            else f"forbidden text found: {FORBIDDEN_MAIN_DOCUMENT_TEXT}"
        ),
    )

    sample_path = root / "labs" / "Lab06_W11_W12" / "data" / "ppa_results_sample.csv"
    sample_text = read_text(sample_path)
    collector.add(
        "Lab06 示意資料標記",
        sample_text is not None and ILLUSTRATIVE_MARKER in sample_text,
        f"sample contains {ILLUSTRATIVE_MARKER}",
        (
            "sample CSV is unreadable"
            if sample_text is None
            else f"sample is missing {ILLUSTRATIVE_MARKER}"
        ),
    )

    return collector.checks


def main(argv: list[str] | None = None) -> int:
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="course project root (default: parent of this scripts directory)",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        message = f"project root is not a directory: {root}"
        if args.json:
            print(json.dumps({"root": str(root), "status": "FAIL", "error": message}, ensure_ascii=False, indent=2))
        else:
            print(f"[FAIL] {message}")
        return 2

    checks = run_checks(root)
    failures = [check for check in checks if check.status == "FAIL"]
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "status": "FAIL" if failures else "PASS",
                    "failures": len(failures),
                    "checks": [asdict(check) for check in checks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Project root: {root}")
        for check in checks:
            print(f"[{check.status:4s}] {check.name}: {check.detail}")
        print(f"SUMMARY: {'FAIL' if failures else 'PASS'} ({len(failures)} failure(s), {len(checks)} check(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
