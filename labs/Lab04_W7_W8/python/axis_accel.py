#!/usr/bin/env python3
"""PYNQ driver and pure-Python golden model for the Lab04 accelerator.

The module deliberately imports PYNQ and NumPy only when hardware is used.  Its
packing helpers and golden model can therefore be imported and tested on a host
computer that does not have PYNQ installed.
"""

from __future__ import annotations

import argparse
from typing import Any, List, Sequence, Tuple


U32_MASK = 0xFFFF_FFFF


def _u32(value: int) -> int:
    return int(value) & U32_MASK


def signed32(value: int) -> int:
    """Interpret the low 32 bits of *value* as a signed two's-complement int."""

    value = _u32(value)
    return value - (1 << 32) if value & (1 << 31) else value


def _signed_field(word: int, offset: int, width: int) -> int:
    mask = (1 << width) - 1
    value = (int(word) >> offset) & mask
    return value - (1 << width) if value & (1 << (width - 1)) else value


def _pack_signed_lanes(values: Sequence[int], width: int, count: int) -> int:
    if len(values) != count:
        raise ValueError("expected {} values, got {}".format(count, len(values)))
    minimum = -(1 << (width - 1))
    maximum = (1 << (width - 1)) - 1
    lane_mask = (1 << width) - 1
    result = 0
    for index, raw_value in enumerate(values):
        value = int(raw_value)
        if not minimum <= value <= maximum:
            raise ValueError(
                "lane {} value {} is outside signed INT{} range [{}, {}]".format(
                    index, value, width, minimum, maximum
                )
            )
        result |= (value & lane_mask) << (index * width)
    return _u32(result)


def pack_int8_word(values: Sequence[int]) -> int:
    """Pack four signed INT8 lanes; values[0] occupies bits 7:0."""

    return _pack_signed_lanes(values, width=8, count=4)


def pack_int4_word(values: Sequence[int]) -> int:
    """Pack eight signed INT4 lanes; values[0] occupies bits 3:0."""

    return _pack_signed_lanes(values, width=4, count=8)


def _validate_2of4_mask(mask: int, name: str = "mask") -> int:
    mask = int(mask)
    if mask < 0 or mask > 0xF:
        raise ValueError("{} must be a 4-bit integer".format(name))
    if bin(mask).count("1") != 2:
        raise ValueError("{} must contain exactly two set bits".format(name))
    return mask


def pack_sparse_int8_weight(values: Sequence[int], mask: int) -> int:
    """Pack one INT8 2:4 group into the RTL's 32-bit weight format."""

    mask = _validate_2of4_mask(mask)
    packed_values = _pack_signed_lanes(values, width=8, count=2)
    return packed_values | (mask << 16)


def pack_sparse_int4_weight(
    group0_values: Sequence[int],
    group0_mask: int,
    group1_values: Sequence[int],
    group1_mask: int,
) -> int:
    """Pack two INT4 2:4 groups into the RTL's 32-bit weight format."""

    group0_mask = _validate_2of4_mask(group0_mask, "group0_mask")
    group1_mask = _validate_2of4_mask(group1_mask, "group1_mask")
    packed0 = _pack_signed_lanes(group0_values, width=4, count=2)
    packed1 = _pack_signed_lanes(group1_values, width=4, count=2)
    return packed0 | (packed1 << 8) | (group0_mask << 16) | (group1_mask << 20)


