#!/usr/bin/env python3
"""Report the course environment without installing or downloading anything."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import platform
import sys
from pathlib import Path


REQUIRED = ("numpy", "torch", "torchvision")


def inspect_module(name: str) -> dict[str, object]:
    found = importlib.util.find_spec(name) is not None
    result: dict[str, object] = {"found": found, "version": None}
    if found:
        try:
            module = importlib.import_module(name)
            result["version"] = getattr(module, "__version__", "unknown")
        except Exception as exc:  # Environment diagnosis should keep going.
            result["import_error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data", help="CIFAR-10 根目錄")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="缺少套件或 Python 太舊時回傳非零狀態",
    )
    args = parser.parse_args()

    modules = {name: inspect_module(name) for name in REQUIRED}
    cuda: dict[str, object] = {"available": False}
    if modules["torch"]["found"] and "import_error" not in modules["torch"]:
        import torch

        cuda = {
            "available": bool(torch.cuda.is_available()),
            "device_count": int(torch.cuda.device_count()),
            "device_name": (
                torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
            ),
        }

    data_root = Path(args.data_root).expanduser()
    cifar_local = (data_root / "cifar-10-batches-py").is_dir()
    result = {
        "python": platform.python_version(),
        "python_ok": sys.version_info >= (3, 10),
        "platform": platform.platform(),
        "modules": modules,
        "cuda": cuda,
        "cifar10_local": cifar_local,
        "data_root": str(data_root.resolve()),
        "network_action_performed": False,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Python {result['python']}: {'OK' if result['python_ok'] else 'TOO OLD'}")
        for name, info in modules.items():
            status = "OK" if info["found"] and "import_error" not in info else "MISSING"
            detail = info.get("version") or info.get("import_error") or ""
            print(f"{name:12s}: {status:7s} {detail}")
        cuda_text = (
            f"可用（{cuda.get('device_name')}）" if cuda["available"] else "不可用，將使用 CPU"
        )
        print(f"CUDA        : {cuda_text}")
        print(f"CIFAR-10    : {'FOUND' if cifar_local else 'NOT FOUND'} at {data_root}")
        print("網路動作    : 無")

    missing = any(
        not info["found"] or "import_error" in info for info in modules.values()
    )
    failed = not result["python_ok"] or missing
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

