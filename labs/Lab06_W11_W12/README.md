# Lab06（W11–W12）：Trade-off 分析、畫圖與專案驗收

本 Lab 是六天課程的第 6 天。你會把 Lab01 的 accuracy、RTL/TB 的 latency/throughput 與 Lab05 的 Vivado PPA 合併，找出四組配置的取捨，最後完成可追溯的報告與專案資料夾檢查。

## 最重要的資料原則

- data/ppa_results_sample.csv 全部是教學用虛構示意值，data_source 明確標為 ILLUSTRATIVE_ONLY_DO_NOT_REPORT。
- data/ppa_results_template.csv 沒有數值，應複製後填入自己的結果。
- 正式報告不得把 sample CSV 的圖或數字當成實測。
- Vivado 估算、RTL 模擬與板上量測是三種不同證據，報告中必須分開標示。

## 資料夾導覽

    Lab06_W11_W12/
    ├── README.md
    ├── requirements.txt
    ├── REPORT_TEMPLATE.md
    ├── data/
    │   ├── ppa_results_sample.csv
    │   └── ppa_results_template.csv
    └── scripts/
        ├── analyze_tradeoffs.py
        └── check_repo.py

## 1. 準備正式 CSV

先把模板複製成自己的檔案，例如 results/ppa_results_measured.csv，然後依下列來源填寫：

| 欄位 | 來源 |
|---|---|
| lut / ff / dsp / bram | Vivado utilization.rpt |
| wns_ns | Vivado timing_summary.rpt |
| fmax_est_mhz | Lab05 collector 粗估；正式 Fmax 最好重跑 clock sweep |
| power_w | Vivado power.rpt，並記錄活動率來源 |
| accuracy_pct | 固定 test split 的軟體或 bit-accurate 驗證 |
| latency_cycles | RTL TB 從 accepted input 到 valid output 的 cycle 數 |
| throughput_gops | 以報告中明確公式計算 |

status 應填 parsed 或 measured，data_source 應能追溯，例如 vivado_2025_1_plus_rtl_tb。notes 寫下任何與其他配置不同的條件。

## 2. 先用示意資料學畫圖

安裝畫圖套件：

    python -m pip install -r requirements.txt

執行：

    python scripts/analyze_tradeoffs.py data/ppa_results_sample.csv --output-dir demo_results

會產生：

- analysis_summary.csv：原始欄位、正規化值、加權分數與 Pareto 標記。
- recommendations.md：依目前權重排序的文字摘要。
- accuracy_vs_lut.png：準確率對 LUT。
- throughput_vs_power.png：吞吐量對功耗。

輸出會保留「示意資料」警告。確認流程後刪除 demo_results，改用自己的 measured CSV。

## 3. 分析自己的結果

    python scripts/analyze_tradeoffs.py results/ppa_results_measured.csv --output-dir results/analysis

預設權重：

- accuracy：0.35，越高越好。
- throughput：0.25，越高越好。
- LUT：0.20，越低越好。
- power：0.20，越低越好。

可依情境改權重，四個值必須大於等於 0 且總和大於 0：

    python scripts/analyze_tradeoffs.py results/ppa_results_measured.csv --output-dir results/edge_device --weights accuracy=0.30,throughput=0.20,lut=0.15,power=0.35

加權分數只用來協助討論，不能證明唯一最佳設計。必須同時檢查 timing 是否通過、accuracy 是否達門檻，以及 Pareto front。

如果尚未安裝 matplotlib，可先驗證 CSV 與分析：

    python scripts/analyze_tradeoffs.py data/ppa_results_sample.csv --output-dir temp_analysis --no-plot

## 4. 如何解釋 Pareto front

若 A 在 accuracy、throughput 不低於 B，同時 LUT、power 不高於 B，而且至少一項更好，則 A dominates B。沒有被其他配置 dominate 的配置會標為 pareto=True。

Pareto 不代表一定採用。例：

- 邊緣裝置可能優先 power。
- 期末展示可能先要求 accuracy 過門檻。
- 教學用設計可能優先可除錯性，而不是最小 LUT。

## 5. 完成報告

複製 REPORT_TEMPLATE.md 後，替換每一個 [請填入]。每張表或圖都應寫清楚：

- 資料來源檔案。
- 工具版本、FPGA part 與 clock。
- 是示意、估算、模擬還是板上量測。
- 四組配置是否使用相同條件。

不要刪掉限制與威脅效度章節；誠實說明 PTQ-ish、vectorless power 與 Fmax 粗估，比提供看似完整但不可追溯的數字更重要。

## 6. 專案完成檢查

從 Lab06 資料夾執行：

    python scripts/check_repo.py --root ../..

若課程其他 Lab 尚未合併，可先看完整清單但不讓命令失敗：

    python scripts/check_repo.py --root ../.. --allow-incomplete

JSON 輸出適合 CI：

    python scripts/check_repo.py --root ../.. --json

檢查內容包含六個 Lab README、Lab01 軟體流程、四組 Vivado config、XDC、RTL、testbench、四題 warmup TB，以及正式結果是否仍混入 ILLUSTRATIVE_ONLY_DO_NOT_REPORT。

## 7. 最終驗收

- 四組配置都有同條件下的 accuracy、latency、throughput 與 PPA。
- timing 未通過的配置沒有被包裝成成功結果。
- 每個正式數字都能追溯到 checkpoint、log、TB 或 Vivado report。
- 圖表標籤、單位、資料來源完整。
- 報告說明 PTQ-ish 與 bit-accurate RTL 的差距。
- check_repo.py 在不加 --allow-incomplete 時回傳 PASS。

