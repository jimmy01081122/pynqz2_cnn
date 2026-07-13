# 暖身 3：小型同步 FIFO

## 這題要學什麼

FIFO（First In, First Out）像排隊：最早寫入的資料會最早讀出。這題實作單一 clock domain 的同步 FIFO，練習：

- 小型記憶體陣列 `mem`
- 讀、寫 pointer
- 使用量 `count`
- `full` / `empty` 邊界保護
- 同一上升緣同時讀與寫

「同步」表示狀態只在 `clk` 上升緣更新。本題的 `rd_data` 是 registered output：一次有效讀取發生後，資料才在該上升緣之後出現在 `rd_data`。

## DUT 介面與接受條件

| 名稱 | 方向 | 說明 |
|---|---|---|
| `clk` | input | 單一上升緣時脈 |
| `rst_n` | input | 低有效、同步 reset |
| `wr_en`, `wr_data` | input | 寫入要求與資料 |
| `full` | output | FIFO 已滿 |
| `rd_en` | input | 讀取要求 |
| `rd_data` | output | 最近一次成功讀取的 registered data |
| `empty` | output | FIFO 為空 |
| `count` | output | 目前儲存筆數，範圍 0 到 `DEPTH` |

本題採下列簡單規則：

```text
do_write = wr_en && !full
do_read  = rd_en && !empty
```

- 對 full FIFO 寫入會被忽略。
- 對 empty FIFO 讀取會被忽略，`rd_data` 保持原值。
- 非 full、非 empty 時可同 cycle 讀寫；兩個 pointer 都前進，`count` 不變。
- 為了讓初學者先掌握邊界，本版本在「開始 cycle 時已 full」的情況不接受寫入，即使同 cycle 也要求讀取。

## pointer 為什麼要回捲

若 `DEPTH=4`，合法索引是 0、1、2、3。pointer 在 3 之後必須回到 0，而不是走到 4。解答以 `next_ptr` function 明確處理，因此即使 `DEPTH` 不是 2 的次方也能模擬正確。

pointer 相同無法單獨分辨 full 與 empty，所以還要用 `count`。`count==0` 是 empty，`count==DEPTH` 是 full。

## TODO 步驟

1. 在 `starter/sync_fifo.sv` 找出 memory、讀寫 pointer 與已提供的 `do_write` / `do_read` 邊界判斷。
2. 完成 pointer 回捲 function。
3. 寫入成功：寫 `mem[wr_ptr]` 並前進 write pointer。
4. 讀取成功：把 `mem[rd_ptr]` 放入 `rd_data` 並前進 read pointer。
5. 只有寫入時 `count+1`，只有讀取時 `count-1`，同時或都沒有時不變。
6. 在 starter TB 加入 full 拒寫、empty 拒讀、回捲與同 cycle 讀寫測試。

## 在 Vivado 看波形

加入 `starter/sync_fifo.sv` 與 `starter/tb_sync_fifo.sv`，把 TB 設為 Simulation Top，再跑 Behavioral Simulation。

先觀察 `wr_en`、`rd_en`、`full`、`empty`、`count`。若要看內部 pointer，可在 Scope 展開 `dut`，把 `wr_ptr`、`rd_ptr` 加進波形。記憶體陣列在不同 Vivado 版本的顯示方式可能不同，但驗證 FIFO 不必依賴直接觀看 `mem`。

請用 clock 上升緣為基準閱讀波形；不要在上升緣之前就期待 registered `rd_data` 改變。

## 常見錯誤

- full 時仍寫 memory，覆蓋尚未讀出的舊資料。
- empty 時仍讓 read pointer 前進。
- 同時讀寫時錯把 `count` 加一或減一。
- pointer 位寬用了 `$clog2(DEPTH)`，卻忘記非 2 次方深度時要手動回捲。
