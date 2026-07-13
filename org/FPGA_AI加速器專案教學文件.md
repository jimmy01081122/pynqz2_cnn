# PYNQ-Z2 可配置精度／2:4 稀疏 CNN 加速器
## 六日專案教學文件（零 Vivado 經驗適用）

適用對象：會 Python/PyTorch、修過數位邏輯，但沒有實際使用 Vivado 經驗的學生  
硬體：PYNQ-Z2（Zynq-7020，`xc7z020clg400-1`）  
建議工具：Vivado 2025.2、PYNQ 3.x、Python 3  
時程：6 天密集實作；每天一個 Lab，每個 Lab 對應原 W1～W12 中的兩週

---

## 0. 先看懂終點與範圍

### 0.1 最後會做出什麼

你會完成一個小型、可驗證的 CNN 運算核心。它不是把完整 PyTorch CNN 原封不動塞進 FPGA，而是把最有代表性的點積／MAC 工作交給 PL：

```text
PyTorch / NumPy
  量化、2:4 剪枝、整理向量、golden result
                 │
                 ▼
PYNQ Python ── DDR buffer ── AXI DMA
                                  │ AXI4-Stream
                                  ▼
                      INT4/INT8 + 2:4 PE Array
                                  │
                                  ▼
                       AXI DMA ── DDR ── Python 比對
```

核心具備三個教學特性：

- INT8 與 INT4 的執行模式；
- 2:4 結構化稀疏資料路徑；
- AXI4-Stream valid/ready backpressure。

最後的成果不是一個單獨波形截圖，而是一條證據鏈：Python 輸入與 golden result、RTL Testbench PASS、Block Design、bitstream/hwh、板上輸出、Vivado PPA 報告、四組公平比較圖。

### 0.2 六天內刻意不做的事

為了讓初學者能真正驗證每一層，本教材不把以下工作硬塞進六天：完整卷積 line buffer、任意大小 tensor tiling、完整模型 compiler、所有 CNN layer 的硬體排程，以及宣稱達到論文級準確率。這些都可以在課程完成後延伸，但不應犧牲基本握手與數值正確性。

### 0.3 你需要建立的五步心智模型

1. **寫 RTL**：描述硬體在每個 clock edge 做什麼。
2. **模擬驗證**：Testbench 送資料並自動比對，不靠肉眼猜波形。
3. **合成／實作**：Vivado 將 RTL 轉成 FPGA 資源，檢查 timing 與資源。
4. **包裝與整合**：把核心接上 AXI DMA 與 Zynq PS。
5. **上板與量測**：Python 搬資料、比較結果、收集效能與 PPA。

如果第 2 步沒有通過，不要跳到第 4 步；上板只會讓錯誤來源變多。

---

## 1. 從零認識 Vivado 與 PYNQ-Z2

### 1.1 PS 與 PL 是什麼

PYNQ-Z2 上的 Zynq 同時含有：

- **PS（Processing System）**：ARM 處理器、DDR controller、Ethernet、SD 等；Linux/Python 跑在這裡。
- **PL（Programmable Logic）**：你用 RTL 做出的平行硬體；PE array 跑在這裡。

PS 適合控制、檔案、網路與彈性工作；PL 適合固定、重複、大量平行運算。AXI 是兩者的共同語言。

### 1.2 安裝 Vivado 時只確認三件事

1. 安裝 Zynq-7000 device support。
2. New Project 的 Parts 頁搜尋得到 `xc7z020clg400-1`。
3. 若要使用 PYNQ-Z2 的 Board Preset，Boards 頁搜尋得到 PYNQ-Z2；找不到就安裝 board files 並重啟 Vivado。

不要把專案放在中文、空格很多或過深的路徑。建議例如：

```text
C:\fpga_course\lab02
```

### 1.3 PYNQ-Z2 第一次開機

1. 將 PYNQ image 寫入 microSD。
2. Boot jumper 設為 SD。
3. 使用 USB 供電時把 Power jumper 設為 USB。
4. 插入 microSD、接網路與電源。
5. 直連電腦時通常瀏覽 `http://192.168.2.99`；接路由器時使用 DHCP 分配的 IP。
6. 在 Jupyter 開 Terminal 或 Notebook，測試：

