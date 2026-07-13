#!/usr/bin/env python3
"""PTQ-ish weight quantization plus activation max-abs calibration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


LAB_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_DIR))

from src.quant_utils import activation_scale, symmetric_quantize


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", nargs="?", help="baseline 或 2:4 checkpoint")
    parser.add_argument("--bits", type=int, choices=(4, 8), default=8)
    parser.add_argument("--output", help="輸出 checkpoint")
    parser.add_argument(
        "--calibration-mode", choices=("synthetic", "cifar10"), default="synthetic"
    )
    parser.add_argument("--data-root", default=str(LAB_DIR / "data"))
    parser.add_argument(
        "--download",
        action="store_true",
        help="明確允許下載 CIFAR-10；預設絕不下載",
    )
    parser.add_argument("--calibration-samples", type=int, default=128)
    parser.add_argument("--calibration-batches", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--demo", action="store_true", help="不讀 checkpoint 的量化示範")
    return parser.parse_args()


def demo(bits: int) -> int:
    values = np.array([-1.0, -0.51, -0.03, 0.0, 0.28, 0.75, 1.0])
    quantized = symmetric_quantize(values, bits)
    print(f"INT{bits} scale={quantized.scale:.9g}")
    print("float      :", values.tolist())
    print("integer    :", quantized.values.tolist())
    print("dequantized:", quantized.dequantize().tolist())
    print("DEMO PASS")
    return 0


def evaluate(model, loader, device):
    import torch

    correct = 0
    count = 0
    model.eval()
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            correct += int((model(images).argmax(dim=1) == labels).sum())
            count += labels.size(0)
    return correct / count if count else 0.0


def main() -> int:
    args = parse_args()
    if args.demo:
        return demo(args.bits)
    if not args.checkpoint:
        raise SystemExit("請提供 checkpoint，或使用 --demo")
    if args.calibration_mode != "cifar10" and args.download:
        raise SystemExit("--download 只可搭配 --calibration-mode cifar10")

    try:
        import torch
    except ImportError as exc:
        raise SystemExit("此操作需要 PyTorch；請先安裝 requirements.txt。") from exc

    from src.data import make_loaders
    from src.tiny_cnn import build_model, is_quantizable_module

    source = Path(args.checkpoint)
    if not source.is_file():
        raise SystemExit(f"找不到 checkpoint：{source}")
    output = (
        Path(args.output)
        if args.output
        else source.with_name(f"{source.stem}_int{args.bits}{source.suffix}")
    )
    try:
        checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    except TypeError:
        checkpoint = torch.load(source, map_location="cpu")
    if not isinstance(checkpoint, dict) or "model_state" not in checkpoint:
        raise SystemExit("checkpoint 必須含 model_state")

    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        if args.device == "cuda" and not torch.cuda.is_available():
            raise SystemExit("指定 --device cuda，但 CUDA 不可用")
        device = torch.device(args.device)

    model = build_model()
    model.load_state_dict(checkpoint["model_state"], strict=True)
    model.to(device).eval()

    train_loader, calibration_loader = make_loaders(
        mode=args.calibration_mode,
        data_root=args.data_root,
        batch_size=args.batch_size,
        workers=args.workers,
        download=args.download,
        seed=args.seed,
        train_samples=args.calibration_samples,
        test_samples=args.calibration_samples,
    )
    del train_loader

    activation_max_abs: dict[str, float] = {}
    handles = []
    for name, module in model.named_modules():
        if is_quantizable_module(module):
            def hook(_module, _inputs, output_tensor, layer_name=name):
                value = float(output_tensor.detach().abs().max().cpu())
                activation_max_abs[layer_name] = max(
                    activation_max_abs.get(layer_name, 0.0), value
                )

            handles.append(module.register_forward_hook(hook))
    with torch.no_grad():
        for batch_index, (images, _) in enumerate(calibration_loader, start=1):
            model(images.to(device))
            if batch_index >= args.calibration_batches:
                break
    for handle in handles:
        handle.remove()

    quantized_state = {}
    weight_scales = {}
    dequantized_state = {}
    for name, tensor in checkpoint["model_state"].items():
        cpu_tensor = tensor.detach().cpu()
        if name.endswith(".weight") and cpu_tensor.ndim >= 2:
            quantized = symmetric_quantize(cpu_tensor.numpy(), bits=args.bits)
            quantized_state[name] = torch.from_numpy(quantized.values)
            weight_scales[name] = quantized.scale
            dequantized_state[name] = torch.from_numpy(quantized.dequantize()).to(
                dtype=cpu_tensor.dtype
            )
        else:
            dequantized_state[name] = cpu_tensor

    model.load_state_dict(dequantized_state, strict=True)
    model.to(device)
    dequantized_accuracy = evaluate(model, calibration_loader, device)
    activation_scales = {
        name: activation_scale(value, args.bits)
        for name, value in activation_max_abs.items()
    }

    result = dict(checkpoint)
    result["model_state"] = dequantized_state
    result["quantized_state"] = quantized_state
    result["weight_scales"] = weight_scales
    result["activation_scales"] = activation_scales
    result["quantization"] = {
        "scheme": "symmetric_per_tensor_weight_ptqish",
        "bits": args.bits,
        "integer_range": [-(1 << (args.bits - 1)), (1 << (args.bits - 1)) - 1],
        "calibration_mode": args.calibration_mode,
        "calibration_batches": min(args.calibration_batches, len(calibration_loader)),
        "calibration_samples_requested": args.calibration_samples,
        "dequantized_calibration_accuracy": dequantized_accuracy,
        "bit_accurate_rtl": False,
        "source_checkpoint": str(source),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result, output)
    print(json.dumps(result["quantization"], ensure_ascii=False, indent=2))
    print(f"weight tensors: {len(quantized_state)}")
    print(f"checkpoint: {output.resolve()}")
    if args.calibration_mode == "synthetic":
        print("提醒：synthetic calibration accuracy 不可作為專案成果。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

