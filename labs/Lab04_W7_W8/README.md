# Lab04（W7–W8）：AXI4-Stream、Zynq Block Design 與 PYNQ DMA

本 Lab 是六天課程的第 4 天，將 W7～W8 包成一個可獨立完成的單元。你會先在純 RTL 模擬中證明 AXI4-Stream 握手與 backpressure 正確，再用 Vivado IP Integrator 把同一個核心接到 Zynq PS、AXI DMA 與 PYNQ Python。

> 本資料夾不附假造的 bitstream 或硬體測量結果。產生 .bit/.hwh 必須使用你電腦上的 Vivado、正確的 PYNQ-Z2 board files 與實體板卡。沒有板卡時仍可完成 RTL 模擬與閱讀 Block Design。

## 1. 今日目標與建議節奏

完成後，你應能：

1. 解釋資料只在 rising edge 且 TVALID 與 TREADY 同時為 1 時傳輸。
2. 在 TREADY=0 時保持 TVALID、TDATA、TKEEP、TLAST 穩定。
3. 分辨 DMA 的 AXI4-Stream 埠與 memory-mapped AXI master。
4. 讀懂 PS GP0 控制路徑、HP0 DDR 路徑與 reset/clock。
5. 產生可由 PYNQ Overlay 載入的同名 .bit/.hwh。
6. 用 Python driver 執行 DMA，並與純 Python golden model 逐筆比對。

建議一天安排：

| 時段 | 內容 | 驗收 |
|---|---|---|
| 上午前半 | 讀 AXI4-Stream 契約與資料格式 | 能指出一次 transfer 的唯一條件 |
| 上午後半 | 跑 self-checking TB、看 backpressure 波形 | Console 出現 PASS |
| 下午前半 | 建立並檢查 Block Design | Validate Design 無 Critical Warning |
| 下午後半 | 若有板卡，產生 bit/hwh 並跑 Python | 兩筆 smoke test 得到 [15, 19] |

## 2. 檔案結構

~~~text
Lab04_W7_W8/
├── README.md
├── rtl/
│   └── axis_dot_accelerator.sv
├── tb/
│   └── tb_axis_dot_accelerator.sv
├── sim/
│   ├── files.f
│   └── run_iverilog.sh
├── constraints/
│   └── pynq_z2_lab04.xdc
├── vivado/
│   ├── create_project.tcl
│   └── create_bd.tcl
└── python/
    └── axis_accel.py
~~~

**axis_dot_accelerator.sv** 是一個 32-bit AXI4-Stream 核心。它支援 dense/sparse 與 INT8/INT4 四種執行模式，並在每個 input beat 產生目前的 running sum。

**create_bd.tcl** 使用 RTL module reference，不要求學生先手動封裝自訂 IP。等你熟悉流程後，仍可再練習 Tools → Create and Package New IP。

## 3. 介面契約與資料格式

### 3.1 AXI4-Stream 的唯一傳輸條件

~~~text
transfer = TVALID && TREADY
~~~

- Sender 可先拉高 TVALID，並等 Receiver 準備好。
- Receiver 可隨時拉低 TREADY 造成 backpressure。
- TVALID=1、TREADY=0 時，TDATA、TKEEP、TLAST 不可改變。
- TLAST 是封包最後一拍的 payload，不是額外脈衝。
- DMA 的 MM2S 在送出 buffer 最後一個 word 時產生 TLAST；S2MM 依 TLAST 結束接收封包。

本核心有一格 elastic output register。因此 output 被 stall 時，input 的 TREADY 會下降，避免舊結果被新結果覆寫。

### 3.2 四種模式

| cfg_mode_int4 | cfg_enable_2to4 | activation word | cfg_weight_tdata |
|---:|---:|---|---|
| 0 | 0 | 4 個 signed INT8 | 4 個 signed INT8 |
| 1 | 0 | 8 個 signed INT4 | 8 個 signed INT4 |
| 0 | 1 | 4 個 signed INT8 | 2 個 INT8 值 + 4-bit mask |
| 1 | 1 | 8 個 signed INT4 | 兩組「2 個 INT4 值 + 4-bit mask」 |

所有 lane 都採 little-lane packing：lane 0 在最低位元。

Sparse INT8 weight word：

~~~text
bits  7:0   value0
bits 15:8   value1
bits 19:16  mask
~~~

Sparse INT4 weight word：

~~~text
bits  3:0   group0 value0
bits  7:4   group0 value1
bits 11:8   group1 value0
bits 15:12  group1 value1
bits 19:16  group0 mask
bits 23:20  group1 mask
~~~

每個 mask 必須剛好有兩個 1。核心由 lane 0 往 lane 3 掃描，依序消耗 value0、value1。若 mask 不合法，本 beat 的 dot product 為 0，status_mask_error 會黏住，直到軟體 pulse cfg_clear_status。

### 3.3 accumulator 與 TLAST