```python
from pynq import Overlay, allocate
print("PYNQ import OK")
```

### 1.4 Vivado 左側 Flow Navigator 只先學這些

| 功能 | 何時用 | 初學者判斷 |
|---|---|---|
| Add Sources | 加 RTL、TB、XDC | TB 一定放 Simulation Sources |
| Run Behavioral Simulation | 功能驗證 | 最先跑；失敗先修這裡 |
| Run Synthesis | RTL 轉網表 | 可初看 LUT/FF/DSP |
| Run Implementation | Place & Route | 看最終 timing/utilization |
| Generate Bitstream | 產生 PL 設定檔 | 模擬與 timing 通過後才跑 |
| IP Integrator | PS/DMA/自訂 IP 串接 | Lab04 才開始 |

### 1.5 Design Source、Simulation Source、Constraint 的差別

- `rtl/*.sv`：可合成硬體，加入 Design Sources。
- `tb/*.sv`：測試環境，加入 Simulation Sources，設定為 simulation top。
- `*.xdc`：腳位與時脈限制，加入 Constraints；behavioral simulation 不需要它。
- `*.tcl`：讓 Vivado 重做相同步驟的腳本，方便重現。

把 TB 放進 Design Sources 可能導致 `$finish`、delay 或不可合成語法錯誤。XDC port 名稱若與 top module 不一致，會出現 `get_ports` 找不到物件。

---

## 2. 六天安排與每天的停止條件

這不是「六天一直按 Next」。每一天都有停止條件；未達成時先不要進下一日。

| Day | Lab | 上午 | 下午 | 當日停止條件 |
|---|---|---|---|---|
| 1 | W1～W2 | 環境、Vivado source 類型、第一個波形 | 四組暖身、量化/剪枝 smoke test | 四組 solution TB PASS；能產生一份量化/稀疏測試資料 |
| 2 | W3～W4 | Dense INT8 PE | 加入 INT4/INT8 mode 與 backpressure | 自動比對 normal/negative/stall/reset case 全通 |
| 3 | W5～W6 | 2:4 decoder | PE array、requant、非法 mask | Dense/sparse 與 golden model 一致 |
| 4 | W7～W8 | AXI wrapper、IP packaging | Zynq PS + DMA Block Design、PYNQ driver | AXI TB 通過；若有板卡，16 筆小資料 round-trip 正確 |
| 5 | W9～W10 | 四組 build config | 報告收集與公平比較 | 每個 CSV 數字均可回指報告，不留手填猜測值 |
| 6 | W11～W12 | 圖表與分析 | README、報告、repo 清理 | 一鍵重做圖表；完整性檢查通過 |

### 2.1 每日建議紀錄

在自己的 lab notebook 記下：

```text
日期／工具版本：
今天使用的 git commit 或壓縮檔版本：
輸入測試向量：
預期值：
實際值：
PASS/FAIL：
若 FAIL，第一個不一致 cycle：
留下的報告與截圖路徑：
```

這個習慣會讓 W11～W12 的報告整理變得非常快。

---

## 3. Day 1／Lab01：只做四組暖身與演算法資料準備

本課程的暖身只保留原 3.2 的四組，不另加第五題。每組都有 `starter/` 與 `solution/`：先做 starter 的 TODO，通過自己的測試後才看 solution。

### 3.1 題目一：參數化加法器與 overflow

學習目標：parameter、組合邏輯、位元寬、有號 overflow。

有號二補數相加的 overflow 不是 carry-out。兩個同號輸入相加，結果卻變成相反符號，才是 signed overflow：

```text
positive + positive -> negative  : overflow
negative + negative -> positive  : overflow
different signs                 : no signed overflow
```

完成 starter 中的 TODO 後，至少測：最大正數加 1、最小負數加 -1、正負相消、一般正數與一般負數。

### 3.2 題目二：valid/ready MAC

學習目標：clocked logic、累加器、資料接受條件、backpressure。

只在 `valid_in && ready_in` 為 1 的 rising edge 接受輸入。若 downstream 還未取走輸出，模組不能偷偷覆寫結果。先在紙上畫出：