def _dot_product(
    activation_word: int,
    weight_word: int,
    mode_int4: bool,
    enable_2to4: bool,
) -> Tuple[int, bool]:
    activation_word = _u32(activation_word)
    weight_word = _u32(weight_word)

    if not enable_2to4:
        width = 4 if mode_int4 else 8
        lanes = 8 if mode_int4 else 4
        total = sum(
            _signed_field(activation_word, lane * width, width)
            * _signed_field(weight_word, lane * width, width)
            for lane in range(lanes)
        )
        return total, False

    if not mode_int4:
        mask = (weight_word >> 16) & 0xF
        if bin(mask).count("1") != 2:
            return 0, True
        compressed_values = [
            _signed_field(weight_word, index * 8, 8) for index in range(2)
        ]
        value_index = 0
        total = 0
        for lane in range(4):
            if mask & (1 << lane):
                total += _signed_field(activation_word, lane * 8, 8) * compressed_values[value_index]
                value_index += 1
        return total, False

    total = 0
    for group in range(2):
        mask = (weight_word >> (16 + group * 4)) & 0xF
        if bin(mask).count("1") != 2:
            return 0, True
        compressed_values = [
            _signed_field(weight_word, group * 8 + index * 4, 4)
            for index in range(2)
        ]
        value_index = 0
        for lane in range(4):
            if mask & (1 << lane):
                activation_lane = group * 4 + lane
                total += (
                    _signed_field(activation_word, activation_lane * 4, 4)
                    * compressed_values[value_index]
                )
                value_index += 1
    return total, False


def golden_packet(
    activation_words: Sequence[int],
    weight_word: int,
    bias: int = 0,
    mode_int4: bool = False,
    enable_2to4: bool = False,
) -> Tuple[List[int], bool]:
    """Return running 32-bit results and the packet's expected mask-error flag.

    The first beat starts at ``bias``.  Every following beat accumulates into the
    same packet.  Results are returned as unsigned 32-bit words, matching the DMA
    buffer; call :func:`signed32` when displaying them as signed integers.
    """

    if not activation_words:
        raise ValueError("activation_words must contain at least one AXIS beat")

    accumulator = signed32(bias)
    results: List[int] = []
    mask_error = False
    for activation_word in activation_words:
        dot, beat_error = _dot_product(
            activation_word, weight_word, bool(mode_int4), bool(enable_2to4)
        )
        accumulator = signed32(accumulator + dot)
        results.append(_u32(accumulator))
        mask_error = mask_error or beat_error
    return results, mask_error


