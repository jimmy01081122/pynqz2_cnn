# Optional：PYNQ-Z2 無時脈加法器上板練習

這個小練習把兩顆開關各當成一個 1-bit operand。`LED[1:0]` 顯示 `SW0 + SW1` 的二進位結果，`LED[3:2]` 固定熄滅。它是純組合邏輯，不需要 clock，因此 XDC **沒有** H16。

| SW1 | SW0 | LED1 | LED0 | 十進位和 |
|:---:|:---:|:----:|:----:|:---:|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 | 1 |
| 1 | 1 | 1 | 0 | 2 |

先模擬：

```bash
bash sim/run_iverilog.sh
```

在 Vivado 建立 RTL Project 時：

1. part 選 `xc7z020clg400-1`。
2. 加入 `rtl/pynq_z2_adder_demo.sv`，top 設為 `pynq_z2_adder_demo`。
3. 加入 `constraints/pynq_z2_adder_demo.xdc`。
4. Run Synthesis → Run Implementation → Generate Bitstream。
5. 上板後依表格撥 SW0/SW1，核對 LED0/LED1。

XDC 使用 `sw[0]=M20`、`sw[1]=M19`，以及 `led[0..3]=R14/P14/N16/M14`。若 top port 名稱被改動，XDC 也必須一起改。