```text
accept = valid_in && ready_in
send   = valid_out && ready_out
```

TB 必須刻意將 `ready_out` 拉低數個 cycle，確認結果與 valid 保持穩定。

### 3.3 題目三：同步 FIFO

學習目標：陣列記憶體、read/write pointer、count、full/empty、同時 push/pop。

四種操作要分開想：不動、只 push、只 pop、同時 push+pop。不要只靠 pointer 相等判斷 full/empty；初學版用 count 最清楚。

TB 應包含：空 FIFO pop、填滿、滿 FIFO push、資料順序、同時 push/pop、reset 後 empty。

### 3.4 題目四：Testbench 技法

學習目標：產生 clock/reset、task、自動比對、`$display`、`$monitor`、timeout。

「波形看起來差不多」不是驗證。Testbench 應維護 error counter，遇到不一致顯示時間、預期與實際，最後只有兩種結論：

```text
PASS: errors=0
FAIL: errors=N
```

加入 timeout，避免 DUT 死鎖時模擬永不結束。`$monitor` 適合學習變化，但大型 TB 不要印每個訊號的每次跳動。

### 3.5 演算法端只先建立資料契約

Lab01 的 Python 重點不是追求最高 CIFAR-10 準確率，而是固定硬體會收到的資料格式：

1. FP32 權重先做對稱量化。
2. INT8 clip 到 `[-128, 127]`；INT4 clip 到 `[-8, 7]`。
3. 每連續四個權重做 2:4 pruning，只保留絕對值最大的兩個。
4. 匯出 hex／NumPy 測試向量與 metadata。
5. 用純 Python 算 golden result。

先跑 synthetic smoke mode，不依賴下載 CIFAR-10，也能驗證量化、mask 與匯出格式。真正訓練可在之後長時間執行。

### 3.6 Day 1 XDC 怎麼用

四組暖身首先只做 Behavioral Simulation，所以不需要 XDC。若要把一個練習接到 PYNQ-Z2 的 LED／switch，再使用 Lab01 提供的教學 XDC 與 board top；不要直接把內部 MAC 的寬資料 port 全接到實體腳位。

---

## 4. Day 2／Lab02：Dense PE 與 INT4/INT8 切換

### 4.1 先固定數值契約

在寫乘法器前先回答：輸入是否 signed、accumulator 幾位、reset 是同步或非同步、何時清 accumulator、output valid 何時產生、stall 時哪些訊號必須保持。

若這些規則只存在腦中，Python、RTL 與 TB 很容易各自實作不同版本。Lab02 README 與 port 註解是本專案的介面契約。

### 4.2 Dense INT8 PE

最小 PE 做這件事：

```text
acc_next = acc + signed(activation) * signed(weight)
```

逐步驗證：

1. `1*1` 重複數次。
2. 正乘負、負乘負。
3. reset 後 accumulator 歸零。
4. input valid 為 0 時 accumulator 不動。
5. output stall 時 payload 不動。

### 4.3 INT4 模式

INT4 仍是二補數 signed。packed byte 的高／低 nibble 順序必須由 README、Python packer、RTL 與 TB 一致定義。解包後要 sign-extend，不能只在前面補 0：

```text
4'b1111 -> -1 -> sign extend -> 8'b1111_1111
```

INT4 模式是否每 cycle 做一個或兩個乘法，會影響 throughput 與硬體結構。教材採用的語意以 Lab02 為準；做 PPA 比較時一定要把「每 cycle 有效操作數」算入，不能只比較 clock。

### 4.4 valid/ready 最重要的 assertion

當輸出端 `valid=1` 且 `ready=0`：

- `valid` 不能自行掉下去；
- data 不能變；
- last 不能變；
- 上游若因此無空間，input ready 應反映 backpressure。

Lab02 TB 會故意產生隨機或固定 stall；若只測 `ready=1`，不算完成。

### 4.5 在 Vivado 內跑 Lab02

