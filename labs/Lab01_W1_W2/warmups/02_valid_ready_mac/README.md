# 暖身 2：帶 valid/ready 的簡單 MAC

## 這題要學什麼

MAC 是 Multiply–Accumulate：每收到一組 `a`、`b`，便計算：

```text
acc_next = acc_old + a * b
```

這題還會加入硬體串流常見的 `valid/ready` 握手。資料**只在 clock 上升緣且 `valid && ready` 同時為 1 時傳送成功**。只有其中一個為 1，都不能把資料算進去。

## 本題定義的交易

輸入端：

- producer 放好 `a`、`b`，拉高 `in_valid`。
- MAC 有能力接收時拉高 `in_ready`。
- 上升緣的 `in_valid && in_ready` 為 1，這一筆 operand 才被接收。

輸出端：

- MAC 算出新的累加值後，以 `out_data` 搭配 `out_valid` 送出。
- consumer 以 `out_ready` 表示能接收。
- 若 `out_valid=1` 但 `out_ready=0`，MAC 必須保持 `out_valid` 與 `out_data` 不變，也不能覆蓋這筆尚未取走的結果。

本解答用一格 output register，因此：

```text
in_ready = !out_valid || out_ready
```

輸出格是空的，或舊輸出會在本 cycle 被取走時，才能接新輸入。這使 MAC 在 consumer 一直 ready 時可每 cycle 接一筆。

## DUT 介面

| 名稱 | 方向 | 說明 |
|---|---|---|
| `clk` | input | 單一上升緣時脈 |
| `rst_n` | input | 低有效、同步 reset；清除累加值與 `out_valid` |
| `in_valid`, `in_ready` | input/output | 輸入握手 |
| `a`, `b` | input | `DATA_WIDTH` 位二補數 signed operand |
| `out_valid`, `out_ready` | output/input | 輸出握手 |
| `out_data` | output | `ACC_WIDTH` 位二補數 signed 累加結果 |

預設 `DATA_WIDTH=8`、`ACC_WIDTH=24`。本題假設 `ACC_WIDTH >= 2*DATA_WIDTH`，讓單次乘積可完整放入 accumulator；長時間累加仍可能依二補數規則回捲。

## TODO 步驟

1. 在 `starter/valid_ready_mac.sv` 完成 `in_ready`。
2. 做出 signed 乘積與符號延伸。
3. reset 時清除 accumulator 與 `out_valid`。
4. 僅在 input handshake 時更新 accumulator 並產生新 output。
5. output handshake 且沒有新 input 時，清掉 `out_valid`。
6. 在 starter TB 補上負數、backpressure、連續輸入三類測試，再設定 `tb_todos_done=1`。

## 波形閱讀

在 Vivado Behavioral Simulation 加入所有介面訊號，將 `a`、`b`、`out_data` 的 Radix 設成 **Signed Decimal**。

特別觀察：

- `out_ready=0` 時，`out_valid`、`out_data` 是否連續數個 cycle 保持不變。
- `out_valid=1` 且 `out_ready=0` 時，`in_ready` 是否變成 0。
- `out_ready=1` 時，舊輸出被取走與新輸入被接收能否發生在同一上升緣。

若看到 starter 的 `[TODO]`，表示模擬器與 clock 正常，接下來才是要完成的設計。

## 常見錯誤

- 只看 `in_valid` 就累加，忘了同時檢查 `in_ready`。
- stalled 時仍改變 `out_data`。
- `a`、`b` 未宣告成 `signed`，負數乘法被當成大正數。
- 用 blocking assignment (`=`) 寫 sequential register；本題寄存器請用 nonblocking assignment (`<=`)。
