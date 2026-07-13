# Lab03（W5–W6）：2:4 Sparse Decoder、4×4 教學陣列與 Requantization

本 Lab 是六天課程的第 3 天。你會把 Dense 權重改成 2:4 structured sparsity：每四個權重只保留兩個，再用 mask 還原位置。接著讓四個 PE 同時處理同一組四 lane activation，最後把 32-bit accumulator 重新量化成 signed INT8。

本 Lab 仍以 behavioral simulation 與 synthesis 為主。平行資料埠沒有全部接到 PYNQ-Z2 實體 pin；Lab04 才透過 AXI DMA 上板。

## 1. 學習目標

完成後你應該能：

1. 寫出本課程的 2:4 編碼與解碼規則。
2. 說明 mask 不合法時硬體採取的明確行為。
3. 分辨「lane 數」與「PE 數」。
4. 手算四列 sparse dot product。
5. 解釋 multiplier、right shift、zero-point 與 INT8 saturation。
6. 用 self-checking TB 分別驗證 decoder、requantizer、陣列與 backpressure。

## 2. 檔案結構

```text
Lab03_W5_W6/
├── rtl/sparse_2of4_decoder.sv  # 兩個值 + 4-bit mask -> 四個值
├── rtl/sparse_pe.sv            # decoder + 4-lane dot product
├── rtl/requantize.sv           # accumulator -> signed INT8
├── rtl/sparse_array_4x4.sv     # 預設四個 PE 並行
├── tb/tb_sparse_array.sv       # 完整自動驗證
├── sim/files.f
├── sim/run_iverilog.sh
├── constraints/pynq_z2_lab03.xdc
└── vivado/create_project.tcl
```

## 3. 本課程的 2:4 格式

一個 group 有四個 lane，mask 的 bit 0 對應 lane 0。合法 mask 必須剛好有兩個 1。壓縮資料只有兩個 signed INT8：

```text
sparse_values[7:0]  = value0
sparse_values[15:8] = value1
```

decoder 從 lane 0 往 lane 3 掃描 mask，遇到第一個 1 放 value0，遇到第二個 1 放 value1。

範例：

```text
mask          = 4'b1010
value0        = 3
value1        = -2
dense weights = [0, 3, 0, -2]   # 依 lane0 到 lane3 列出
```

activation 若為 `[1,2,3,4]`，dot product 是 `0×1 + 3×2 + 0×3 + (-2)×4 = -2`。

### 3.1 非法 mask 的安全語意

`0001`、`1110`、`0000` 都不是 2:4。本設計不猜測資料意思，而是：

- `mask_ok = 0`。
- 該 decoder 的四個輸出全部為 0。
- 該 PE 本次 dot product 為 0，因此該列 accumulator 不增加。
- 陣列仍產生 output transaction，並將 `out_mask_error = 1`，其他合法 PE 繼續計算。

這個行為讓錯誤可被軟體看見，同時不把不明資料加進 accumulator。

## 4. 「4×4 陣列」到底是什麼

這裡的預設設定為：

- 4 個 activation lanes，廣播給所有 PE。
- 4 個 PE，每個 PE 代表一列權重，並有自己的 accumulator。
- 每拍共執行 4 個 PE × 4 個 lane = 16 個位置；因 2:4 稀疏，每列只有兩個非零乘法。

`DATA_WIDTH`、`ACC_WIDTH`、`PES` 都是 parameter。`LANES` 明列為 parameter 以顯示介面尺寸，但本模組一次解一個 2:4 group，所以必須保持 4；若要 8 lanes，正確擴充方式是每個 PE 放兩組 decoder，而不是把 2:4 decoder 硬改成 2:8。

### 4.1 testbench 使用的四列

activation 固定為 `[1,2,3,4]`：

| PE | mask | 兩個值 | dense row | dot |
|---:|:----:|:------:|:----------|----:|
| 0 | `0101` | `1, 2` | `[1,0,2,0]` | 7 |
| 1 | `1010` | `-1, 1` | `[0,-1,0,1]` | 2 |
| 2 | `0011` | `2, 3` | `[2,3,0,0]` | 8 |
| 3 | `1100` | `1, -2` | `[0,0,1,-2]` | -5 |