1. Create Project → RTL Project → part 選 `xc7z020clg400-1`。
2. Add Sources：把 `rtl/` 加入 Design Sources。
3. Add Sources → Add or create simulation sources：把 `tb/` 加入。
4. Simulation Settings 確認 simulation top 是 TB，不是 DUT。
5. Run Behavioral Simulation。
6. Console 必須出現 PASS；再查看 acc、valid/ready 與 mode 波形。
7. 模擬通過後才加入 `constraints/`、設定硬體 top、Run Synthesis。

XDC 只約束硬體 top 的 clock 與少量 debug I/O；純 DUT simulation 不使用它。

---

## 5. Day 3／Lab03：2:4 稀疏、陣列與 requantization

### 5.1 2:4 的資料格式

每組四個原始權重只能保留兩個非零。至少需要：兩個非零值，以及它們對應的 index 或一個 4-bit mask。

例如：

```text
original weights = [ 0, -3, 0, 5 ]
mask             = 4'b1010   # bit 1 與 bit 3 有效（以 Lab03 規則為準）
nonzero values   = [ -3, 5 ]
```

Mask bit ordering 是最常見的軟硬體不一致來源。不要只寫「1010」，一定畫出 mask bit 對到哪個 lane。

### 5.2 先做 decoder，再接 PE

單獨測 decoder：六種合法的 4 選 2 組合都要測。若 mask 不是恰好兩個 bit 為 1，DUT 應回報 error/invalid 或採已文件化行為，不能默默算出不可預期值。

接上 PE 後，用 dense golden model 計算同一組輸入；只要被 prune 的位置是 0，sparse 與 dense 結果應相同。

### 5.3 陣列不是把模組複製就結束

參數化陣列要確認：

- 每個 lane 的 slice 是否正確；
- signed cast 是否在 slice 後仍保留；
- valid/ready 是否全陣列一致；
- accumulator clear 是否同一個 transaction 邊界；
- output 的 lane ordering 是否與 Python 相同。

先測全 1，再測單一 lane 非零，再測正負交錯，最後才測隨機向量。

### 5.4 Requantization

累加結果通常比輸入寬。送回 INT8/INT4 前需要縮放與飽和：

```text
wide accumulator
    -> optional bias
    -> arithmetic right shift
    -> rounding policy
    -> saturation to target range
```

特別測最大正值、最小負值、接近 round boundary 的正負數。SystemVerilog 的 `>>>` 必須作用在 signed 值；若 operand 被當成 unsigned，負數會錯。

### 5.5 何謂「稀疏有加速」

把乘法器的一個輸入設為 0，功能上會得到正確稀疏結果，但不必然省 DSP，也不必然增加 throughput。真正的效益可能來自：

- 只傳兩個非零權重，降低資料量；
- 用 selection network 讓相同硬體處理更多有效工作；
- clock/power gating 降低切換；
- 重新排程以減少 cycle。

因此 Lab05 要同時報告功能、cycle、資源與功耗，不能把「零值跳過」直接等同「兩倍快」。

---

## 6. Day 4／Lab04：AXI4-Stream、IP Integrator 與 PYNQ

### 6.1 先把 AXI4-Stream 當作一條嚴格契約

一筆資料只在 rising edge 且 `TVALID && TREADY` 時傳輸。`TLAST` 是 payload 的一部分，stall 時也要穩定。

```text
transfer = TVALID && TREADY
```

不要在 `TVALID=1` 後假設下一 cycle 一定被收走。DMA 可能拉低 `TREADY`。

### 6.2 AXI wrapper Testbench 先通過

在沒有 PS、DMA、板子之前，TB 要涵蓋：

1. 連續無 stall packet。
2. input 中間空泡。
3. output backpressure。
4. stall 期間 TDATA/TLAST 穩定。
5. reset 插入 transaction 前後。
6. packet 最後一拍的 result 與 TLAST 對齊。

若這裡失敗，先修 wrapper；不要進 Block Design。

### 6.3 本教材採 Module Reference

本專案的可重建腳本採 **Module Reference**：讓 Vivado 直接把已通過 TB 的
`axis_dot_accelerator.sv` 加入 Block Design。這條路不需要建立 IP repository，
也不需要 Package IP，對第一次接觸 Vivado 的學生較容易追查 RTL 與介面。