一個 packet 的第一拍計算：

~~~text
result = signed(cfg_bias) + dot(first activation, weight)
~~~

後續每拍累加：

~~~text
result = previous result + dot(next activation, weight)
~~~

每拍都會送出 running result。收到 input TLAST 後，下一個 packet 又由 bias 開始。軟體不得在同一 packet 傳輸途中改 mode、weight 或 bias。

### 3.4 AXI GPIO 對照

Block Design 使用兩個 AXI GPIO：

| instance | channel | 方向 | 意義 |
|---|---:|---|---|
| axi_gpio_control | 1 | PS → PL | bit0 INT4、bit1 2:4、bit2 clear-status pulse |
| axi_gpio_control | 2 | PL → PS | bit0 sticky mask error |
| axi_gpio_params | 1 | PS → PL | 32-bit packed weight |
| axi_gpio_params | 2 | PS → PL | signed 32-bit bias |

Python driver 已包裝這些細節；初學時不要直接猜 register offset。

## 4. 先完成純 RTL 模擬

### 4.1 使用 Icarus Verilog

在 Lab04_W7_W8 根目錄執行：

~~~bash
bash sim/run_iverilog.sh
~~~

預期最後一行：

~~~text
[PASS] Lab04 dense/sparse INT8/INT4, invalid-mask, TLAST, and backpressure tests passed.
~~~

TB 會自動比對：

- Dense INT8 兩拍累加與 bias。
- Dense INT4 signed nibble。
- Sparse INT8 與 Sparse INT4。
- 非法 2:4 mask 的 zero-dot 與 sticky status。
- TKEEP/TLAST 傳遞。
- output stall 時 TVALID 與 payload 穩定。
- clear-status pulse。

若沒有 PASS，不要先進 Block Design。第一個值得看的波形是：

~~~text
s_axis_tvalid, s_axis_tready, s_axis_tdata, s_axis_tlast,
m_axis_tvalid, m_axis_tready, m_axis_tdata, m_axis_tlast
~~~

### 4.2 使用 Vivado Behavioral Simulation

1. 開啟 Vivado。
2. 選 Tools → Run Tcl Script。
3. 選本 Lab 的 vivado/create_project.tcl。
4. 專案建立後，左側選 Run Simulation → Run Behavioral Simulation。
5. 按 Run All，確認 Tcl Console 出現同一個 PASS。

第一次執行 Tcl 後產生的 build/ 是工具輸出，不是要手改的原始碼。

## 5. 從零檢查 Block Design

create_project.tcl 會呼叫 create_bd.tcl，建立 **lab04_bd** 與 **lab04_bd_wrapper**。在 Flow Navigator 選 IP Integrator → Open Block Design。

資料路徑如下：

~~~text
DDR
 ↑↓
Zynq PS S_AXI_HP0
 ↑↓
axi_smc_memory
 ↑  M_AXI_MM2S       ↑  M_AXI_S2MM
AXI DMA ─M_AXIS_MM2S→ accelerator ─M_AXIS→ S_AXIS_S2MM
~~~

控制路徑：

~~~text
ARM / PYNQ
   │ PS M_AXI_GP0
axi_smc_control
   ├── AXI DMA S_AXI_LITE
   ├── axi_gpio_control
   └── axi_gpio_params
~~~

最容易混淆的是一個字母：

- **M_AXIS_MM2S** 是 stream，只接 accelerator 的 S_AXIS。
- **M_AXI_MM2S** 是 DDR read master，接 memory SmartConnect。
- **M_AXI_S2MM** 是 DDR write master，也接 memory SmartConnect。
- accelerator 的 M_AXIS 只接 DMA 的 S_AXIS_S2MM。

create_bd.tcl 已明確使用 DMA 的 M_AXI_MM2S 與 M_AXI_S2MM 接 HP0；不要把 M_AXIS_MM2S 再接一次 SmartConnect。

腳本固定使用 100 MHz FCLK_CLK0，並讓 Processor System Reset 產生 active-low reset。Address Editor 應看到：

| IP | PS address |
|---|---:|
| axis_dma_0 | 0x4040_0000 |
| axi_gpio_control | 0x4120_0000 |
| axi_gpio_params | 0x4121_0000 |

### 5.1 Board preset 是硬體安全條件

Tcl Console 應顯示使用 PYNQ-Z2 board part。若只看到「board files were not found」警告：

1. 可先做 RTL simulation。
2. 不要用 generic PS/DDR 設定產生要下載到板上的 bitstream。
3. 安裝正確 PYNQ-Z2 board files、重啟 Vivado，再重跑 create_project.tcl。
4. 以 Block Design 的 Processing System 設定頁確認 DDR/MIO 來自 board preset。

不要用「忽略 DRC」代替正確 board preset。

## 6. XDC 為何幾乎是空的

