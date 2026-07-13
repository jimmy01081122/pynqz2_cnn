"""Pack signed integers into fixed-width words for readmemh."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackedWords:
    lines: list[str]
    valid_values: int
    padded_values: int
    values_per_word: int


@dataclass(frozen=True)
class SparsePackedWords:
    """Lab04-compatible packed 2:4 rows.

    ``padded_values`` counts zero lanes added to complete a four-lane group.
    ``padded_groups`` counts legal all-zero groups added only to complete an
    INT4 two-group word. Padding groups use mask ``0011`` rather than the
    illegal mask ``0000``.
    """

    lines: list[str]
    valid_values: int
    padded_values: int
    valid_groups: int
    padded_groups: int
    groups_per_word: int
    groups_per_row: int
    words_per_row: int
    row_count: int


def signed_to_twos_complement(value: int, bits: int) -> int:
    minimum = -(1 << (bits - 1))
    maximum = (1 << (bits - 1)) - 1
    if value < minimum or value > maximum:
        raise ValueError(f"{value} 超出 signed INT{bits} 範圍 [{minimum}, {maximum}]")
    return value & ((1 << bits) - 1)


def pack_signed(
    values,
    bits: int,
    word_bits: int = 32,
    lsb_first: bool = True,
) -> PackedWords:
    """Pack values; the first value occupies the least-significant lane by default."""
    if bits <= 0 or word_bits <= 0 or word_bits % bits:
        raise ValueError("word_bits 必須是 bits 的正整數倍")
    lanes = word_bits // bits
    flattened = [int(value) for value in values]
    padded = (-len(flattened)) % lanes
    flattened.extend([0] * padded)
    width = word_bits // 4
    lines: list[str] = []
    for start in range(0, len(flattened), lanes):
        chunk = flattened[start : start + lanes]
        word = 0
        for lane, value in enumerate(chunk):
            encoded = signed_to_twos_complement(value, bits)
            shift_lane = lane if lsb_first else lanes - lane - 1
            word |= encoded << (shift_lane * bits)
        lines.append(f"{word:0{width}X}")
    return PackedWords(lines, len(values), padded, lanes)


def _popcount4(mask: int) -> int:
    return sum((mask >> lane) & 1 for lane in range(4))


def _encode_sparse_group(group_values, mask: int, bits: int) -> tuple[int, int]:
    """Select two values using an explicit mask, in low-lane-first order."""
    if mask < 0 or mask > 0xF or _popcount4(mask) != 2:
        raise ValueError(f"2:4 mask 必須剛好有兩個 1，收到 0x{mask:X}")
    selected = [
        int(group_values[lane]) for lane in range(4) if (mask >> lane) & 1
    ]
    return (
        signed_to_twos_complement(selected[0], bits),
        signed_to_twos_complement(selected[1], bits),
    )


def pack_sparse_2to4_rows(rows, group_masks, bits: int) -> SparsePackedWords:
    """Pack row-wise 2:4 data into the exact 32-bit Lab04 weight format.

    ``group_masks`` contains one explicit 4-bit mask per group. The mask is
    never inferred from whether a quantized value is zero: a retained value is
    allowed to quantize to zero.

    INT8 word layout::

        [7:0]=value0, [15:8]=value1, [19:16]=mask

    INT4 word layout::

        [3:0]=g0v0, [7:4]=g0v1, [11:8]=g1v0, [15:12]=g1v1,
        [19:16]=g0mask, [23:20]=g1mask
    """
    if bits not in (4, 8):
        raise ValueError("sparse 2:4 combined-word 格式只支援 INT4 或 INT8")

    row_lists = [[int(value) for value in row] for row in rows]
    mask_lists = [[int(mask) for mask in row_masks] for row_masks in group_masks]
    if not row_lists:
        raise ValueError("至少需要一列權重")
    if len(row_lists) != len(mask_lists):
        raise ValueError("權重列數與 mask 列數不同")

    row_width = len(row_lists[0])
    if row_width == 0 or any(len(row) != row_width for row in row_lists):
        raise ValueError("所有權重列必須有相同且非零的長度")
    groups_per_row = (row_width + 3) // 4
    if any(len(masks) != groups_per_row for masks in mask_lists):
        raise ValueError("每列 explicit mask 數量必須等於 ceil(row_width/4)")

    groups_per_word = 1 if bits == 8 else 2
    words_per_row = (groups_per_row + groups_per_word - 1) // groups_per_word
    padded_values_per_row = groups_per_row * 4 - row_width
    padded_groups_per_row = words_per_row * groups_per_word - groups_per_row
    lines: list[str] = []

    for row, masks in zip(row_lists, mask_lists):
        padded_row = row + [0] * padded_values_per_row
        encoded_groups: list[tuple[int, int, int]] = []
        for group_index, mask in enumerate(masks):
            start = group_index * 4
            value0, value1 = _encode_sparse_group(
                padded_row[start : start + 4], mask, bits
            )
            encoded_groups.append((value0, value1, mask))

        # An all-zero padding group still needs a legal mask because Lab03 and
        # Lab04 intentionally reject 0000. 0011 selects two stored zeros.
        encoded_groups.extend([(0, 0, 0b0011)] * padded_groups_per_row)

        if bits == 8:
            for value0, value1, mask in encoded_groups:
                word = value0 | (value1 << 8) | (mask << 16)
                lines.append(f"{word:08X}")
        else:
            for group_index in range(0, len(encoded_groups), 2):
                g0v0, g0v1, g0mask = encoded_groups[group_index]
                g1v0, g1v1, g1mask = encoded_groups[group_index + 1]
                word = (
                    g0v0
                    | (g0v1 << 4)
                    | (g1v0 << 8)
                    | (g1v1 << 12)
                    | (g0mask << 16)
                    | (g1mask << 20)
                )
                lines.append(f"{word:08X}")

    return SparsePackedWords(
        lines=lines,
        valid_values=len(row_lists) * row_width,
        padded_values=len(row_lists) * padded_values_per_row,
        valid_groups=len(row_lists) * groups_per_row,
        padded_groups=len(row_lists) * padded_groups_per_row,
        groups_per_word=groups_per_word,
        groups_per_row=groups_per_row,
        words_per_row=words_per_row,
        row_count=len(row_lists),
    )
