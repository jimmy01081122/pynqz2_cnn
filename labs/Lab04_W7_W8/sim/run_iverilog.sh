#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$LAB_DIR"
mkdir -p build
iverilog -g2012 -Wall -s tb_axis_dot_accelerator -o build/tb_axis_dot_accelerator.vvp -c sim/files.f
vvp build/tb_axis_dot_accelerator.vvp