在 Sources 對 module 按右鍵 **Add Module to Block Design**。Vivado 會依 RTL
attribute 辨識 `S_AXIS` 與 `M_AXIS`；若沒有辨識，先檢查 port 名稱、方向、
clock association 與 reset polarity。Lab04 的 `create_bd.tcl` 會以
`create_bd_cell -type module -reference` 重做相同流程。

> 延伸選項：完成本 Lab 後若想練習封裝 IP，可使用 Tools → Create and Package
> New IP；但封裝版與 Module Reference 版應分開建立，不要在同一個 Block
> Design 同時加入兩份相同核心。

### 6.4 建立 Block Design

1. 建立以 PYNQ-Z2 board 或 `xc7z020clg400-1` 為目標的新 project。
2. 將 Lab04 RTL 加入 Design Sources。
3. Create Block Design，並以 Add Module 加入 accelerator。
4. 加入 `ZYNQ7 Processing System`，Run Block Automation 套用 board preset。
5. 加入 `AXI DMA`，啟用 MM2S 與 S2MM，初學版先關閉 Scatter Gather。
6. 加入自訂 accelerator IP。
7. `M_AXIS_MM2S` → accelerator `S_AXIS`。
8. accelerator `M_AXIS` → `S_AXIS_S2MM`。
9. DMA 的 memory-mapped master 經 interconnect 連到 PS `S_AXI_HP0`。
10. DMA control `S_AXI_LITE` 連到 PS 的 GP master。
11. `FCLK_CLK0` 設 100 MHz，接 AXI clocks；用 Processor System Reset 產生 active-low reset。
12. Run Connection Automation 後仍要人工檢查 clock、reset 與 Address Editor。
13. Validate Design。

### 6.5 XDC 在 PS-PL 設計中的角色

AXI accelerator 的 clock 來自 PS FCLK，不要同時把它綁到 H16。Zynq PS 的 DDR/MIO 由 board preset／PS 設定處理。只有 accelerator 額外拉到 PL 外部的 LED、switch、Pmod 等 port 才需要對應 XDC。

### 6.6 Generate Bitstream 與交付給 PYNQ

1. Create HDL Wrapper，讓 Vivado 管理 wrapper。
2. Run Synthesis → Run Implementation。
3. 查看 Timing Summary，WNS 必須符合課程門檻；負值不能只截圖後忽略。
4. Generate Bitstream。
5. 找到 `.bit` 與 `.hwh`，改成相同 basename，例如：

```text
cnn_accel.bit
cnn_accel.hwh
```

6. 將它們與 driver 放到板子同一個資料夾。

不要把 `.xsa` 直接傳給 `Overlay()`；PYNQ runtime 主要需要 bitstream 與 metadata。

### 6.7 Python DMA 最小驗證順序

1. 先建立 receive buffer。
2. 啟動 receive transfer。
3. 啟動 send transfer。
4. 等待 send 與 receive 完成。
5. 與 NumPy golden result 比對。
6. 釋放 contiguous buffers。

先測 16 筆或一個最小 packet。若 DMA `wait()` 卡住，優先檢查 TLAST 是否送出、DMA transaction length、clock/reset、以及 S2MM channel 是否已啟用。

---

## 7. Day 5／Lab05：四組實驗與 PPA

### 7.1 四組固定實驗

| config | 精度 | 稀疏 | 目的 |
|---|---|---|---|
| dense_int8 | INT8 | 無 | baseline |
| dense_int4 | INT4 | 無 | 精度消融 |
| int8_2to4 | INT8 | 2:4 | 稀疏消融 |
| int4_2to4 | INT4 | 2:4 | 完整組合 |

### 7.2 公平比較規則

四組必須固定：Vivado version、part、clock constraint、array 規模、implementation strategy、輸入 workload、計數起訖、power estimation 方法。若某組每 cycle 處理更多 operation，throughput 公式要反映真正的有效 MAC 數。

Lab05 的 `ai_accel_top` 是寬平行的 block-level PPA top，不是板級 I/O top。批次腳本使用 `synth_design -mode out_of_context`，避免工具替數百個教學 port 插入 I/O buffer；四組仍會走相同的 opt/place/route。OOC 報告適合比較核心邏輯，但不可寫成完整 PYNQ-Z2 bitstream 或整板實測。

