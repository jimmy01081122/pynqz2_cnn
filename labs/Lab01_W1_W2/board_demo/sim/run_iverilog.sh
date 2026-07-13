#!/usr/bin/env bash
set -euo pipefail

SIM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$SIM_DIR/.." && pwd)"
mkdir -p "$DEMO_DIR/build"
cd "$SIM_DIR"
iverilog -g2012 -s tb_pynq_z2_adder_demo -o "$DEMO_DIR/build/tb_adder.vvp" -f files.f
vvp "$DEMO_DIR/build/tb_adder.vvp"
