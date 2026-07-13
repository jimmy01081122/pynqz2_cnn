# FPGA AI 加速器專案報告

> 使用方式：複製本檔後，替換所有 [請填入]。任何示意值都不可留在正式報告。

## 1. 專案資訊

| 項目 | 內容 |
|---|---|
| 組別 / 姓名 | [請填入] |
| 日期 | [請填入] |
| Git commit / 壓縮檔版本 | [請填入] |
| Vivado 版本 | [請填入] |
| FPGA board / part | [請填入] |
| Python / PyTorch 版本 | [請填入] |

## 2. 目標與驗收條件

本專案的目標是 [請填入]。

必要門檻：

- test accuracy >= [請填入] %。
- WNS >= 0 ns，clock constraint = [請填入] ns。
- latency <= [請填入] cycles。
- 其他限制：[請填入]。

## 3. 系統架構與資料流

[請插入架構圖，並說明輸入格式、權重格式、MAC/PE、累加位寬、activation、輸出格式與控制流程。]

### 3.1 數值格式

| 訊號 / 資料 | 位寬 | signed | scale / 小數位 | rounding | saturation |
|---|---:|---|---|---|---|
| input activation | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] |
| weight | INT4 / INT8 | yes | [請填入] | [請填入] | [請填入] |
| accumulator | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] |
| output activation | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] |

## 4. 軟體 Baseline、量化與 2:4

### 4.1 可重現條件

| 項目 | 設定 |
|---|---|
| dataset / split | [請填入] |
| preprocessing | [請填入] |
| random seed | [請填入] |
| epochs / optimizer / LR | [請填入] |
| checkpoint SHA-256 | [請填入] |
| calibration set / batches | [請填入] |

### 4.2 PTQ-ish 方法

[請說明 weight quantization、activation calibration、scale、zero-point、rounding，以及目前哪些部分不是 bit-accurate integer inference。]

### 4.3 2:4 方法

[請說明 group 軸、tail 處理、剪枝順序，以及每組是否確實最多兩個非零值。]

## 5. RTL 與 Testbench 驗證

| 測試 | 輸入數量 | 期望值來源 | pass | log / waveform |
|---|---:|---|---|---|
| directed corner cases | [請填入] | [請填入] | [請填入] | [請填入] |
| random regression | [請填入] | [請填入] | [請填入] | [請填入] |
| overflow / saturation | [請填入] | [請填入] | [請填入] | [請填入] |
| 2:4 index / zero skip | [請填入] | [請填入] | [請填入] | [請填入] |

Latency 定義：[請填入 accepted input 與 valid output 的精確事件]。

Throughput 公式：[請填入運算數定義、clock 與量測區間]。

## 6. 四組配置結果

> 資料來源：[請填入正式 CSV 路徑]。不可使用 ppa_results_sample.csv。

| 配置 | Accuracy (%) | Latency (cycles) | Throughput (GOPS) | LUT | FF | DSP | BRAM | WNS (ns) | Power (W) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dense INT8 | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] |
| Dense INT4 | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] |
| INT8 2:4 | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] |
| INT4 2:4 | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] | [請填入] |

Vivado PPA 條件：part=[請填入]，clock=[請填入] ns，strategy=[請填入]，power activity=[請填入]。

## 7. Trade-off 與 Pareto 分析

[請插入 accuracy_vs_lut.png]

[請插入 throughput_vs_power.png]

- 權重 accuracy / throughput / LUT / power：[請填入]。
- Pareto front：[請填入]。
- 通過必要門檻的配置：[請填入]。
- 最終選擇：[請填入]。
- 選擇理由：[請以數據與應用情境說明]。

## 8. 限制、威脅效度與待辦

- PTQ-ish 與真正 integer/RTL bit-accurate inference 的差距：[請填入]。
- Fmax_est 與實際可達 clock 的差距：[請填入]。
- Vivado power activity 假設：[請填入]。
- 測試資料量與 corner-case 覆蓋不足之處：[請填入]。
- 板上尚未驗證的部分：[請填入]。

## 9. 結論與重現方式

結論：[請填入]。

從乾淨環境重現的命令：

    [請填入環境建立命令]
    [請填入 baseline / prune / quantize / export 命令]
    [請填入 RTL simulation 命令]
    [請填入 Vivado batch 命令]
    [請填入 trade-off 分析命令]

原始證據清單：

- checkpoint / manifest：[請填入]。
- TB log / waveform：[請填入]。
- Vivado reports / DCP：[請填入]。
- 正式 CSV / 圖表：[請填入]。

