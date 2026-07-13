#!/usr/bin/env python3
"""Train the small CNN with an offline-first data policy."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path


LAB_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_DIR))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-mode", choices=("synthetic", "cifar10"), default="synthetic")
    parser.add_argument("--data-root", default=str(LAB_DIR / "data"))
    parser.add_argument(
        "--download",
        action="store_true",
        help="明確允許 torchvision 下載 CIFAR-10；預設絕不下載",
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--train-samples", type=int, default=1024)
    parser.add_argument("--test-samples", type=int, default=256)
    parser.add_argument("--max-train-steps", type=int, default=0)
    parser.add_argument("--output", default=str(LAB_DIR / "artifacts" / "baseline.pt"))
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="強制 synthetic、1 epoch、64/32 samples、最多 2 training steps",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只顯示執行計畫，不載入 PyTorch、不建立檔案",
    )
    return parser.parse_args()


def validate_args(args) -> None:
    positive = ("epochs", "batch_size", "learning_rate", "train_samples", "test_samples")
    for name in positive:
        if getattr(args, name) <= 0:
            raise SystemExit(f"--{name.replace('_', '-')} 必須大於 0")
    if args.data_mode != "cifar10" and args.download:
        raise SystemExit("--download 只可搭配 --data-mode cifar10")


def evaluate(model, loader, criterion, device):
    import torch

    model.eval()
    loss_sum = 0.0
    correct = 0
    count = 0
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            logits = model(images)
            loss_sum += float(criterion(logits, labels)) * labels.size(0)
            correct += int((logits.argmax(dim=1) == labels).sum())
            count += labels.size(0)
    return {"loss": loss_sum / count, "accuracy": correct / count, "samples": count}


def main() -> int:
    args = parse_args()
    if args.smoke:
        args.data_mode = "synthetic"
        args.download = False
        args.epochs = 1
        args.batch_size = min(args.batch_size, 16)
        args.train_samples = 64
        args.test_samples = 32
        args.max_train_steps = 2
    validate_args(args)

    plan = {
        "data_mode": args.data_mode,
        "download": args.download,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "train_samples": args.train_samples if args.data_mode == "synthetic" else None,
        "test_samples": args.test_samples if args.data_mode == "synthetic" else None,
        "max_train_steps": args.max_train_steps,
        "output": args.output,
        "smoke_only": args.smoke,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        print("DRY-RUN PASS：未載入 PyTorch、未下載資料、未建立 checkpoint。")
        return 0

    try:
        import numpy as np
        import torch
        import torch.nn as nn
    except ImportError as exc:
        raise SystemExit(
            "缺少 PyTorch 或 NumPy。請先安裝 requirements.txt，"
            "或使用 --dry-run 做零相依檢查。"
        ) from exc

    from src.data import CIFAR10_CLASSES, make_loaders
    from src.tiny_cnn import build_model

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        if args.device == "cuda" and not torch.cuda.is_available():
            raise SystemExit("指定 --device cuda，但 torch.cuda.is_available() 為 False")
        device = torch.device(args.device)

    train_loader, test_loader = make_loaders(
        mode=args.data_mode,
        data_root=args.data_root,
        batch_size=args.batch_size,
        workers=args.workers,
        download=args.download,
        seed=args.seed,
        train_samples=args.train_samples,
        test_samples=args.test_samples,
    )
    model = build_model().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )

    start = time.time()
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        seen = 0
        for step, (images, labels) in enumerate(train_loader, start=1):
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            running_loss += float(loss) * labels.size(0)
            seen += labels.size(0)
            if args.max_train_steps and step >= args.max_train_steps:
                break
        metrics = evaluate(model, test_loader, criterion, device)
        metrics.update(epoch=epoch, train_loss=running_loss / seen)
        history.append(metrics)
        print(
            f"epoch {epoch:02d} train_loss={metrics['train_loss']:.4f} "
            f"test_loss={metrics['loss']:.4f} accuracy={metrics['accuracy']:.4f}"
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "format_version": 1,
        "model_name": "SmallCIFAR10CNN",
        "model_state": {key: value.detach().cpu() for key, value in model.state_dict().items()},
        "classes": list(CIFAR10_CLASSES),
        "train_config": plan | {
            "seed": args.seed,
            "device": str(device),
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
        },
        "history": history,
        "final_metrics": history[-1],
        "elapsed_seconds": time.time() - start,
        "data_provenance": (
            "synthetic_smoke_not_for_accuracy"
            if args.data_mode == "synthetic"
            else "torchvision_cifar10"
        ),
    }
    torch.save(checkpoint, output)
    print(f"checkpoint: {output.resolve()}")
    if args.data_mode == "synthetic":
        print("提醒：synthetic 準確率不可作為專案成果。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

