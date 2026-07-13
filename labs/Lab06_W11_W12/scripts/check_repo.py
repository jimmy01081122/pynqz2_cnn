#!/usr/bin/env python3
"""Check whether the six-day course repository contains required deliverables."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_ROOT = SCRIPT_PATH.parents[3]
SKIP_DIRS = {".git", ".venv", "__pycache__", "build", "artifacts", "tradeoff_results"}
ILLUSTRATIVE_MARKER = "ILLUSTRATIVE_ONLY_DO_NOT_REPORT"


@dataclass
class Check:
    name: str
    status: str
    detail: str


def check_path(root: Path, relative: str, name: str | None = None) -> Check:
    path = root / relative
    return Check(
        name or relative,
        "PASS" if path.exists() else "FAIL",
        f"found: {relative}" if path.exists() else f"missing: {relative}",
    )


def project_files(root: Path, suffixes: set[str] | None = None):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in relative_parts):
            continue
        if suffixes is None or path.suffix.lower() in suffixes:
            yield path


def is_testbench(path: Path) -> bool:
    name = path.stem.casefold()
    return (
        name.startswith("tb_")
        or name.endswith("_tb")
        or "testbench" in name
        or "/tb/" in path.as_posix().casefold()
    )


def count_todo_tokens(paths: list[Path]) -> int:
    count = 0
    for path in paths:
        try:
            count += len(
                re.findall(r"\bTODO\b", path.read_text(encoding="utf-8", errors="ignore"))
            )
        except OSError:
            pass
    return count


def run_checks(root: Path) -> list[Check]:
    checks: list[Check] = []
    required_paths = [
        "README.md",
        "labs/Lab01_W1_W2/README.md",
        "labs/Lab01_W1_W2/scripts/check_env.py",
        "labs/Lab01_W1_W2/scripts/train_baseline.py",
        "labs/Lab01_W1_W2/scripts/prune_2to4.py",
        "labs/Lab01_W1_W2/scripts/quantize_ptq.py",
        "labs/Lab01_W1_W2/scripts/export_hex.py",
        "labs/Lab02_W3_W4/README.md",
        "labs/Lab03_W5_W6/README.md",
        "labs/Lab04_W7_W8/README.md",
        "labs/Lab05_W9_W10/README.md",
        "labs/Lab05_W9_W10/constraints/lab05_timing.xdc",
        "labs/Lab05_W9_W10/vivado/run_config.tcl",
        "labs/Lab06_W11_W12/README.md",
        "labs/Lab06_W11_W12/REPORT_TEMPLATE.md",
        "labs/Lab06_W11_W12/data/ppa_results_template.csv",
        "labs/Lab06_W11_W12/scripts/analyze_tradeoffs.py",
    ]
    checks.extend(check_path(root, relative) for relative in required_paths)

    config_paths = [
        root / "labs" / "Lab05_W9_W10" / "vivado" / "configs" / f"{name}.tcl"
        for name in ("dense_int8", "dense_int4", "int8_2to4", "int4_2to4")
    ]
    missing_configs = [
        str(path.relative_to(root)) for path in config_paths if not path.is_file()
    ]
    checks.append(
        Check(
            "四組 Vivado config",
            "PASS" if not missing_configs else "FAIL",
            "all four configs found"
            if not missing_configs
            else "missing: " + ", ".join(missing_configs),
        )
    )

    hdl_files = list(project_files(root, {".sv", ".v"}))
    production_rtl = [
        path
        for path in hdl_files
        if "warmup" not in path.as_posix().casefold() and not is_testbench(path)
    ]
    testbenches = [path for path in hdl_files if is_testbench(path)]
    checks.append(
        Check(
            "專案 RTL",
            "PASS" if production_rtl else "FAIL",
            f"{len(production_rtl)} production RTL file(s)",
        )
    )
    checks.append(
        Check(
            "Testbench",
            "PASS" if testbenches else "FAIL",
            f"{len(testbenches)} testbench file(s)",
        )
    )

    xdc_files = list(project_files(root, {".xdc"}))
    checks.append(
        Check(
            "XDC",
            "PASS" if xdc_files else "FAIL",
            f"{len(xdc_files)} XDC file(s)",
        )
    )

    warmup_dir = root / "labs" / "Lab01_W1_W2" / "warmups"
    warmup_hdl = (
        [path for path in warmup_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".sv", ".v"}]
        if warmup_dir.is_dir()
        else []
    )
    warmup_tbs = [path for path in warmup_hdl if is_testbench(path)]
    todo_count = count_todo_tokens(warmup_hdl)
    checks.append(
        Check(
            "四題 warmup TB",
            "PASS" if len(warmup_tbs) >= 4 else "FAIL",
            f"{len(warmup_tbs)} warmup testbench file(s); expected >= 4",
        )
    )
    checks.append(
        Check(
            "warmup TODO",
            "PASS" if todo_count >= 4 else "FAIL",
            f"{todo_count} TODO token(s); expected >= 4",
        )
    )

    contaminated = []
    measured_csv = []
    for path in project_files(root, {".csv"}):
        if path.name in {"ppa_results_sample.csv", "ppa_results_template.csv"}:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if ILLUSTRATIVE_MARKER in text:
            contaminated.append(str(path.relative_to(root)))
        if re.search(r",(?:parsed|measured),", text):
            measured_csv.append(str(path.relative_to(root)))
    checks.append(
        Check(
            "正式 CSV 無示意資料",
            "PASS" if not contaminated else "FAIL",
            "no illustrative marker outside sample/template"
            if not contaminated
            else "illustrative marker found in: " + ", ".join(contaminated),
        )
    )
    checks.append(
        Check(
            "可追溯實測 CSV",
            "PASS" if measured_csv else "WARN",
            (
                "measured result: " + ", ".join(measured_csv)
                if measured_csv
                else "尚未找到 status=parsed/measured 的正式 CSV；教材範本可先保留此警告"
            ),
        )
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="仍列出 FAIL，但回傳 0；適合教材尚在合併時",
    )
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"找不到專案根目錄：{root}")

    checks = run_checks(root)
    failures = [check for check in checks if check.status == "FAIL"]
    warnings = [check for check in checks if check.status == "WARN"]
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "status": "FAIL" if failures else "PASS",
                    "failures": len(failures),
                    "warnings": len(warnings),
                    "checks": [asdict(check) for check in checks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for check in checks:
            print(f"[{check.status:4s}] {check.name}: {check.detail}")
        print(
            f"SUMMARY: {'FAIL' if failures else 'PASS'} "
            f"({len(failures)} failure(s), {len(warnings)} warning(s))"
        )
        if failures and args.allow_incomplete:
            print("--allow-incomplete 已啟用：保留失敗清單，但命令回傳 0。")
    return 0 if not failures or args.allow_incomplete else 1


if __name__ == "__main__":
    raise SystemExit(main())

