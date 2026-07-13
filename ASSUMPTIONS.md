# 專案假設與範圍

這份教材依下列假設實作。若實際設備不同，先修改這一頁，再修改對應 XDC／Tcl，避免「程式看似正確但永遠無法上板」。

## 硬體與工具

- 板卡：PYNQ-Z2。
- FPGA part：`xc7z020clg400-1`。
- Vivado：2025.2；若學校使用其他版本，可照 GUI 步驟操作，但不要跨版本直接重用 `.xpr`。
- PYNQ：3.x 系列；實際 SD image 版本以手上板卡可用版本為準。
- RTL：SystemVerilog，合成目標為 Xilinx 7-series。
- 純 PL 練習時脈：板上 125 MHz，`sysclk` 位於 H16，XDC period 為 8 ns。
- PS-PL 系統時脈：由 Zynq PS 的 `FCLK_CLK0` 提供，教材預設 100 MHz；此時 AXI 邏輯不使用 H16 外部時脈。

## 加速器功能邊界

- 教學核心是「向量點積／PE 陣列核心」，展示 INT4/INT8 切換、2:4 結構化稀疏、AXI4-Stream 與 PPA 評估。
- 完整 CNN 的卷積滑窗、feature-map tiling、所有層排程與 activation buffering 不全放進 RTL；由 Python 端先整理成加速器要處理的向量／封包。這是 6 天內可驗證、可理解的範圍。
- INT4 是二補數有號數，合法範圍 `-8..7`；實際 packing 規則以 Lab02 README 和 RTL port 註解為準。
- INT8 是二補數有號數，合法範圍 `-128..127`。
- 2:4 稀疏代表每個連續 4 權重群組保留 2 個非零值；mask 格式與非法 mask 行為由 Lab03 明確定義。
- Requantization 採定點右移、四捨五入／截斷與飽和的教學版本，不宣稱等同任何特定 PyTorch backend。

## 六天的意思

- 一天對應原本兩週內容，是密集實作安排，預估每日 8～10 小時。
- 六天內合理的完成標準是：模擬全通、AXI 串流可上板、能產生自己的 PPA 資料與圖表。
- CIFAR-10 長時間訓練、四套完整 bitstream、精準板級功耗量測可能超過六天；教材提供 smoke mode、可續跑腳本與紀錄格式，不虛構結果。

## XDC 使用原則

- XDC 的 port 名稱必須與目前 top module 完全一致。
- Behavioral Simulation 不需要 XDC。
- 若設計只使用 PS 產生的 FCLK 且不接 PL 外部腳位，通常不需要為 AXI 時脈指定 H16。
- 本專案只啟用實際用到的 PYNQ-Z2 腳位，其餘腳位保持未約束，避免複製整份 Master XDC 後造成 port 對不上。
- H16、R14、P14、N16、M14、M20、M19、D19、D20、L20、L19 等教學用腳位，均應在實作前與 PYNQ-Z2 Master XDC／原理圖再次核對。

