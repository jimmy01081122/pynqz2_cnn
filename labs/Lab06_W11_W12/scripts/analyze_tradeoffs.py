#!/usr/bin/env python3
"""Validate four-configuration results, score trade-offs, and make plots."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


REQUIRED_COLUMNS = (
    "config",
    "display_name",
    "lut",
    "power_w",
    "accuracy_pct",
    "throughput_gops",
    "status",
    "data_source",
)
METRICS = ("accuracy", "throughput", "lut", "power")
DEFAULT_WEIGHTS = {
    "accuracy": 0.35,
    "throughput": 0.25,
    "lut": 0.20,
    "power": 0.20,
}
VALID_STATUSES = {"parsed", "measured", "illustrative"}
ILLUSTRATIVE_MARKER = "ILLUSTRATIVE_ONLY_DO_NOT_REPORT"


def finite_float(text: str, field: str, config: str) -> float:
    try:
        value = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{config}: {field} 不是數字或為空") from exc
    if not math.isfinite(value):
        raise ValueError(f"{config}: {field} 必須是有限數")
    return value


def read_results(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [field for field in REQUIRED_COLUMNS if field not in fields]
        if missing:
            raise ValueError("CSV 缺少必要欄位：" + ", ".join(missing))
        raw_rows = list(reader)

    seen = set()
    usable = []
    skipped = []
    for raw in raw_rows:
        config = (raw.get("config") or "").strip()
        if not config:
            skipped.append("<空白 config>: skipped")
            continue
        if config in seen:
            raise ValueError(f"config 重複：{config}")
        seen.add(config)
        status = (raw.get("status") or "").strip()
        if status not in VALID_STATUSES:
            skipped.append(f"{config}: status={status or '<empty>'}")
            continue
        try:
            numeric = {
                "accuracy": finite_float(raw.get("accuracy_pct", ""), "accuracy_pct", config),
                "throughput": finite_float(
                    raw.get("throughput_gops", ""), "throughput_gops", config
                ),
                "lut": finite_float(raw.get("lut", ""), "lut", config),
                "power": finite_float(raw.get("power_w", ""), "power_w", config),
            }
        except ValueError as exc:
            skipped.append(str(exc))
            continue
        if numeric["lut"] < 0 or numeric["power"] < 0 or numeric["throughput"] < 0:
            skipped.append(f"{config}: resource/power/throughput 不可為負")
            continue
        usable.append({"raw": raw, "config": config, **numeric})
    return fields, raw_rows, usable, skipped


def parse_weights(text: str) -> dict[str, float]:
    result = {}
    for item in text.split(","):
        if "=" not in item:
            raise ValueError("權重格式應為 accuracy=...,throughput=...,lut=...,power=...")
        key, value_text = (piece.strip() for piece in item.split("=", 1))
        if key not in METRICS:
            raise ValueError(f"未知權重名稱：{key}")
        if key in result:
            raise ValueError(f"權重重複：{key}")
        value = float(value_text)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} 權重必須是非負有限數")
        result[key] = value
    missing = [key for key in METRICS if key not in result]
    if missing:
        raise ValueError("缺少權重：" + ", ".join(missing))
    total = sum(result.values())
    if total <= 0:
        raise ValueError("權重總和必須大於 0")
    return {key: value / total for key, value in result.items()}


def normalized(values: list[float], higher_is_better: bool) -> list[float]:
    minimum, maximum = min(values), max(values)
    if maximum == minimum:
        return [0.5] * len(values)
    norm = [(value - minimum) / (maximum - minimum) for value in values]
    return norm if higher_is_better else [1.0 - value for value in norm]


def dominates(a: dict, b: dict) -> bool:
    no_worse = (
        a["accuracy"] >= b["accuracy"]
        and a["throughput"] >= b["throughput"]
        and a["lut"] <= b["lut"]
        and a["power"] <= b["power"]
    )
    strictly_better = (
        a["accuracy"] > b["accuracy"]
        or a["throughput"] > b["throughput"]
        or a["lut"] < b["lut"]
        or a["power"] < b["power"]
    )
    return no_worse and strictly_better


def analyze(rows: list[dict], weights: dict[str, float]) -> list[dict]:
    if not rows:
        raise ValueError("沒有 status=parsed/measured/illustrative 且四個核心指標完整的資料列")
    for metric in METRICS:
        beneficial = metric in {"accuracy", "throughput"}
        values = normalized([row[metric] for row in rows], beneficial)
        for row, value in zip(rows, values):
            row[f"norm_{metric}"] = value
    for row in rows:
        row["score"] = sum(
            weights[metric] * row[f"norm_{metric}"] for metric in METRICS
        )
        row["pareto"] = not any(
            dominates(other, row) for other in rows if other is not row
        )
    return sorted(rows, key=lambda row: (-row["score"], row["config"]))


def write_summary(path: Path, input_fields: list[str], rows: list[dict]) -> None:
    extra_fields = [
        "norm_accuracy",
        "norm_throughput",
        "norm_lut",
        "norm_power",
        "weighted_score",
        "pareto",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=input_fields + extra_fields)
        writer.writeheader()
        for row in rows:
            output = dict(row["raw"])
            for metric in METRICS:
                output[f"norm_{metric}"] = f"{row[f'norm_{metric}']:.6f}"
            output["weighted_score"] = f"{row['score']:.6f}"
            output["pareto"] = str(row["pareto"]).lower()
            writer.writerow(output)


def make_plots(output_dir: Path, rows: list[dict], illustrative: bool) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "找不到 matplotlib。請安裝 requirements.txt，或加 --no-plot。"
        ) from exc

    banner = " — ILLUSTRATIVE DATA" if illustrative else ""
    colors = ["#2563eb" if row["pareto"] else "#94a3b8" for row in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(
        [row["lut"] for row in rows],
        [row["accuracy"] for row in rows],
        c=colors,
        s=90,
        edgecolors="black",
        linewidths=0.6,
    )
    for row in rows:
        ax.annotate(
            row["raw"].get("display_name") or row["config"],
            (row["lut"], row["accuracy"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
        )
    ax.set_xlabel("LUT count (lower is better)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Accuracy vs LUT" + banner)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "accuracy_vs_lut.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(
        [row["power"] for row in rows],
        [row["throughput"] for row in rows],
        c=colors,
        s=90,
        edgecolors="black",
        linewidths=0.6,
    )
    for row in rows:
        ax.annotate(
            row["raw"].get("display_name") or row["config"],
            (row["power"], row["throughput"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
        )
    ax.set_xlabel("Estimated power (W, lower is better)")
    ax.set_ylabel("Throughput (GOPS)")
    ax.set_title("Throughput vs Power" + banner)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "throughput_vs_power.png", dpi=160)
    plt.close(fig)


def write_recommendations(
    path: Path,
    source: Path,
    rows: list[dict],
    weights: dict[str, float],
    skipped: list[str],
    illustrative: bool,
) -> None:
    lines = ["# Trade-off 分析摘要", ""]
    if illustrative:
        lines.extend(
            [
                "> 警告：輸入含 ILLUSTRATIVE_ONLY_DO_NOT_REPORT；以下排序只示範流程，"
                "不可當作專案實測結論。",
                "",
            ]
        )
    lines.extend(
        [
            f"- 輸入資料：{source}",
            "- 權重（已正規化）："
            + "、".join(f"{key}={weights[key]:.3f}" for key in METRICS),
            "",
            "## 加權排序",
            "",
        ]
    )
    for rank, row in enumerate(rows, start=1):
        name = row["raw"].get("display_name") or row["config"]
        pareto = "，Pareto" if row["pareto"] else ""
        lines.append(f"{rank}. {name}：score={row['score']:.4f}{pareto}")

    pareto_names = [
        row["raw"].get("display_name") or row["config"] for row in rows if row["pareto"]
    ]
    lines.extend(
        [
            "",
            "## Pareto front",
            "",
            "、".join(pareto_names) if pareto_names else "無可判定資料。",
            "",
            "## Timing 提醒",
            "",
        ]
    )
    timing_failures = []
    for row in rows:
        text = row["raw"].get("wns_ns", "")
        try:
            if text != "" and float(text) < 0:
                timing_failures.append(row["raw"].get("display_name") or row["config"])
        except ValueError:
            pass
    lines.append(
        "WNS < 0：" + "、".join(timing_failures)
        if timing_failures
        else "未在可用資料中發現 WNS < 0；仍請核對 timing_summary.rpt。"
    )
    lines.extend(
        [
            "",
            "## 解讀限制",
            "",
            "- 加權分數取決於應用情境，不代表唯一最佳答案。",
            "- fmax_est_mhz 與 Vivado power 都是估計，應保留原始報告與假設。",
            "- Accuracy、latency 與 throughput 必須使用四組一致的測試條件。",
        ]
    )
    if skipped:
        lines.extend(["", "## 未納入列", ""])
        lines.extend(f"- {message}" for message in skipped)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def self_test() -> int:
    a = {"accuracy": 80.0, "throughput": 40.0, "lut": 5000.0, "power": 1.0}
    b = {"accuracy": 79.0, "throughput": 30.0, "lut": 6000.0, "power": 1.2}
    assert dominates(a, b)
    assert not dominates(b, a)
    assert normalized([1.0, 2.0, 3.0], True) == [0.0, 0.5, 1.0]
    assert normalized([1.0, 2.0, 3.0], False) == [1.0, 0.5, 0.0]
    print("analyze_tradeoffs self-test: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", nargs="?", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("tradeoff_results"))
    parser.add_argument(
        "--weights",
        default="accuracy=0.35,throughput=0.25,lut=0.20,power=0.20",
    )
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.input_csv is None:
        raise SystemExit("請提供 input_csv，或使用 --self-test")
    if not args.input_csv.is_file():
        raise SystemExit(f"找不到 CSV：{args.input_csv}")

    try:
        weights = parse_weights(args.weights)
        input_fields, raw_rows, usable, skipped = read_results(args.input_csv)
        ranked = analyze(usable, weights)
    except ValueError as exc:
        raise SystemExit(f"資料驗證失敗：{exc}") from exc

    illustrative = any(
        ILLUSTRATIVE_MARKER in (row.get("data_source") or "") for row in raw_rows
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_summary(args.output_dir / "analysis_summary.csv", input_fields, ranked)
    write_recommendations(
        args.output_dir / "recommendations.md",
        args.input_csv.resolve(),
        ranked,
        weights,
        skipped,
        illustrative,
    )
    if not args.no_plot:
        try:
            make_plots(args.output_dir, ranked, illustrative)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc

    print(f"usable configurations: {len(ranked)}")
    print(f"skipped rows: {len(skipped)}")
    print(f"output: {args.output_dir.resolve()}")
    if illustrative:
        print("WARNING: ILLUSTRATIVE_ONLY_DO_NOT_REPORT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

