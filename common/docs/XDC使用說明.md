# XDC 使用說明

XDC 不是「每個 `.sv` 都要配一份」；它約束的是目前被選為 synthesis top 的外部 ports 與 clocks。Behavioral Simulation 不需要 XDC。

## 三種情況

### 1. 純 RTL／Testbench

不載入 XDC。先把功能與握手驗證完成。

### 2. 純 PL 板上小 demo

top module 使用 `sysclk`、`sw`、`btn`、`led` 時，可從 `pynq_z2_user_io.xdc` 複製真正用到的行。若 top 只有 `sysclk` 與 `led[0]`，其餘 switch/button/LED 行都必須註解，否則 `get_ports` 會找不到物件。

### 3. Zynq PS + AXI DMA + accelerator

AXI clock 由 `FCLK_CLK0` 產生，DDR/MIO 由 PS 與 board preset 處理。若 HDL wrapper 沒有 PL user-I/O port，就不需要 `sysclk`/LED XDC。只有額外 export 的 debug LED、Pmod 等才加入相應 pin constraint。

## PYNQ-Z2 教學用腳位表

| top port | package pin | I/O standard | 板上元件 |
|---|---|---|---|
| `sysclk` | H16 | LVCMOS33 | 125 MHz clock |
| `sw[0]` | M20 | LVCMOS33 | SW0 |
| `sw[1]` | M19 | LVCMOS33 | SW1 |
| `led[0]` | R14 | LVCMOS33 | LED0 |
| `led[1]` | P14 | LVCMOS33 | LED1 |
| `led[2]` | N16 | LVCMOS33 | LED2 |
| `led[3]` | M14 | LVCMOS33 | LED3 |
| `btn[0]` | D19 | LVCMOS33 | BTN0 |
| `btn[1]` | D20 | LVCMOS33 | BTN1 |
| `btn[2]` | L20 | LVCMOS33 | BTN2 |
| `btn[3]` | L19 | LVCMOS33 | BTN3 |

實作前仍應以手上板卡版本的 Master XDC／原理圖做最後核對。

