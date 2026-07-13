"""Framework-independent symmetric quantization helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class QuantizedArray:
    values: np.ndarray
    scale: float
    bits: int

    def dequantize(self) -> np.ndarray:
        return self.values.astype(np.float32) * np.float32(self.scale)


def quant_limits(bits: int) -> tuple[int, int]:
    if bits < 2 or bits > 16:
        raise ValueError("bits 必須介於 2 與 16")
    return -(1 << (bits - 1)), (1 << (bits - 1)) - 1


def symmetric_quantize(array, bits: int = 8) -> QuantizedArray:
    """Per-tensor, signed, symmetric, round-to-nearest quantization."""
    values = np.asarray(array, dtype=np.float32)
    qmin, qmax = quant_limits(bits)
    max_abs = float(np.max(np.abs(values))) if values.size else 0.0
    scale = max_abs / qmax if max_abs > 0.0 else 1.0
    quantized = np.clip(np.rint(values / scale), qmin, qmax)
    dtype = np.int8 if bits <= 8 else np.int16
    return QuantizedArray(quantized.astype(dtype), float(scale), bits)


def activation_scale(max_abs: float, bits: int = 8) -> float:
    """Turn a calibration max-abs value into a signed symmetric scale."""
    _, qmax = quant_limits(bits)
    return float(max_abs) / qmax if max_abs > 0.0 else 1.0

