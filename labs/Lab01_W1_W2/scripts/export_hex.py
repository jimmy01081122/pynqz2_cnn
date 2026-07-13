#!/usr/bin/env python3
"""Export dense or Lab04-compatible compressed 2:4 readmemh files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


LAB_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_DIR))

from src.hex_utils import pack_signed, pack_sparse_2to4_rows


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", nargs="?", help="quantize_ptq.py 產生的 checkpoint")
    parser.add_argument("--out-dir", default=str(LAB_DIR / "artifacts" / "hex"))
    parser.add_argument("--bits", type=int, choices=(4, 8), help="預設由 checkpoint 判斷")
    parser.add_argument("--word-bits", type=int, default=32)
    parser.add_argument(
        "--msb-first",
        action="store_true",
        help="dense 模式把第一個值放最高 lane；預設最低 lane",
    )
    parser.add_argument(
        "--sparse-2to4",
        action="store_true",
        help="用 checkpoint 內 explicit pruning_masks 匯出 Lab04 combined word",
    )
    parser.add_argument("--demo", action="store_true", help="顯示打包規則，不建立檔案")
    return parser.parse_args()


def safe_name(tensor_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "__", tensor_name).strip("_")


def demo(bits: int, word_bits: int, msb_first: bool, sparse_2to4: bool) -> int:
    if sparse_2to4:
        if word_bits != 32 or msb_first:
            raise SystemExit("sparse combined-word demo 固定為 32-bit、low-lane-first")
        if bits == 8:
            packed = pack_sparse_2to4_rows([[1, 0, 2, 0]], [[0b0101]], bits=8)
            expected = ["00050201"]
        else:
            packed = pack_sparse_2to4_rows(
                [[1, 0, 2, 0, 0, -1, 0, 1]], [[0b0101, 0b1010]], bits=4
            )
            expected = ["00A51F21"]
        print(f"Lab04 sparse INT{bits}: {packed.lines}")
        assert packed.lines == expected
        print("DEMO PASS")
        return 0

    minimum = -(1 << (bits - 1))
    maximum = (1 << (bits - 1)) - 1
    values = [minimum, -1, 0, maximum, 1]
    packed = pack_signed(values, bits, word_bits, lsb_first=not msb_first)
    print(f"values={values}")
    print(
        f"INT{bits}, word_bits={word_bits}, "
        f"order={'MSB-first' if msb_first else 'LSB-first'}"
    )
    for line in packed.lines:
        print(line)
    print(f"valid={packed.valid_values}, padded={packed.padded_values}")
    print("DEMO PASS")
    return 0


def main() -> int:
    args = parse_args()
    if args.word_bits % 4:
        raise SystemExit("--word-bits 必須是 4 的倍數")
    if args.sparse_2to4 and (args.word_bits != 32 or args.msb_first):
        raise SystemExit("--sparse-2to4 固定使用 32-bit combined word 與 low-lane-first")
    if args.demo:
        return demo(args.bits or 8, args.word_bits, args.msb_first, args.sparse_2to4)
    if not args.checkpoint:
        raise SystemExit("請提供 checkpoint，或使用 --demo")

    try:
        import torch
    except ImportError as exc:
        raise SystemExit("讀取 checkpoint 需要 PyTorch；請先安裝 requirements.txt。") from exc

    source = Path(args.checkpoint)
    if not source.is_file():
        raise SystemExit(f"找不到 checkpoint：{source}")
    try:
        checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    except TypeError:
        checkpoint = torch.load(source, map_location="cpu")
    quantized_state = checkpoint.get("quantized_state") if isinstance(checkpoint, dict) else None
    if not quantized_state:
        raise SystemExit("checkpoint 沒有 quantized_state；請先執行 quantize_ptq.py")
    bits = args.bits or int(checkpoint.get("quantization", {}).get("bits", 0))
    if bits not in (4, 8):
        raise SystemExit("無法判斷 INT4/INT8，請明確提供 --bits")
    if args.word_bits % bits:
        raise SystemExit("--word-bits 必須是 --bits 的整數倍")

    pruning_masks = checkpoint.get("pruning_masks", {})
    if args.sparse_2to4 and not pruning_masks:
        raise SystemExit(
            "checkpoint 沒有 explicit pruning_masks；請重新執行新版 prune_2to4.py。"
            "為避免 retained zero 遺失，本工具不會從 qvalue != 0 猜 mask。"
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    weight_scales = checkpoint.get("weight_scales", {})
    manifest = {
        "format": (
            "lab04_sparse_2to4_combined_word_v1"
            if args.sparse_2to4
            else "readmemh_packed_signed_v1"
        ),
        "source_checkpoint": str(source.resolve()),
        "bits_per_value": bits,
        "word_bits": args.word_bits,
        "first_value_lane": "msb" if args.msb_first else "lsb",
        "twos_complement": True,
        "mask_source": (
            "checkpoint.pruning_masks (explicit)" if args.sparse_2to4 else None
        ),
        "tensors": [],
    }
    for tensor_name in sorted(quantized_state):
        tensor = quantized_state[tensor_name].detach().cpu()
        filename = f"{safe_name(tensor_name)}.memh"

        if args.sparse_2to4:
            if tensor.ndim < 2:
                raise SystemExit(f"{tensor_name} 不是二維以上 weight tensor")
            if tensor_name not in pruning_masks:
                raise SystemExit(f"explicit pruning_masks 缺少 tensor：{tensor_name}")
            mask_tensor = pruning_masks[tensor_name]
            if hasattr(mask_tensor, "detach"):
                mask_tensor = mask_tensor.detach().cpu()
            rows = tensor.reshape(tensor.shape[0], -1).tolist()
            try:
                mask_rows = mask_tensor.reshape(tensor.shape[0], -1).tolist()
            except (AttributeError, RuntimeError, ValueError) as exc:
                raise SystemExit(f"{tensor_name} 的 explicit mask shape 不合法") from exc
            packed = pack_sparse_2to4_rows(rows, mask_rows, bits=bits)
            sparse_fields = {
                "row_count": packed.row_count,
                "row_width": len(rows[0]),
                "groups_per_row": packed.groups_per_row,
                "groups_per_word": packed.groups_per_word,
                "words_per_row": packed.words_per_row,
                "valid_groups": packed.valid_groups,
                "padded_groups": packed.padded_groups,
                "padding_group_mask": "0011" if packed.padded_groups else None,
            }
        else:
            values = tensor.reshape(-1).tolist()
            packed = pack_signed(
                values,
                bits=bits,
                word_bits=args.word_bits,
                lsb_first=not args.msb_first,
            )
            sparse_fields = {"values_per_word": packed.values_per_word}

        text = "\n".join(packed.lines) + "\n"
        (out_dir / filename).write_text(text, encoding="ascii")
        manifest["tensors"].append(
            {
                "name": tensor_name,
                "file": filename,
                "shape": list(tensor.shape),
                "scale": float(weight_scales.get(tensor_name, 1.0)),
                "valid_values": packed.valid_values,
                "padded_values": packed.padded_values,
                "packed_words": len(packed.lines),
                "sha256": hashlib.sha256(text.encode("ascii")).hexdigest(),
                **sparse_fields,
            }
        )
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"exported tensors: {len(manifest['tensors'])}")
    print(f"format: {manifest['format']}")
    print(f"manifest: {manifest_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
