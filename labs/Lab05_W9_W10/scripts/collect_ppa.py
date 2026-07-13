#!/usr/bin/env python3
"""Collect common Vivado report fields without inventing missing measurements."""

from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path


LAB_DIR = Path(__file__).resolve().parents[1]
CONFIGS = (
    ("dense_int8", "Dense INT8", 8, "dense"),
    ("dense_int4", "Dense INT4", 4, "dense"),
    ("int8_2to4", "INT8 2:4", 8, "2:4"),
    ("int4_2to4", "INT4 2:4", 4, "2:4"),
)
FIELDS = (
    "config",
    "display_name",
    "data_width",
    "sparsity",
    "target_clock_ns",
    "lut",
    "ff",
    "dsp",
    "bram",
    "wns_ns",
    "fmax_est_mhz",
    "power_w",
    "accuracy_pct",
    "latency_cycles",
    "throughput_gops",
    "status",
    "data_source",
    "notes",
)
NUMBER = re.compile(r"[-+]?(?:\d[\d,]*\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def number(text: str) -> float | None:
    match = NUMBER.search(text)
    if not match:
        return None
    try:
        value = float(match.group(0).replace(",", ""))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def pipe_value(text: str, labels: tuple[str, ...]) -> float | None:
    normalized = tuple(label.casefold() for label in labels)
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]
        if len(cells) < 2:
            continue
        first = cells[0].casefold()
        if first in normalized:
            return number(cells[1])
    return None


def parse_utilization(text: str) -> dict[str, float | None]:
    return {
        "lut": pipe_value(text, ("CLB LUTs", "Slice LUTs")),
        "ff": pipe_value(text, ("CLB Registers", "Slice Registers")),
        "dsp": pipe_value(text, ("DSPs", "DSP48E1 only", "DSP48E2 only")),
        "bram": pipe_value(text, ("Block RAM Tile", "Block RAM Tiles")),
    }


def parse_wns(text: str) -> float | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "WNS(ns)" not in line and "WNS (ns)" not in line:
            continue
        for candidate in lines[index + 1 : index + 8]:
            stripped = candidate.strip()
            if not stripped or set(stripped) <= {"-", " ", "\t"}:
                continue
            value = number(stripped)
            if value is not None:
                return value
    # Fallback for compact key/value reports.
    match = re.search(
        r"\bWNS(?:\s*\(ns\))?\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def parse_power(text: str) -> float | None:
    value = pipe_value(text, ("Total On-Chip Power (W)",))
    if value is not None:
        return value
    match = re.search(
        r"Total\s+On-Chip\s+Power\s*\(W\)\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def read_metadata(run_dir: Path) -> dict[str, str]:
    path = run_dir / "run_metadata.csv"
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return rows[0] if rows else {}


def display_number(value: float | None, integer: bool = False) -> str:
    if value is None:
        return ""
    if integer and float(value).is_integer():
        return str(int(value))
    return f"{value:.6g}"


def blank_row(config_id: str, display_name: str, bits: int, sparsity: str) -> dict[str, str]:
    row = {field: "" for field in FIELDS}
    row.update(
        {
            "config": config_id,
            "display_name": display_name,
            "data_width": str(bits),
            "sparsity": sparsity,
            "target_clock_ns": "10",
            "status": "not_measured",
            "data_source": "user_measurement_required",
            "notes": "請由 Vivado 原始報告與軟體/RTL 測試填入；目前沒有實測值",
        }
    )
    return row


def collect_one(
    runs_dir: Path,
    config_id: str,
    display_name: str,
    bits: int,
    sparsity: str,
) -> dict[str, str]:
    run_dir = runs_dir / config_id
    report_dir = run_dir / "reports"
    util_path = report_dir / "utilization.rpt"
    timing_path = report_dir / "timing_summary.rpt"
    power_path = report_dir / "power.rpt"
    row = blank_row(config_id, display_name, bits, sparsity)
    metadata = read_metadata(run_dir)
    target_clock = number(metadata.get("target_clock_ns", "")) or 10.0
    row["target_clock_ns"] = display_number(target_clock)

    missing_files = [
        path.name for path in (util_path, timing_path, power_path) if not path.is_file()
    ]
    if missing_files:
        row.update(
            status="missing_reports",
            data_source="not_measured",
            notes="缺少原始報告：" + ", ".join(missing_files),
        )
        return row

    utilization = parse_utilization(util_path.read_text(encoding="utf-8", errors="replace"))
    wns = parse_wns(timing_path.read_text(encoding="utf-8", errors="replace"))
    power = parse_power(power_path.read_text(encoding="utf-8", errors="replace"))
    parsed = utilization | {"wns_ns": wns, "power_w": power}
    missing_fields = [key for key, value in parsed.items() if value is None]
    for key in ("lut", "ff", "dsp", "bram"):
        row[key] = display_number(utilization[key], integer=True)
    row["wns_ns"] = display_number(wns)
    row["power_w"] = display_number(power)
    if wns is not None and target_clock - wns > 0:
        row["fmax_est_mhz"] = display_number(1000.0 / (target_clock - wns))

    if missing_fields:
        row.update(
            status="parse_error",
            data_source="vivado_reports_partial",
            notes=(
                "報告存在但欄位解析失敗："
                + ", ".join(missing_fields)
                + "；請人工核對原始 report"
            ),
        )
    else:
        row.update(
            status="parsed",
            data_source="vivado_reports",
            notes=(
                "PPA 由原始 Vivado report 解析；fmax_est_mhz 僅為 "
                "1000/(target_clock_ns-WNS) 粗估"
            ),
        )
    return row


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def self_test() -> int:
    utilization = """
    | Site Type       | Used  | Available |
    | CLB LUTs        | 1,234 | 63400     |
    | CLB Registers   | 2,345 | 126800    |
    | Block RAM Tile  | 12    | 135       |
    | DSPs            | 48    | 240       |
    """
    timing = """
    WNS(ns)      TNS(ns)  TNS Failing Endpoints
    -------      -------  ---------------------
      0.321        0.000              0
    """
    power = "| Total On-Chip Power (W) | 1.456 |"
    assert parse_utilization(utilization) == {
        "lut": 1234.0,
        "ff": 2345.0,
        "dsp": 48.0,
        "bram": 12.0,
    }
    assert parse_wns(timing) == 0.321
    assert parse_power(power) == 1.456
    print("collect_ppa parser self-test: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=LAB_DIR / "build")
    parser.add_argument("--output", type=Path, default=LAB_DIR / "ppa_results.csv")
    parser.add_argument(
        "--template-only",
        action="store_true",
        help="只建立四列空白模板，不讀任何 report",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    if args.template_only:
        rows = [blank_row(*config) for config in CONFIGS]
    else:
        rows = [collect_one(args.runs_dir, *config) for config in CONFIGS]
    write_csv(args.output, rows)
    parsed_count = sum(row["status"] == "parsed" for row in rows)
    print(f"CSV: {args.output.resolve()}")
    print(f"parsed configurations: {parsed_count}/{len(rows)}")
    if not args.template_only and parsed_count < len(rows):
        print("提醒：空值保持空白；程式沒有填入任何猜測的 PPA 數字。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

