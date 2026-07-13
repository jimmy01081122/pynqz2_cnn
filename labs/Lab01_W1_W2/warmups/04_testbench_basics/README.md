# 暖身 4：Testbench 技法（clock、`$display`、`$monitor`）

## 這題要學什麼

這一題的主角是 testbench。為了練習，我們自行設計一個很小的 DUT：`tiny_counter`。

- `rst=1`：在下一個上升緣把 `count` 清成 0。
- `rst=0 && en=1`：在每個上升緣把 `count` 加 1。
- `rst=0 && en=0`：保持原值。
- 加到全 1 後再加 1，依固定寬度自然回到 0。

你會學會產生 clock、安排 stimulus、印出訊息，以及讓 TB 自己判斷 PASS/FAIL。

## DUT 與 testbench 的分工

`tiny_counter.sv` 是要合成到 FPGA 的設計：不能使用 `#5`、`$display` 等僅供模擬的語法。

`tb_tiny_counter.sv` 只在電腦上模擬，不會合成進 FPGA，因此可以使用：

```systemverilog
always #(CLK_PERIOD/2) clk = ~clk;
```

這會每半個週期反相一次 clock。若 `timescale` 是 `1ns/1ps` 且 `CLK_PERIOD=10`，完整週期為 10 ns，也就是模擬中的 100 MHz。

## `$display` 與 `$monitor`

`$display` 像拍照：程式執行到該行時印一次。

```systemverilog
$display("目前 count=%0d", count);
```

`$monitor` 像持續追蹤：呼叫一次後，只要參數中的任一值改變就自動印一行。

```systemverilog
$monitor("t=%0t rst=%b en=%b count=%0d", $time, rst, en, count);
```

通常一個 testbench 只開一個 `$monitor`。訊息太多時可用 `$monitoroff` 暫停、`$monitoron` 恢復。

格式提示：`%b` 是二進位、`%h` 是十六進位、`%0d` 是十進位、`%0t` 是時間。

## 避免上升緣競爭

若 TB 與 DUT 都剛好在上升緣改訊號，可能產生 race。這份範例採簡單紀律：

- TB 在 `@(negedge clk)` 改 `rst`、`en`。
- DUT 在 `@(posedge clk)` 取樣。
- TB 在上升緣後 `#1` 再檢查 nonblocking assignment 更新後的結果。

更進階的課程會介紹 clocking block；目前先把這個安全節奏練熟。

## TODO 步驟

1. 在 `starter/tiny_counter.sv` 完成 reset、enable、保持三種行為。
2. 在 starter TB 找到 clock 產生器，確認一個週期為何是 `CLK_PERIOD`。
3. 取消 `$monitor` 範例的註解並補好要觀察的欄位。
4. 用 `@(negedge clk)` 安排 stimulus。
5. 加入 enable=0 保持、回捲、再次 reset 的自我檢查。
6. 所有測試完成後設定 `tb_todos_done=1`。

## 第一次用 Vivado 跑 TB

1. 建立 RTL Project，不指定 Sources 也可以先完成精靈。
2. **Add Sources → Add or create design sources**：加入 `starter/tiny_counter.sv`。
3. **Add Sources → Add or create simulation sources**：加入 `starter/tb_tiny_counter.sv`。
4. 在 Sources 的 Simulation Sources 對 `tb_tiny_counter` 按右鍵，選 **Set as Top**。
5. **Run Simulation → Run Behavioral Simulation**。
6. 按工具列 Run All，或在 Tcl Console 輸入 `run all`。

Console 會看到 `$display` / `$monitor` 文字；Waveform 會看到相同訊號的圖形。兩者互相補充：波形適合看時序，self-checking 訊息適合自動回歸。

## 何謂 self-checking TB

只印波形、靠人眼看很容易漏錯。self-checking TB 會把實際值與 expected value 比較，失敗時用 `$fatal` 讓模擬回傳非零狀態，成功時清楚印 `[PASS]`。`solution/` 示範了這種寫法。

這題仍是純模擬，所以不需要 `.xdc`。
