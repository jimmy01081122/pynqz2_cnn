#!/usr/bin/env bash
set -euo pipefail

SIM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$(cd "$SIM_DIR/.." && pwd)"
BUILD_DIR="$LAB_DIR/build/sim"
mkdir -p "$BUILD_DIR"

if ! command -v iverilog >/dev/null 2>&1; then
    echo "ERROR: 找不到 iverilog。請先安裝 Icarus Verilog。" >&2
    exit 2
fi
if ! command -v vvp >/dev/null 2>&1; then
    echo "ERROR: 找不到 vvp。請確認 Icarus Verilog 安裝完整。" >&2
    exit 2
fi

cd "$LAB_DIR"
for config in dense_int8:8:0 dense_int4:4:0 int8_2to4:8:1 int4_2to4:4:1; do
    IFS=: read -r name data_width enable_2to4 <<<"$config"
    output="$BUILD_DIR/${name}.vvp"
    echo "== $name (DATA_WIDTH=$data_width ENABLE_2TO4=$enable_2to4) =="
    iverilog -g2012 -Wall -s tb_ai_accel_top \
        -Ptb_ai_accel_top.DATA_WIDTH="$data_width" \
        -Ptb_ai_accel_top.ENABLE_2TO4="$enable_2to4" \
        -o "$output" -f sim/files.f
    vvp "$output"
done

echo "[PASS] Lab05 all four configurations passed."