### 7.3 報告來源

| 欄位 | Vivado 來源 | 判讀 |
|---|---|---|
| LUT/FF/DSP/BRAM | Report Utilization | 使用量與可用量都保存 |
| WNS/TNS | Report Timing Summary | WNS < 0 表示目標 clock 未 closure |
| Power | Report Power | 記錄 vectorless 或 SAIF-based |
| cycles | RTL counter／ILA／Python timestamp | 說明是否含 DMA |
| throughput | 由相同 operation 定義計算 | 不只報 clock MHz |
| accuracy | PyTorch evaluation | 與相同 test set 比較 |

### 7.4 不可捏造的欄位

模板中的空值就是「尚未量到」，不要填 0。0 LUT 與「沒有資料」是不同意思。Lab05 腳本只解析實際報告或產生待填模板，絕不生成看似合理的假數字。

### 7.5 Timing closure 基本順序

1. 先看 critical path 起點、終點與邏輯層數。
2. 檢查是否有寬乘加後直接接大 MUX／飽和邏輯。
3. 加 pipeline register，重新定義 latency 並更新 TB。
4. 確認 clock constraint 真正套用在正確 clock。
5. 才考慮 implementation directive；不要用 directive 掩蓋架構問題。

### 7.6 功耗聲明

沒有實際 switching activity 時，Vivado power 通常是估算。報告需標記 `vectorless`；若匯入 SAIF，記錄 simulation workload、時間範圍與 clock。PYNQ-Z2 若沒有直接可用的整板精密量測通道，板級功耗需額外儀器，不能把工具估算值說成實測瓦數。

---

## 8. Day 6／Lab06：Trade-off、報告與可重現性

### 8.1 一張圖只回答一個問題

建議至少產生：

- 四組 LUT/DSP 長條圖：硬體成本。
- 四組 throughput 長條圖：效能。
- accuracy vs throughput 散點圖：精度／效能權衡。
- power 或 energy per inference 圖：僅在測量方法一致時使用。

不要用雷達圖取代原始表格；它容易受尺度影響。圖中標示 timing failed 的配置，不能把未 closure 的 clock 當可用效能。

### 8.2 結論要分成觀察與解釋

```text
觀察：int8_2to4 相較 dense_int8，〈填入可追溯的 LUT／DSP／cycle 差異〉。
解釋：〈依 RTL 架構與原始報告解釋原因；不要先假定稀疏一定較快〉。
限制：〈例如 power 為 vectorless estimate，尚未使用 SAIF〉。
```

這比「稀疏比較好」更有可信度。

### 8.3 Repo 最低交付內容

- 所有 RTL 與 TB。
- 所有 XDC/Tcl，且不只留 `.xpr`。
- Python golden model、PYNQ driver、量化／剪枝與畫圖腳本。
- 原始／解析後 PPA 資料與欄位說明。
- 六個 Lab README 與本主教材。
- 確切工具版本、part、時脈與資料格式。
- 若附 `.bit/.hwh`，兩者同 basename 且標明產生版本；不附也要說明重建方法。

---

## 9. 驗收、除錯與延伸

### 9.1 分層驗收順序

```text
Python quantization/mask unit test
        ↓
single module TB
        ↓
PE / array TB
        ↓
AXI wrapper protocol TB
        ↓
Vivado synthesis + timing
        ↓
DMA 16-word board test
        ↓
full workload + PPA
```

任何一層失敗，都回到最接近且可觀察性最高的上一層。不要在板上用 print 猜一個其實能在 1 秒 RTL simulation 重現的 bug。

### 9.2 常見症狀快速索引

| 症狀 | 第一個檢查點 |
|---|---|
| Simulation 沒有波形 | simulation top、是否 run 足夠時間、TB clock |
| 全部是 X | reset 是否真的經過 rising edge、未初始化訊號、多重 driver |
| 正數對、負數錯 | signed 宣告、slice 後 cast、INT4 sign extension、`>>>` |
| 偶爾少一筆 | valid/ready 是否同 edge 才計 transfer |
| stall 時結果變 | output register 未保持、內部 state 仍前進 |
| DMA 永遠 wait | TLAST、S2MM 是否先啟動、clock/reset、length |
| XDC get_ports error | top port 名與 XDC 名不一致，或用錯 top |
| WNS 負值 | 過長組合路徑、clock period、缺 pipeline |
| 四組 PPA 看似一樣 | parameter 未真正影響 elaboration、舊 run 未清、top/config 用錯 |