當 `in_clear_acc=1`，初值為 bias 加本次 dot。testbench 的 bias 是 `[10,0,-8,5]`，所以第一筆輸出為 `[17,2,0,0]`。下一筆相同資料但 `clear_acc=0`，結果是 `[24,4,8,-5]`。

## 5. Requantization 數學

本 Lab 使用純整數公式：

```text
scaled = round_away_from_zero(acc × multiplier / 2^shift)
q      = saturate_to_signed_int8(scaled + zero_point)
```

- `multiplier` 是 signed 16-bit。
- `shift` 是 0～63；實務上請選不超過運算寬度的值。
- `zero_point` 是 signed 16-bit。
- 最終輸出限制於 -128～127。

「round away from zero」表示 +10.5 變 +11，-10.5 變 -11。testbench 也測試 +200 飽和成 +127、-200 飽和成 -128。這是教學用定點規則；若要與 TensorFlow Lite、ONNX Runtime 完全 bit-accurate，必須把它們各自的 multiplier 編碼與 rounding 規格逐條對齊。

## 6. 命令列模擬

在本 Lab 根目錄執行：

```bash
bash sim/run_iverilog.sh
```

預期最後看到：

```text
[PASS] Lab03 decoder, sparse array, requant, and backpressure tests passed.
```

這不是只列印 PASS 的展示程式；每個預期值都由 testbench 比對，不符合便累計錯誤並以 non-zero status 結束。

## 7. 第一次用 Vivado 的步驟

1. 開 Vivado。
2. 選 **Tools → Run Tcl Script**。
3. 選 `vivado/create_project.tcl`。
4. Tcl Console 顯示專案建立完成後，在左側按 **Run Simulation → Run Behavioral Simulation**。
5. 按 **Run All**，確認 Console 有 `[PASS]`。

建議加入波形：

```text
in_valid, in_ready, in_sparse_masks, in_clear_acc,
out_valid, out_ready, out_acc, out_q, out_mask_error
```

`out_acc` 與 `out_q` 是 flat packed vectors：最低 32-bit/8-bit 是 PE0，接著是 PE1。要看單一 PE，可在 Objects 或 Scope 中展開 generate block，或在波形使用對應 slice。

## 8. 合成報告怎麼看

按 **Run Synthesis** 後可開 **Open Synthesized Design → Report Utilization**。請比較：

1. `PES=4` 與暫時改成 `PES=2`。
2. `DATA_WIDTH=8` 與較小寬度（同時調整 testbench 才能模擬）。
3. 有無 requant multiplier 對 DSP 使用量的影響。

XDC 只提供 PYNQ-Z2 的 H16 125 MHz clock constraint。寬資料介面尚未做 pin mapping，所以本 Lab 不直接 Generate Bitstream。未約束 I/O 的 DRC 不是靠降低嚴重度掩蓋，而是在 Lab04 正確改成 AXI 內部連線。

## 9. 常見錯誤

- **把 mask bit 3 當 lane 0**：本課程 lane 0 永遠在最低位元。
- **兩個值依 mask 數字大小排序**：不是；是從 lane 0 到 lane 3 依序消耗 value0/value1。
- **假設 sparse value 一定非零**：2:4 的「保留位置」可存數字 0；格式限制的是位置數，不檢查數值。
- **非法 mask 仍使用部分值**：本實作整列歸零並回報 error。
- **直接截成 8-bit**：截斷會 wrap；requantizer 必須先 saturation。
- **忽略負數 rounding**：算術右移會朝負無限方向，不能直接等同對稱四捨五入。
- **只測正常 ready**：backpressure 才最容易暴露資料覆寫問題。

## 10. 驗收清單

- [ ] 能由 `mask=1010, values={3,-2}` 還原 `[0,3,0,-2]`。
- [ ] 能說明非法 mask 的四項行為。
- [ ] 手算 testbench 四個 PE 的 dot。
- [ ] 模擬顯示 `[PASS]`。
- [ ] 能說明 requant 的 multiplier、shift、zero-point、saturation。
- [ ] 知道本 Lab 為何只 synthesis、不直接產 bitstream。

通過後，下一個 Lab 會用 AXI4-Stream 把相同的 packed integer 運算接到 Zynq PS 與 PYNQ Python。
