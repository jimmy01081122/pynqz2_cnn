#!/usr/bin/env python3
"""Apply deterministic row-wise 2:4 pruning and save explicit group masks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


LAB_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_DIR))

from src.prune_utils import prune_2to4


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", nargs="?", help="baseline 或已處理的 .pt checkpoint")
    parser.add_argument("--output", help="輸出 checkpoint；預設在原檔名加 _2to4")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="每個輸出 row 長度不是 4 的倍數時停止，不做零值 padding",
    )
    parser.add_argument("--demo", action="store_true", help="不讀 checkpoint 的規則示範")
    return parser.parse_args()


def prune_with_explicit_masks(array, strict: bool = False):
    """Prune padded four-lane groups and return explicit 4-bit masks.

    The returned model tensor keeps its original shape.  ``group_masks`` has
    shape ``[out_rows, ceil(row_width/4)]`` and includes mask bits for padded
    zero lanes, so every stored nibble remains a legal two-of-four mask.
    """
    values = np.asarray(array)
    if values.ndim < 2:
        raise ValueError("2:4 剪枝只套用在至少二維的權重 tensor")
    rows = values.reshape(values.shape[0], -1)
    row_width = rows.shape[1]
    pad_per_row = (-row_width) % 4
    if strict and pad_per_row:
        raise ValueError(
            f"每列長度 {row_width} 不是 4 的倍數；需要 padding={pad_per_row}"
        )

    padded_rows = np.pad(rows, ((0, 0), (0, pad_per_row)), mode="constant")
    pruned_padded, mask_padded, _ = prune_2to4(padded_rows, strict=True)
    group_masks = np.zeros((rows.shape[0], padded_rows.shape[1] // 4), dtype=np.uint8)
    mask_groups = mask_padded.reshape(rows.shape[0], -1, 4)
    for lane in range(4):
        group_masks |= mask_groups[:, :, lane].astype(np.uint8) << lane

    if not all(bin(int(mask)).count("1") == 2 for mask in group_masks.reshape(-1)):
        raise RuntimeError("內部錯誤：產生了不合法的 2:4 mask")
    original_mask = mask_padded[:, :row_width]
    pruned_rows = pruned_padded[:, :row_width]
    if np.any(pruned_rows[~original_mask] != 0):
        raise RuntimeError("內部錯誤：被 mask 移除的位置沒有歸零")

    original_values = int(values.size)
    grouped_storage_values = int(padded_rows.size)
    pruned_original_values = int(np.count_nonzero(~original_mask))
    tail_per_row = row_width % 4
    stats = {
        # Keep the original field names for older notebooks, then add the
        # padding-aware names used by the compressed exporter.
        "total_values": original_values,
        "grouped_values": grouped_storage_values,
        "pruned_values": pruned_original_values,
        "tail_values": rows.shape[0] * tail_per_row,
        "padded_values": rows.shape[0] * pad_per_row,
        "groups": int(group_masks.size),
        "row_width": row_width,
        "padded_row_width": int(padded_rows.shape[1]),
        "grouped_sparsity": (
            pruned_original_values / original_values if original_values else 0.0
        ),
    }
    return pruned_rows.reshape(values.shape), group_masks, stats


def demo() -> int:
    # Width 7 deliberately exercises the legal padded final group.
    values = np.array([[1.0, -7.0, 3.0, 2.0, -9.0, 4.0, 0.5]], dtype=np.float32)
    pruned, group_masks, stats = prune_with_explicit_masks(values)
    print("input       :", values.tolist())
    print("group masks :", [f"{int(mask):04b}" for mask in group_masks[0]])
    print("output      :", pruned.tolist())
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    assert all(bin(int(mask)).count("1") == 2 for mask in group_masks.reshape(-1))
    assert stats["padded_values"] == 1
    print("DEMO PASS")
    return 0


def main() -> int:
    args = parse_args()
    if args.demo:
        return demo()
    if not args.checkpoint:
        raise SystemExit("請提供 checkpoint，或使用 --demo")

    try:
        import torch
    except ImportError as exc:
        raise SystemExit("此操作需要 PyTorch；請先安裝 requirements.txt。") from exc

    source = Path(args.checkpoint)
    if not source.is_file():
        raise SystemExit(f"找不到 checkpoint：{source}")
    output = (
        Path(args.output)
        if args.output
        else source.with_name(f"{source.stem}_2to4{source.suffix}")
    )
    try:
        checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    except TypeError:
        checkpoint = torch.load(source, map_location="cpu")
    if not isinstance(checkpoint, dict) or "model_state" not in checkpoint:
        raise SystemExit("checkpoint 必須是 train_baseline.py 產生且含 model_state 的字典")

    new_state = {}
    explicit_masks = {}
    layer_stats = {}
    total_keys = (
        "total_values",
        "grouped_values",
        "pruned_values",
        "tail_values",
        "padded_values",
        "groups",
    )
    totals = {key: 0 for key in total_keys}
    for name, tensor in checkpoint["model_state"].items():
        if name.endswith(".weight") and tensor.ndim >= 2:
            pruned, group_masks, stats = prune_with_explicit_masks(
                tensor.detach().cpu().numpy(), strict=args.strict
            )
            new_state[name] = torch.from_numpy(pruned).to(dtype=tensor.dtype)
            explicit_masks[name] = torch.from_numpy(group_masks).to(dtype=torch.uint8)
            layer_stats[name] = stats
            for key in total_keys:
                totals[key] += int(stats[key])
        else:
            new_state[name] = tensor.detach().cpu()

    if not layer_stats:
        raise SystemExit("model_state 中沒有可剪枝的二維以上 weight tensor")
    totals["grouped_sparsity"] = (
        totals["pruned_values"] / totals["total_values"]
        if totals["total_values"]
        else 0.0
    )
    result = dict(checkpoint)
    result["model_state"] = new_state
    result["pruning_masks"] = explicit_masks
    result["pruning"] = {
        "scheme": "row_wise_2_of_4_with_zero_padding",
        "strict": args.strict,
        "mask_encoding": "uint8 nibble; bit0 is lane0; popcount is exactly 2",
        "mask_source": "explicit pruning decision (never inferred from quantized value)",
        "padding": "row tail padded with zeros before pruning",
        "totals": totals,
        "layers": layer_stats,
        "source_checkpoint": str(source),
    }
    result["format_version"] = max(int(result.get("format_version", 1)), 2)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, output)
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    print(f"explicit mask tensors: {len(explicit_masks)}")
    print(f"checkpoint: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
