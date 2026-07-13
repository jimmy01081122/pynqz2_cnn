# Lab05（W9–W10）：四組可直接模擬與合成的 PPA 實驗

本 Lab 是六天課程的第 5 天。資料夾已包含可編譯的四 PE `ai_accel_top`、self-checking testbench、四組 Icarus runner 與 Vivado batch flow，不需要再從外部專案借 RTL。你會固定運算語意，只改變資料寬度與 dense／2:4 datapath，再比較 Performance、Power、Area。

> 本資料夾不預填任何宣稱為 FPGA 實測的 PPA 數字。只有 Vivado 在你的電腦完成 route 後產生的原始 report，才可作為正式結果。

## 1. 四組配置

| ID | 顯示名稱 | `DATA_WIDTH` | `ENABLE_2TO4` | 每個 PE 的乘法數 |
|---|---|---:|---:|---:|
| `dense_int8` | Dense INT8 | 8 | 0 | 4 |
| `dense_int4` | Dense INT4 | 4 | 0 | 4 |
| `int8_2to4` | INT8 2:4 | 8 | 1 | 2 |
| `int4_2to4` | INT4 2:4 | 4 | 1 | 2 |

所有配置都是四個 PE。Dense PE 直接做四個 signed multiply；sparse PE 只保存兩個 signed weight，由 4-bit mask 選出兩個 activation，再做兩個 multiply。Sparse mask popcount 不是 2 時，該 PE 安全輸出 bias-only，transaction 同時令 `out_mask_error=1`。

## 2. 資料夾

```text
Lab05_W9_W10/
├── rtl/ai_accel_top.sv          # 四 PE，可合成，DATA_WIDTH/ENABLE_2TO4 parameters
├── tb/tb_ai_accel_top.sv        # 四組共用 self-checking TB
├── sim/
│   ├── files.f
│   └── run_iverilog.sh          # 一次跑完四組
├── constraints/lab05_timing.xdc
├── vivado/
│   ├── run_config.tcl
│   └── configs/
│       ├── dense_int8.tcl
│       ├── dense_int4.tcl
│       ├── int8_2to4.tcl
│       └── int4_2to4.tcl
└── scripts/collect_ppa.py
```

`build/` 是模擬與 Vivado 產物，不需提交版本控制。

## 3. 先看懂 top 介面

- `in_activations`：四個 lane，lane0 在最低位元。
- `in_dense_weights`：每個 PE 四個 weight，只在 dense config 使用。
- `in_sparse_values`：每個 PE 兩個 compressed weight，只在 sparse config 使用。
- `in_sparse_masks`：每個 PE 一個 4-bit mask，bit0 對應 activation lane0。
- `in_bias` / `out_result`：每個 PE 一個 signed 32-bit slice，PE0 在最低位元。
- `in_valid/in_ready` 與 `out_valid/out_ready`：一進一出的 elastic handshake。

輸出 register 被 backpressure 擋住時，`out_valid`、`out_result`、`out_mask_error` 都保持不變；舊輸出被接受的同一拍也可接收新 input 並立即替換。

## 4. 先跑四組 RTL 模擬

在 Lab05 根目錄執行：

```bash
bash sim/run_iverilog.sh
```

runner 會依序編譯並執行：

```text
dense_int8  dense_int4  int8_2to4  int4_2to4
```

每組 TB 都檢查：四個 PE 的 signed 算術、三拍 backpressure 穩定性、consume-and-replace、以及 invalid mask。Dense 組也會確認 mask 被忽略。最後應看到：

```text
[PASS] Lab05 all four configurations passed.
```

若顯示找不到 `iverilog` 或 `vvp`，先安裝 Icarus Verilog，再重新執行；runner 不會把缺少 simulator 誤報成 PASS。

## 5. Vivado 預設值（PYNQ-Z2）

本 Lab 的預設設定已可直接指向自己的 RTL：

