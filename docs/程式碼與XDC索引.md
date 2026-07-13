# 程式碼、Testbench 與 XDC 索引

本頁回答「教學文件的每一部分，要開哪一個檔案」。實際檔名若在個別 Lab 中有更細分版本，以該 Lab README 為準。

| 教學主題 | 完整程式 | Testbench／測試 | XDC／實作檔 |
|---|---|---|---|
| 參數化加法器與 overflow | `labs/Lab01_W1_W2/warmups/01_parameterized_adder/solution/` | 同資料夾 `solution/` | optional `labs/Lab01_W1_W2/board_demo/constraints/pynq_z2_adder_demo.xdc` |
| valid/ready MAC | `labs/Lab01_W1_W2/warmups/02_valid_ready_mac/solution/` | 同資料夾 `solution/` | 純模擬核心；不直接綁板上腳位 |
| 同步 FIFO | `labs/Lab01_W1_W2/warmups/03_sync_fifo/solution/` | 同資料夾 `solution/` | 純模擬核心；不直接綁板上腳位 |
| Testbench 技法 | `labs/Lab01_W1_W2/warmups/04_testbench_basics/solution/` | 同資料夾 `solution/` | 不需要 XDC |
| Dense INT8 PE | `labs/Lab02_W3_W4/rtl/` | `labs/Lab02_W3_W4/tb/` | `labs/Lab02_W3_W4/constraints/` |
| INT4/INT8 切換 | `labs/Lab02_W3_W4/rtl/` | `labs/Lab02_W3_W4/tb/` | `labs/Lab02_W3_W4/constraints/` |
| 2:4 sparse decoder | `labs/Lab03_W5_W6/rtl/` | `labs/Lab03_W5_W6/tb/` | `labs/Lab03_W5_W6/constraints/` |
| PE array 與 requant | `labs/Lab03_W5_W6/rtl/` | `labs/Lab03_W5_W6/tb/` | `labs/Lab03_W5_W6/constraints/` |
| AXI4-Stream wrapper | `labs/Lab04_W7_W8/rtl/` | `labs/Lab04_W7_W8/tb/` | `labs/Lab04_W7_W8/constraints/` |
| PYNQ DMA driver | `labs/Lab04_W7_W8/python/` | 軟體 golden compare／DMA 驗證 | `labs/Lab04_W7_W8/constraints/pynq_z2_lab04.xdc`（刻意無 PL 外部腳位） |
| 四組 PPA | `labs/Lab05_W9_W10/rtl/ai_accel_top.sv` | `labs/Lab05_W9_W10/tb/tb_ai_accel_top.sv` 與 `sim/run_iverilog.sh` | `labs/Lab05_W9_W10/constraints/lab05_timing.xdc` 與 `vivado/` |
| Trade-off 圖表 | `labs/Lab06_W11_W12/` | sample/template CSV smoke test | 不需要 XDC |

`starter/` 是留有 TODO 的學生版；`solution/` 是可對照的完整解答。主加速器 Labs 則直接提供完整版本，讓學生把時間用在理解、模擬、修改與量測。

