# 測試報告

測試日期：2026-07-13（Asia/Taipei）

## 結果摘要

```text
SUMMARY: PASS (18 passed, 0 failed, 0 skipped)
```

`scripts/run_all_tests.py --require-simulator` 已在實際 Icarus simulator 上執行，而不是只做檔案存在性檢查。

## 測試環境

- Python 3.10.12
- NumPy 2.2.6
- Icarus Verilog 11.0 (stable)
- Tcl 8.6.12（只用於 `SMOKE_ONLY`，不呼叫 Vivado command）
- Vivado：此執行環境未安裝
- PyTorch／torchvision：此執行環境未安裝
- PYNQ-Z2 實板：此執行環境未連接

Icarus 與 Tcl 僅解壓在 `/tmp` 作驗證，沒有打包進專案，也沒有修改系統安裝。

## 18 個整合測試

### 結構與 Python（6）

1. 靜態交付驗證：24 項全 PASS；精確六 Lab、精確四暖身、TODO 規則、必要 RTL/TB/XDC/Tcl/Python、禁用摘要文字與 illustrative marker。
2. Lab01 離線 smoke：2:4 pruning、explicit masks、retained-zero、dense/sparse packing 與合法 padding。
3. Lab05 `collect_ppa.py --self-test`。
4. Lab06 `analyze_tradeoffs.py --self-test`。
5. Lab06 illustrative CSV 分析；正確顯示 `ILLUSTRATIVE_ONLY_DO_NOT_REPORT` 警告。
6. Lab06 repo checker：PASS，保留一個預期警告「尚無可追溯實測 CSV」。

### SystemVerilog 實跑（12）

1. 暖身 01：參數化加法器／overflow。
2. 暖身 02：valid/ready MAC／backpressure。
3. 暖身 03：同步 FIFO。
4. 暖身 04：tiny counter／self-checking TB 技法。
5. Lab01 PYNQ-Z2 switch/LED board demo：四種輸入全通過。
6. Lab02：Dense INT8/INT4 PE 與 backpressure。
7. Lab03：2:4 decoder、sparse array、requantization 與 backpressure。
8. Lab04：dense/sparse INT8/INT4、invalid mask、TLAST 與 backpressure。
9. Lab05：Dense INT8。
10. Lab05：Dense INT4。
11. Lab05：2:4 INT8。
12. Lab05：2:4 INT4。

Lab05 四配置另有 testbench watchdog，可將 time-0 loop 或握手 deadlock 轉成明確失敗，而非無限等待。

## 額外驗證

- 全部 19 個 Python 檔以內建 `compile()` 做語法檢查：PASS，未產生 `.pyc`。
- Lab01 CLI demos：train dry-run、2:4 prune、INT8/INT4 quantization、dense packing、sparse INT8 `00050201`、sparse INT4 `00A51F21`：PASS。
- Lab05 四個 Tcl config 的 `SMOKE_ONLY`：全部找到 config、`xc7z020clg400-1`、本 Lab RTL、`ai_accel_top` 與 XDC。
- 全部 Markdown 相對連結：PASS。

## 尚未在此環境執行

- Vivado synthesis、OOC place/route、Block Design validation 與 bitstream generation。
- PYNQ DMA 實板傳輸、`.bit/.hwh` 載入與板上 timing/power。
- PyTorch 完整 training → pruning → PTQ checkpoint 流程及 CIFAR-10 accuracy。

因此專案不附上述產物或測量值。Lab04 提供可執行的 Block Design／PYNQ driver；Lab05 使用官方建議的 `synth_design -mode out_of_context` 避免寬平行 microarchitecture top 被板級 I/O 數量干擾。學生需在自己的 Vivado/PYNQ-Z2 環境完成最後三項驗收。
