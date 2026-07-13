# Lab01 暖身練習（原文件 3.2）

這個資料夾只收錄原教學文件第 3.2 節指定的四組暖身題：

1. `01_parameterized_adder`：參數化位寬加法器與 signed overflow
2. `02_valid_ready_mac`：帶 `valid/ready` 握手的簡單 MAC
3. `03_sync_fifo`：單一時脈的小型同步 FIFO
4. `04_testbench_basics`：用小型 counter 練習 clock、`$display`、`$monitor` 與自我檢查

每一題都有：

- `README.md`：從零開始的觀念、介面、波形與 Vivado 操作說明。
- `starter/`：可編譯但尚未完成的 DUT 與 testbench；請搜尋 `TODO`。
- `solution/`：完整 SystemVerilog 解答與 self-checking testbench。
- `files.f`：給 Icarus Verilog 使用的檔案清單。

## 建議順序

先讀每題 README，再複製或直接修改 `starter/`。不要一開始就看 `solution/`。完成後先讓 starter testbench 全部通過，再用 solution 對照寫法。

## 使用 Vivado 的共同流程

1. 開啟 Vivado，按 **Create Project**。
2. 選 **RTL Project**；這些暖身題不需要加入 `.xdc`，也不需要產生 bitstream。
3. 在 **Add Sources** 加入該題 `starter/` 的 DUT `.sv`。
4. 在 **Add Simulation Sources** 加入同一題 `starter/` 的 `tb_*.sv`。
5. 確認 testbench 被設為 Simulation Top：在 Sources 視窗對 testbench 按右鍵，選 **Set as Top**。
6. 點 **Run Simulation → Run Behavioral Simulation**。
7. 在 Tcl Console 查看 `[PASS]`、`[FAIL]` 或 `[TODO]`；需要時把訊號拖到波形視窗。

> `.xdc` 是把 FPGA 腳位連到實體開關、LED、時脈等資源的約束檔。這四題只做行為模擬，沒有固定開發板，因此刻意不使用 `.xdc`。

## 使用 Icarus Verilog（可選）

進入某一題的 `starter/` 或 `solution/` 後執行：

```bash
iverilog -g2012 -f files.f -o sim.out
vvp sim.out
```

starter 出現 `[TODO]` 或測試失敗是預期現象；solution 應以 `[PASS]` 結束。
