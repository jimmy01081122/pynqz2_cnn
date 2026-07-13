# PYNQ-Z2 adaptive／2:4 sparse CNN element

這是一份給「學過數位邏輯與 Python，但沒有用過 Vivado」學生的完整專案教材。原本 W1～W12 的內容已重新整理成 6 個獨立 Lab；每個 Lab 對應原進度的兩週，預計一天完成一個 Lab。

> 重要界線：本專案提供可模擬 RTL、Testbench、Vivado Tcl/XDC、PYNQ 驅動與分析工具，但不附假造的 `.bit`、`.hwh`、時序、功耗或準確率結果。這些板卡／工具版本相依的產物，必須由學生在本機 Vivado 與 PYNQ-Z2 上產生。

## 建議閱讀順序

1. `docs/專案教學文件.md`：從安裝、模擬到上板的完整主教材。
2. `docs/開始前檢查表.md`：開始前逐項確認工具、板卡與檔案。
3. 依序完成 `labs/Lab01_W1_W2` 到 `labs/Lab06_W11_W12`。
4. 卡住時查 `docs/除錯指南.md` 與各 Lab 的 README。
5. 用 `MANIFEST.md` 確認成果是否齊全，並查看 `TEST_REPORT.md` 的實際測試與環境限制。

## 六天／六個 Lab

| 天數 | 獨立 Lab | 對應原進度 | 當天可驗收成果 |
|---|---|---|---|
| Day 1 | Lab01 | W1～W2 | 環境檢查、第一個模擬、四組 TODO 暖身、量化／2:4 匯出 smoke test |
| Day 2 | Lab02 | W3～W4 | Dense INT8 PE 與 INT4/INT8 切換，通過自動比對 Testbench |
| Day 3 | Lab03 | W5～W6 | 2:4 sparse decoder、PE 陣列與 requantization 模擬通過 |
| Day 4 | Lab04 | W7～W8 | AXI4-Stream 包裝、backpressure 驗證、Block Design 與 PYNQ DMA 驅動 |
| Day 5 | Lab05 | W9～W10 | 四組配置批次建置流程與 PPA CSV；所有數字可追溯到 Vivado 報告 |
| Day 6 | Lab06 | W11～W12 | Trade-off 圖表、技術報告骨架與 repo 完整性檢查 |

## 專案資料夾

```text
FPGA_AI_Accelerator_6Day_Course/
├── README.md
├── ASSUMPTIONS.md
├── MANIFEST.md
├── TEST_REPORT.md
├── docs/
├── common/
├── labs/
│   ├── Lab01_W1_W2/
│   ├── Lab02_W3_W4/
│   ├── Lab03_W5_W6/
│   ├── Lab04_W7_W8/
│   ├── Lab05_W9_W10/
│   └── Lab06_W11_W12/
├── scripts/
└── lab_packages/
```

每個 Lab 都是獨立教學單元，至少包含：

- 一份繁體中文 README；
- 該日使用的程式碼；
- Testbench 或 smoke test；
- XDC（若只做模擬，會明確說明何時才會使用 XDC）；
- 完成條件與應保留的證據。

## 兩種執行路徑

### 路徑 A：先做純模擬（推薦第一次使用）

不接板子也能完成 Lab01～Lab03 的核心驗證。可使用 Vivado Behavioral Simulation；若電腦有 Icarus Verilog，也可用各資料夾提供的命令快速做語法與功能檢查。

### 路徑 B：完成 PYNQ-Z2 上板

Lab04 起需要 Vivado、正確的 PYNQ-Z2 board files、PYNQ SD image 與實體板卡。先產生 `.bit` 與 `.hwh`，再放到板子上的同一個資料夾，由 Python `Overlay` 載入。

## 成功標準

本課程的「完成」不是只看到 Vivado 顯示綠色勾勾，而是每一層都有可重現證據：

1. RTL 層：self-checking Testbench 印出 PASS，且錯誤數為 0。
2. 介面層：在 `TREADY=0` 時，`TVALID/TDATA/TLAST` 保持穩定。
3. 數值層：Python golden model 與 RTL／板上輸出逐筆相同。
4. 實作層：WNS、LUT、FF、DSP、BRAM、Power 均能回指原始 Vivado 報告。
5. 實驗層：四組配置採用相同時脈、資料量與測量方式，才做比較。

## 快速驗證

在專案根目錄執行：

```bash
python scripts/verify_project.py
python scripts/run_all_tests.py --require-simulator
```

第二行需要 Icarus Verilog。若沒有 simulator，runner 會明確顯示 `SKIP`／`INCOMPLETE`，不會把未執行的 HDL 誤報成 PASS。本次交付的精確結果見 `TEST_REPORT.md`。

要重建六個 Lab 分包、完整 ZIP、獨立教材與 SHA-256，將輸出目錄放在專案根目錄之外：

```bash
python scripts/build_release.py --output-dir ../release_output
```

## 使用的官方參考

- [PYNQ-Z2 設定指南](https://pynq.readthedocs.io/en/latest/getting_started/pynq_z2_setup.html)
- [PYNQ board settings 與 XDC 說明](https://pynq.readthedocs.io/en/v2.5.1/overlay_design_methodology/board_settings.html)
- [PYNQ DMA 使用方式](https://pynq.readthedocs.io/en/v2.7.0/pynq_libraries/dma.html)
- [AMD XUP Vivado Design Flow](https://xilinx.github.io/xup_fpga_vivado_flow/)
- [AMD UG901：`synth_design -mode out_of_context`](https://docs.amd.com/r/2024.2-English/ug901-vivado-synthesis/Running-Synthesis-with-Tcl)

# pynqz2_cnn