class AxisDotAccelerator:
    """Small PYNQ wrapper around ``axis_dma_0`` and the two AXI GPIO blocks."""

    MODE_INT4 = 1 << 0
    ENABLE_2TO4 = 1 << 1
    CLEAR_STATUS = 1 << 2
    CONTROL_MASK = MODE_INT4 | ENABLE_2TO4 | CLEAR_STATUS

    def __init__(
        self,
        overlay: Any,
        dma_name: str = "axis_dma_0",
        control_gpio_name: str = "axi_gpio_control",
        params_gpio_name: str = "axi_gpio_params",
    ) -> None:
        self.overlay = overlay
        try:
            self.dma = getattr(overlay, dma_name)
            self.control_gpio = getattr(overlay, control_gpio_name)
            self.params_gpio = getattr(overlay, params_gpio_name)
        except AttributeError as exc:
            available = sorted(getattr(overlay, "ip_dict", {}).keys())
            raise ValueError(
                "The overlay is missing a Lab04 IP. Available IP names: {}".format(
                    ", ".join(available) if available else "unknown"
                )
            ) from exc
        self._control_word = 0

    @classmethod
    def from_bitfile(cls, bitfile: str, download: bool = True) -> "AxisDotAccelerator":
        """Load a same-basename .bit/.hwh pair and construct the driver."""

        try:
            from pynq import Overlay
        except ImportError as exc:
            raise RuntimeError("PYNQ is required only when using real hardware") from exc
        return cls(Overlay(bitfile, download=download))

    def configure(
        self,
        weight_word: int,
        bias: int = 0,
        mode_int4: bool = False,
        enable_2to4: bool = False,
        clear_status: bool = True,
    ) -> None:
        """Write stable parameters before starting a DMA packet."""

        self.params_gpio.channel1.write(_u32(weight_word), U32_MASK)
        self.params_gpio.channel2.write(_u32(bias), U32_MASK)
        self._control_word = (
            (self.MODE_INT4 if mode_int4 else 0)
            | (self.ENABLE_2TO4 if enable_2to4 else 0)
        )
        self.control_gpio.channel1.write(self._control_word, self.CONTROL_MASK)
        if clear_status:
            self.clear_status()

    def clear_status(self) -> None:
        """Pulse the sticky-mask-error clear bit for at least one AXI clock."""

        self.control_gpio.channel1.write(
            self._control_word | self.CLEAR_STATUS, self.CONTROL_MASK
        )
        self.control_gpio.channel1.write(self._control_word, self.CONTROL_MASK)

    @property
    def mask_error(self) -> bool:
        return bool(int(self.control_gpio.channel2.read()) & 0x1)

    @staticmethod
    def _release_buffer(buffer: Any) -> None:
        if buffer is None:
            return
        if hasattr(buffer, "freebuffer"):
            buffer.freebuffer()
        elif hasattr(buffer, "close"):
            buffer.close()

    def run(self, activation_words: Sequence[int]) -> List[int]:
        """Send one DMA packet and receive one running result per input beat."""

        if not activation_words:
            raise ValueError("activation_words must contain at least one AXIS beat")
        try:
            import numpy as np
            from pynq import allocate
        except ImportError as exc:
            raise RuntimeError("NumPy and PYNQ are required for DMA transfers") from exc

        send_buffer = None
        receive_buffer = None
        try:
            count = len(activation_words)
            send_buffer = allocate(shape=(count,), dtype=np.uint32)
            receive_buffer = allocate(shape=(count,), dtype=np.uint32)
            send_buffer[:] = np.asarray([_u32(word) for word in activation_words], dtype=np.uint32)

            # Start S2MM first so the accelerator can never block waiting for a
            # receive descriptor while MM2S is already producing a packet.
            self.dma.recvchannel.transfer(receive_buffer)
            self.dma.sendchannel.transfer(send_buffer)
            self.dma.sendchannel.wait()
            self.dma.recvchannel.wait()
            if hasattr(receive_buffer, "invalidate"):
                receive_buffer.invalidate()
            return [int(word) for word in receive_buffer]
        finally:
            self._release_buffer(send_buffer)
            self._release_buffer(receive_buffer)

    def verify(
        self,
        activation_words: Sequence[int],
        weight_word: int,
        bias: int = 0,
        mode_int4: bool = False,
        enable_2to4: bool = False,
    ) -> List[int]:
        """Configure, run, and raise AssertionError on any hardware mismatch."""

        expected, expected_error = golden_packet(
            activation_words,
            weight_word,
            bias=bias,
            mode_int4=mode_int4,
            enable_2to4=enable_2to4,
        )
        self.configure(
            weight_word,
            bias=bias,
            mode_int4=mode_int4,
            enable_2to4=enable_2to4,
            clear_status=True,
        )
        actual = self.run(activation_words)
        if actual != expected:
            raise AssertionError(
                "DMA result mismatch: expected {}, got {}".format(
                    [signed32(word) for word in expected],
                    [signed32(word) for word in actual],
                )
            )
        actual_error = self.mask_error
        if actual_error != expected_error:
            raise AssertionError(
                "mask status mismatch: expected {}, got {}".format(
                    expected_error, actual_error
                )
            )
        return actual


def _board_demo(bitfile: str) -> None:
    accelerator = AxisDotAccelerator.from_bitfile(bitfile)
    activation_words = [
        pack_int8_word([1, 2, 3, 4]),
        pack_int8_word([1, 1, 1, 1]),
    ]
    results = accelerator.verify(
        activation_words,
        pack_int8_word([1, 1, 1, 1]),
        bias=5,
        mode_int4=False,
        enable_2to4=False,
    )
    print("[PASS] Lab04 PYNQ DMA results:", [signed32(word) for word in results])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Lab04 PYNQ DMA smoke test")
    parser.add_argument("bitfile", help="path to a .bit file with a same-basename .hwh")
    args = parser.parse_args()
    _board_demo(args.bitfile)


if __name__ == "__main__":
    main()