這個設計的 AXI clock 由 PS FCLK_CLK0 產生，DDR 與 FIXED_IO 由 Zynq PS board preset 處理。HDL wrapper 沒有額外 PL LED、switch 或 Pmod port，所以不需要 PACKAGE_PIN。

因此 constraints/pynq_z2_lab04.xdc 只有說明文字是刻意的：

- 不要把 FCLK_CLK0 再綁到 PYNQ-Z2 的 H16。
- 不要替內部 AXI signal 猜 pin。
- 只有未來 export 額外 user I/O 時，才從官方 Master XDC 複製實際使用的 pin。

## 7. 產生 .bit/.hwh 並在 PYNQ 執行

### 7.1 Vivado

在產生硬體前逐項確認：

1. BOARD_PART 是 PYNQ-Z2。
2. Validate Design 無 Critical Warning。
3. Synthesis top 是 lab04_bd_wrapper，不是單獨的 axis_dot_accelerator。
4. Run Synthesis → Run Implementation。
5. 打開 Timing Summary，確認 100 MHz constraint 下 WNS 不為負。
6. Generate Bitstream。

Vivado 產生的 wrapper bitstream 與 Block Design hwh 位置會因版本略有不同。可在專案目錄搜尋 *.bit 與 *.hwh。複製時改成相同 basename，例如：

~~~text
lab04.bit
lab04.hwh
axis_accel.py
~~~

不要將舊 .hwh 與新 .bit 混用，也不要把 .xsa 傳給 PYNQ Overlay。

### 7.2 板上最小 smoke test

把上面三個檔案放在 PYNQ 同一資料夾，在 Terminal 執行：

~~~bash
python3 axis_accel.py lab04.bit
~~~

預期：

~~~text
[PASS] Lab04 PYNQ DMA results: [15, 19]
~~~

這兩拍使用 bias=5、weight=[1,1,1,1]：

- activation [1,2,3,4]：5 + 10 = 15。
- activation [1,1,1,1]：15 + 4 = 19，且第二拍帶 TLAST。

Notebook 也可直接使用：

~~~python
from axis_accel import AxisDotAccelerator, pack_int8_word, signed32

accel = AxisDotAccelerator.from_bitfile("lab04.bit")
inputs = [
    pack_int8_word([1, 2, 3, 4]),
    pack_int8_word([1, 1, 1, 1]),
]
outputs = accel.verify(
    inputs,
    weight_word=pack_int8_word([1, 1, 1, 1]),
    bias=5,
    mode_int4=False,
    enable_2to4=False,
)
print([signed32(word) for word in outputs])
~~~

axis_accel.py 的 packing helper 與 golden_packet 不依賴 PYNQ；只有真正載入 Overlay 或配置 DMA buffer 時才 import PYNQ/NumPy。

## 8. 常見錯誤與排除順序

### DMA wait 卡住

1. 確認 driver 先啟動 recvchannel，再啟動 sendchannel。
2. 確認 DMA 同時啟用 MM2S 與 S2MM，且 Scatter Gather 關閉。
3. 確認 accelerator 的 output TLAST 連到 S_AXIS_S2MM。
4. 確認 input/output buffer 都是 uint32，長度相同且不為 0。
5. 確認 FCLK、所有 AXI clock 與 active-low reset 已接好。
6. 確認 .bit 與 .hwh 同 basename、來自同一次 build。

### 結果數字看似很大

DMA buffer 是 unsigned 32-bit。FFFF_FFFC 代表 signed -4；使用 signed32() 顯示。不要用浮點數解讀 packed word。

### Sparse 結果為 bias 且 status=1

mask 不是合法 2:4。Python 的 pack_sparse_int8_weight 與 pack_sparse_int4_weight 會先拒絕非法 mask；若刻意測錯誤狀況，可直接提供 raw 32-bit weight word。

### Validate Design 指向 interface/clock

從第一個 Critical Warning 開始處理，依序核對 interface 類型、clock association、reset polarity、Address Editor。Run Connection Automation 後也必須人工追一遍完整路徑。

## 9. 驗收清單

- [ ] Icarus 或 Vivado self-checking TB 顯示 PASS。
- [ ] 能說明 stall 時哪四個 M_AXIS signal 必須保持穩定。
- [ ] 能分辨 M_AXIS_MM2S 與 M_AXI_MM2S。
- [ ] Block Design 中 M_AXI_MM2S、M_AXI_S2MM 都經 axi_smc_memory 接 PS S_AXI_HP0。
- [ ] control/parameter GPIO instance name與 Python driver 一致。
- [ ] Board preset、clock、reset、address map 均已人工檢查。
- [ ] 若有板卡，Python smoke test 得到 [15, 19]。
- [ ] 保留 simulation log、Validate Design、Timing Summary 與板上 compare 結果作為證據。

完成後，Lab05 會用四組固定配置收集 PPA；只有 Vivado 真正產生且可回溯到原始 report 的數字才可寫入報告。
