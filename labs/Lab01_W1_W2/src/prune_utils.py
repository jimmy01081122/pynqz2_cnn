"""NumPy implementation of row-wise 2:4 structured pruning."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PruneStats:
    total_values: int
    grouped_values: int
    pruned_values: int
    tail_values: int

    @property
    def grouped_sparsity(self) -> float:
        if self.grouped_values == 0:
            return 0.0
        return self.pruned_values / self.grouped_values


def prune_2to4(array, strict: bool = False) -> tuple[np.ndarray, np.ndarray, PruneStats]:
    """Keep two largest magnitudes in every group of four per output row.

    Tensors are interpreted as [out_channels, remaining_dimensions...].
    A final group shorter than four is preserved unless strict=True.
    """
    values = np.asarray(array)
    if values.ndim < 2:
        raise ValueError("2:4 剪枝只套用在至少二維的權重 tensor")
    rows = values.reshape(values.shape[0], -1)
    row_width = rows.shape[1]
    grouped_width = (row_width // 4) * 4
    tail_per_row = row_width - grouped_width
    if strict and tail_per_row:
        raise ValueError(
            f"每列長度 {row_width} 不是 4 的倍數；tail={tail_per_row}"
        )

    pruned = rows.copy()
    mask = np.ones(rows.shape, dtype=bool)
    if grouped_width:
        groups = rows[:, :grouped_width].reshape(rows.shape[0], -1, 4)
        group_mask = np.ones(groups.shape, dtype=bool)
        # argsort is deterministic; ties keep the higher two indices.
        remove = np.argsort(np.abs(groups), axis=-1)[..., :2]
        np.put_along_axis(group_mask, remove, False, axis=-1)
        pruned[:, :grouped_width] *= group_mask.reshape(rows.shape[0], grouped_width)
        mask[:, :grouped_width] = group_mask.reshape(rows.shape[0], grouped_width)

    grouped_values = rows.shape[0] * grouped_width
    stats = PruneStats(
        total_values=values.size,
        grouped_values=grouped_values,
        pruned_values=grouped_values // 2,
        tail_values=rows.shape[0] * tail_per_row,
    )
    return pruned.reshape(values.shape), mask.reshape(values.shape), stats


def groups_are_2to4(array) -> bool:
    """Return True when each complete group has at most two non-zero values."""
    values = np.asarray(array)
    if values.ndim < 2:
        return False
    rows = values.reshape(values.shape[0], -1)
    grouped_width = (rows.shape[1] // 4) * 4
    if grouped_width == 0:
        return True
    groups = rows[:, :grouped_width].reshape(rows.shape[0], -1, 4)
    return bool(np.all(np.count_nonzero(groups, axis=-1) <= 2))

