# Lab02（W3–W4）：Dense INT8／INT4 PE 與 valid/ready

本 Lab 是六天課程的第 2 天。你會從「有號整數乘加」開始，完成一個可在 INT8 與 INT4 間切換的 processing element（PE），並理解硬體串流最重要的 `valid/ready` 握手。即使你從未使用 Vivado，也可以依本文件逐步完成模擬。

> 本 Lab 的寬資料介面是為了看懂與模擬，不直接接 PYNQ-Z2 的按鍵或 LED。先不要產生 bitstream；到 Lab04 才會把運算核心放進 AXI Block Design。這是刻意的分工，不是缺少檔案。

## 1. 今天要完成什麼

完成後你應該能夠：

1. 解釋二補數 INT8（-128～127）與 INT4（-8～7）。
2. 看懂 32-bit word 中的 lane packing。
3. 用 `clear_acc` 開始新的一次累加。
4. 用 `valid && ready` 判斷「這一拍是否真的傳輸」。
5. 在下游 backpressure 時保持 `out_valid/out_acc/out_last` 穩定。
6. 執行 self-checking testbench，看到 `[PASS]` 而不是只看波形猜答案。

## 2. 資料夾

```text
Lab02_W3_W4/
├── rtl/dense_int_pe.sv          # 可合成的 PE
├── tb/tb_dense_int_pe.sv        # 自動比對答案的測試
├── sim/files.f                  # Icarus Verilog 檔案清單
├── sim/run_iverilog.sh          # 命令列模擬腳本
├── constraints/pynq_z2_lab02.xdc
└── vivado/create_project.tcl    # 自動建立 Vivado 專案
```

`build/` 會在執行模擬或 Tcl 後產生，已產生的內容可以刪除後重建。

## 3. 先讀懂 packing 規則

32-bit 的最低位元放 lane 0。這件事非常重要，因為它決定軟體與硬體如何解讀同一個數字。

### 3.1 INT8 模式（`in_mode_int4 = 0`）

```text
bit 31          24 23          16 15           8 7            0
+----------------+---------------+---------------+---------------+
| lane 3 (INT8)  | lane 2 (INT8) | lane 1 (INT8) | lane 0 (INT8) |
+----------------+---------------+---------------+---------------+
```

例如 `32'h0403_0201` 是 `[lane0,lane1,lane2,lane3] = [1,2,3,4]`，不是 `[4,3,2,1]`。若 activation 與 weight 都是此值，dot product 為：

```text
1×1 + 2×2 + 3×3 + 4×4 = 30
```

### 3.2 INT4 模式（`in_mode_int4 = 1`）

每個 hexadecimal digit 正好是一個 4-bit lane：

```text
32'h8765_4321 -> [1,2,3,4,5,6,7,-8]
```

最左邊的 `8` 是二補數 `4'b1000`，代表 -8。`F` 代表 -1。INT4 模式沒有額外 scale 或 zero-point；本 Lab 的語意就是「八組 signed INT4 相乘後，以 32-bit signed accumulator 相加」。量化 scale 會在 Lab03 的 requantization 加入。

## 4. PE 每一拍做什麼

只有在以下條件成立時，輸入才被接受：

```text
accept = in_valid && in_ready
```

若 `in_clear_acc = 1`：

```text
next_acc = dot_product
```

否則：

```text
next_acc = previous_acc + dot_product
```

結果先放進一格 output register。當 `out_valid=1` 且 `out_ready=0`，這格已滿又無法送出，所以 `in_ready=0`，同時輸出資料保持不變。當 `out_ready=1`，舊結果可以在該拍被取走；若此時也有新輸入，暫存器能在同一拍換成新結果，不必插入空拍。

## 5. 最快的模擬方式：Icarus Verilog

先安裝 Icarus Verilog，並確認終端機輸入 `iverilog -V` 有版本資訊。接著在本 Lab 根目錄執行：

```bash
bash sim/run_iverilog.sh
```

正確結果最後一行為：

```text
[PASS] Lab02 dense INT8/INT4 PE and backpressure tests passed.
```

testbench 會自動檢查：

- INT8 dot product 與跨 transaction 累加。
- INT4 signed nibble 的正負號。
- `clear_acc` 是否真的重開累加。
- `out_ready=0` 連續三拍時，`valid/data/last` 是否穩定。
- output register 被占用時 `in_ready` 是否為 0。

若看到 `[ERROR]`，往上找第一個錯誤；第一個通常才是根因。

## 6. 第一次使用 Vivado

### 6.1 建立專案

1. 開啟 **Vivado**，不需要先按 Create Project。
2. 選上方選單 **Tools → Run Tcl Script**。
3. 選擇 `vivado/create_project.tcl`。
4. 等待 Tcl Console 顯示 `Lab02 project created`。

腳本已指定 PYNQ-Z2 的 FPGA part：`xc7z020clg400-1`，也已加入 RTL、testbench 與 XDC。

### 6.2 執行行為模擬

1. 左側 **Flow Navigator** 找到 **Simulation**。
2. 按 **Run Simulation → Run Behavioral Simulation**。
3. 模擬視窗打開後按 **Run All**（三角形加直線的圖示）。
4. 下方 Tcl Console 應出現 `[PASS]`。

想看握手時，將下列訊號加入波形：

```text
in_valid, in_ready, in_mode_int4, in_clear_acc,
out_valid, out_ready, out_acc, out_last
```

在波形名稱上按右鍵可將 `out_acc` 的 radix 改成 **Signed Decimal**。

### 6.3 合成與 XDC 的界線

你可以按 **Run Synthesis** 檢查 RTL 能否合成。`pynq_z2_lab02.xdc` 只約束板上的 125 MHz clock（H16，8 ns period）。其餘寬資料埠刻意沒有綁到實體接腳，因此不要對 `dense_int_pe` 直接 Run Implementation 或 Generate Bitstream。真正上板會在 Lab04 透過 Zynq PS、DMA 與 AXI4-Stream 連接，不需要把 64 個資料腳拉到板外。

## 7. 建議的課堂操作

1. 先手算 testbench 中第一筆 INT8，確認答案 30。
2. 將 `out_ready` 固定為 1，觀察沒有 backpressure 的時序。
3. 恢復原 testbench，觀察停住三拍時輸出不變。
4. 把一個 INT4 nibble 改為 `F`，先手算再改 expected value。
5. 最後才閱讀 `packed_dot` function，對照 lane part-select。

## 8. 常見錯誤

- **把 `valid` 當成脈衝**：valid 可以維持很多拍；只有 `valid && ready` 是一次 transfer。
- **停住時改資料**：送出端在 `valid=1 && ready=0` 時不可更改 data 或 last。
- **把 nibble 8 當 +8**：signed INT4 沒有 +8；`4'b1000` 是 -8。
- **lane 順序反了**：本課程一律 lane 0 在最低位元。
- **忘了 `$signed`**：位元向量預設可能以 unsigned 解讀，使負數乘法錯誤。
- **直接產 bitstream**：本 Lab 還不是板級 top，未約束寬資料埠是預期行為。

## 9. 驗收清單

- [ ] Icarus 或 Vivado behavioral simulation 顯示 `[PASS]`。
- [ ] 能手算 `0x04030201 · 0x04030201 = 30`。
- [ ] 能解釋 `0x87654321` 在 INT4 模式含有 -8。
- [ ] 能指出輸入與輸出各自的 transfer 條件。
- [ ] 能說明為什麼 backpressure 期間輸出必須穩定。

完成後保留 Lab02 的原始碼與模擬截圖，再進入 Lab03 的 2:4 sparse datapath。
