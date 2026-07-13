# 專案交付清單（Manifest）

本清單描述壓縮檔內應有的教學原始碼。執行產物（Vivado build、checkpoint、bitstream、Python cache）不屬於這份乾淨交付。

## 六個獨立 Lab

| Lab | 對應進度 | 原始檔數 | 核心交付 |
|---|---|---:|---|
| `Lab01_W1_W2` | W1–W2／Day 1 | 49 | 僅四組暖身的 starter/solution/TODO/TB、離線 CNN 工具、explicit 2:4 mask 與 compressed exporter、PYNQ-Z2 switch/LED demo RTL/TB/XDC |
| `Lab02_W3_W4` | W3–W4／Day 2 | 7 | Dense INT8/INT4 PE、self-checking TB、Icarus runner、XDC、Vivado Tcl |
| `Lab03_W5_W6` | W5–W6／Day 3 | 10 | 2:4 decoder、sparse PE、4×4 array、requantization、TB、XDC、Vivado Tcl |
| `Lab04_W7_W8` | W7–W8／Day 4 | 9 | 四模式 AXI4-Stream accelerator、TB、PYNQ DMA driver/golden model、Block Design Tcl、XDC |
| `Lab05_W9_W10` | W9–W10／Day 5 | 12 | 四 PE configurable top、四配置 TB、OOC Vivado PPA flow、report collector、timing XDC |
| `Lab06_W11_W12` | W11–W12／Day 6 | 7 | PPA template/sample、trade-off analyzer、repo checker、技術報告模板 |

每個 Lab 的獨立 ZIP 位於 `lab_packages/`；整份 ZIP 內仍保留原始 `labs/` 目錄，方便直接閱讀與修改。

## 共用與導覽檔

- `README.md`：課程入口、六日安排、驗證與使用順序。
- `ASSUMPTIONS.md`：PYNQ-Z2、part、clock、數值格式與專案邊界。
- `docs/專案教學文件.md`：零 Vivado 經驗適用的完整主教材；不含原第 10 節一頁式摘要。
- `docs/需求對照表.md`：逐項對應本次七點需求。
- `docs/程式碼與XDC索引.md`：主題到 RTL／TB／XDC 的索引。
- `docs/開始前檢查表.md`、`docs/除錯指南.md`：課前檢查與分層除錯。
- `common/constraints/pynq_z2_user_io.xdc`：經核對的 PYNQ-Z2 最小 user-I/O 約束參考。
- `scripts/verify_project.py`：靜態交付驗證。
- `scripts/run_all_tests.py`：Python 與 HDL 整合測試；沒有 simulator 時不會誤報完整 PASS。
- `scripts/build_release.py`：重建六個 Lab ZIP、完整 ZIP、獨立教材與 SHA-256。
- `TEST_REPORT.md`：本次實際執行的測試與環境限制。

## 暖身題邊界

`warmups/` 精確只有原文件 3.2 的四組：

1. 參數化加法器與 overflow。
2. valid/ready MAC。
3. 同步 FIFO。
4. Testbench 技法。

每組均有繁中 README、含 TODO 的 `starter/`、無 TODO 的完整 `solution/`，兩者都有 DUT、TB 與 filelist。`board_demo/` 是題目一的可選 PYNQ-Z2 板級 top，不是第五個暖身題。

## 刻意不包含

- 未在此環境產生的 `.bit`、`.hwh`、`.xsa`、`.dcp`。
- 假造的 Vivado utilization/timing/power 或板上量測數字。
- 假造的 CIFAR-10 accuracy。
- `build/`、`artifacts/`、`__pycache__/`、`.pyc`、`.vvp` 等可重建產物。

Lab06 的 `ppa_results_sample.csv` 僅供畫圖練習，每列都有 `ILLUSTRATIVE_ONLY_DO_NOT_REPORT`；正式成果必須由學生自己的原始報告與量測產生。