- FPGA part：`xc7z020clg400-1`
- RTL directory：`Lab05_W9_W10/rtl`
- top：`ai_accel_top`
- clock port：`clk`
- target period：10 ns（100 MHz）

`run_config.tcl` 在任何 Vivado command 前會先檢查 RTL directory、top module declaration 與 XDC 是否存在。需要比較其他器件或 RTL 時，仍可用 `FPGA_PART`、`RTL_DIR`、`TOP`、`BUILD_DIR` 環境變數覆寫；正式報告必須記錄實際值。

XDC 只建立 `clk` timing constraint，不猜 PACKAGE_PIN。這個寬平行介面是 block-level PPA top，不是直接接到 PYNQ-Z2 排針的 bitstream top。`run_config.tcl` 因此使用 `synth_design -mode out_of_context`：不插入數百個 I/O buffer，但仍會執行最佳化、放置、繞線並產生三份報告。若拿掉 OOC，I/O 數量會掩蓋真正要比較的 PE 邏輯。

## 6. 先做不呼叫 Vivado 的 Tcl smoke

Linux：

```bash
SMOKE_ONLY=1 tclsh vivado/run_config.tcl dense_int8
SMOKE_ONLY=1 tclsh vivado/run_config.tcl dense_int4
SMOKE_ONLY=1 tclsh vivado/run_config.tcl int8_2to4
SMOKE_ONLY=1 tclsh vivado/run_config.tcl int4_2to4
```

Windows PowerShell：

```powershell
$env:SMOKE_ONLY = "1"
tclsh vivado/run_config.tcl dense_int8
Remove-Item Env:SMOKE_ONLY
```

成功訊息會明確指出 config、預設 RTL_DIR、top declaration 與 XDC 都存在。此步驟不產生 PPA。

## 7. 執行 Vivado PPA flow

從 Lab05 根目錄執行一組：

```bash
vivado -mode batch -source vivado/run_config.tcl -tclargs dense_int8
```

把最後參數換成另外三個 config。每組成功後會產生：

```text
build/<config>/
├── reports/
│   ├── utilization.rpt
│   ├── timing_summary.rpt
│   └── power.rpt
├── routed.dcp
└── run_metadata.csv
```

`run_metadata.csv` 只是配置摘要；三份 `.rpt` 與 `routed.dcp` 才是可追溯證據。這是 block-level OOC 結果，不能宣稱為完整 PYNQ-Z2 bitstream 或整板量測。

## 8. 收集結果

```bash
python scripts/collect_ppa.py --runs-dir build --output ppa_results.csv
```

解析器自測與空白模板：

```bash
python scripts/collect_ppa.py --self-test
python scripts/collect_ppa.py --template-only --output ppa_template.csv
```

缺 report 時 collector 會留空並標示 `missing_reports`，不填猜測數字。

## 9. 公平比較與判讀

四組必須共用 FPGA part、Vivado 版本、clock constraint、implementation flow 與相同 input workload。先看 `status`，再看 LUT/FF/DSP、WNS 與 power：

- `WNS >= 0` 只代表通過目前 10 ns constraint。
- `fmax_est_mhz` 是由 WNS 推得的粗估，不等於板上量測。
- power 是 Vivado switching-activity 假設下的估計，報告要記錄 activity 來源。
- accuracy、latency、throughput 需由軟體或 RTL 測量另行填入，不由 PPA report 自動產生。

## 10. 驗收

- [ ] `bash sim/run_iverilog.sh` 四組都顯示 PASS。
- [ ] 四個 `SMOKE_ONLY` 都找到預設 Lab05 RTL、`ai_accel_top` 與 XDC。
- [ ] 能指出 dense 每 PE 四個 multiply、sparse 每 PE 兩個 multiply 的 RTL。
- [ ] 能解釋 invalid mask 的 bias-only 與 `out_mask_error` 行為。
- [ ] 至少一組 Vivado flow 產生 routed checkpoint 與三份原始 report。
- [ ] collector 不會替缺檔填假數據，正式 CSV 可追溯到原始 report。
