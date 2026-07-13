#!/usr/bin/env python3
"""Dependency-light smoke tests for Lab01 utilities."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


LAB_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_DIR))

from scripts.prune_2to4 import prune_with_explicit_masks
from src.hex_utils import pack_signed, pack_sparse_2to4_rows
from src.prune_utils import groups_are_2to4, prune_2to4
from src.quant_utils import symmetric_quantize


def main() -> int:
    original = np.array([[1.0, -4.0, 3.0, 0.5, 9.0, 2.0, -8.0, 1.0]])
    pruned, _, stats = prune_2to4(original)
    assert groups_are_2to4(pruned)
    assert stats.pruned_values == 4
    assert np.count_nonzero(pruned) == 4

    padded_pruned, explicit_masks, padded_stats = prune_with_explicit_masks(
        np.array([[1.0, -4.0, 3.0, 0.5, 9.0, 2.0, -8.0]])
    )
    assert padded_pruned.shape == (1, 7)
    assert explicit_masks.shape == (1, 2)
    assert all(bin(int(mask)).count("1") == 2 for mask in explicit_masks.reshape(-1))
    assert padded_stats["padded_values"] == 1

    quantized = symmetric_quantize(np.array([-1.0, 0.0, 1.0]), bits=4)
    assert quantized.values.tolist() == [-7, 0, 7]
    assert np.allclose(quantized.dequantize(), [-1.0, 0.0, 1.0])

    packed = pack_signed([-8, -1, 0, 7, 1], bits=4, word_bits=16)
    assert packed.lines == ["70F8", "0001"]
    assert packed.padded_values == 3

    # Exact Lab04 combined-word examples.
    sparse_int8 = pack_sparse_2to4_rows([[1, 0, 2, 0]], [[0b0101]], bits=8)
    assert sparse_int8.lines == ["00050201"]
    sparse_int4 = pack_sparse_2to4_rows(
        [[1, 0, 2, 0, 0, -1, 0, 1]], [[0b0101, 0b1010]], bits=4
    )
    assert sparse_int4.lines == ["00A51F21"]

    # A retained weight may quantize to zero. The explicit 1001 mask still
    # selects lane0=0 and lane3=-2; qvalue != 0 would incorrectly lose lane0.
    retained_zero = pack_sparse_2to4_rows([[0, 9, 0, -2]], [[0b1001]], bits=8)
    assert retained_zero.lines == ["0009FE00"]

    # INT4 stores two groups per word. If a row has one group, the second is
    # zero-valued but uses legal mask 0011, never invalid 0000.
    legal_padding = pack_sparse_2to4_rows([[1, 0, 2, 0]], [[0b0101]], bits=4)
    assert legal_padding.lines == ["00350021"]
    assert legal_padding.padded_groups == 1

    try:
        pack_sparse_2to4_rows([[1, 0, 2, 0]], [[0b0001]], bits=8)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid 2:4 mask was not rejected")

    print("PASS prune_2to4")
    print("PASS explicit pruning masks and row padding")
    print("PASS symmetric_quantize")
    print("PASS dense signed hex packing")
    print("PASS Lab04 sparse INT8/INT4 combined-word packing")
    print("PASS retained-zero mask and legal padding group")
    print("Lab01 smoke test: PASS（未使用網路、未要求 PyTorch）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