更完整步驟見 `docs/除錯指南.md`。

### 9.3 完成後可延伸

1. 把 activation/weight buffer 移到 BRAM，加入 double buffering。
2. 將 software im2col 的部分逐步搬到 PL。
3. 用 AXI4-Lite 暫存器設定 mode、shift、vector length。
4. 加 cycle/performance counter 與 interrupt。
5. 匯入 SAIF 做更可信的 power estimate。
6. 研究不同 2:4 encoding 與真正的資料／cycle 節省。
7. 從 4-lane／小陣列放大，並做 timing-aware pipeline。

### 9.4 官方參考（需要時查，不用先全部讀）

- [PYNQ-Z2 Setup Guide](https://pynq.readthedocs.io/en/latest/getting_started/pynq_z2_setup.html)
- [PYNQ Board Settings／XDC](https://pynq.readthedocs.io/en/v2.5.1/overlay_design_methodology/board_settings.html)
- [PYNQ Overlay Design Methodology](https://pynq.readthedocs.io/en/v2.5/overlay_design_methodology.html)
- [PYNQ DMA](https://pynq.readthedocs.io/en/v2.7.0/pynq_libraries/dma.html)
- [PYNQ Python Overlay API／allocate](https://pynq.readthedocs.io/en/v2.5/overlay_design_methodology/python_overlay_api.html)
- [AMD XUP FPGA Vivado Flow](https://xilinx.github.io/xup_fpga_vivado_flow/)
- AMD UG901（Synthesis）、UG908（Programming and Debugging）、UG949（UltraFast Methodology），請依安裝版本從 AMD Docs 開啟。

---

## 附錄 A：第一次模擬的最小操作卡

1. 開 Vivado → Create Project。
2. RTL Project；不要勾 Project is an extensible Vitis platform。
3. 選 part `xc7z020clg400-1`。
4. 加 `rtl/*.sv` 到 Design Sources。
5. 加 `tb/*.sv` 到 Simulation Sources。
6. 在 Sources 視窗右鍵 TB → Set as Top。
7. Flow Navigator → Run Behavioral Simulation。
8. 看 Tcl Console 的 PASS/FAIL，而不是只看波形。
9. 若要重跑：先 restart，再 run all。

## 附錄 B：第一次看波形要加的訊號

- clock/reset；
- input valid/ready/data；
- output valid/ready/data/last；
- accumulator 或 state；
- mode/mask；
- TB 的 transaction counter/error counter。

將 radix 設為 signed decimal 與 hexadecimal各看一次。INT4 packing 用 hex 容易看 nibble；accumulator 正負用 signed decimal 容易判讀。

## 附錄 C：成果提交命名

```text
results/
├── tool_versions.txt
├── simulation/
│   ├── lab02_console.txt
│   ├── lab03_console.txt
│   └── lab04_axis_console.txt
├── vivado_reports/
│   ├── dense_int8/
│   ├── dense_int4/
│   ├── int8_2to4/
│   └── int4_2to4/
├── ppa_results.csv
├── figures/
└── board_test/
    ├── input.npy
    ├── expected.npy
    └── actual.npy
```

## 附錄 D：完成定義

- [ ] 四組暖身 starter 的 TODO 都完成，且未直接複製 solution。
- [ ] Lab02、Lab03、Lab04 所有 self-checking TB 為 PASS。
- [ ] Python 與 RTL 對 signed、packing、mask、rounding 的定義一致。
- [ ] AXI stall 時 payload 穩定。
- [ ] 至少完成一次 synthesis，理解 utilization report。
- [ ] 若有板卡，最小 DMA packet 與 golden result 完全一致。
- [ ] 四組 PPA 沒有捏造值，空值與 0 有區別。
- [ ] 圖表能由 CSV 一鍵重建。
- [ ] README 足以讓另一位同學在乾淨資料夾重跑。

