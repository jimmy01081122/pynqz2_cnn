#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$LAB_DIR"
mkdir -p build
iverilog -g2012 -Wall -s tb_sparse_array -o build/tb_sparse_array.vvp -c sim/files.f
vvp build/tb_sparse_array.vvp
