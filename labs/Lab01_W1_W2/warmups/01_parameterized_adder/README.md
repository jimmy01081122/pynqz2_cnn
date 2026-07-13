# 暖身 1：參數化位寬加法器與 overflow

## 這題要學什麼

你會寫一個位寬可調整的組合邏輯加法器，並分清楚兩個常被混用的概念：

- `carry_out`：把輸入視為**無號數**時，最高位之外是否產生進位。
- `overflow`：把輸入視為二補數**有號數**時，真正結果是否超出 `WIDTH` 位可表示範圍。

例如 8 位元的 `8'h7f + 8'h01 = 8'h80` 沒有 `carry_out`，卻有 signed overflow，因為 `127 + 1` 無法用 8 位元 signed 數表示。相反地，`8'hff + 8'h01 = 8'h00` 有 `carry_out`，但 signed 觀點是 `-1 + 1 = 0`，沒有 overflow。

## DUT 介面

| 名稱 | 寬度 | 方向 | 說明 |
|---|---:|---|---|
| `a` | `WIDTH` | input | 第一個運算元 |
| `b` | `WIDTH` | input | 第二個運算元 |
| `sum` | `WIDTH` | output | 截斷為 `WIDTH` 位的和 |
| `carry_out` | 1 | output | 無號加法的最高位進位 |
| `overflow` | 1 | output | 二補數有號加法溢位 |

這是組合邏輯，沒有 clock。`a` 或 `b` 改變後，輸出會跟著更新。

## 推導 overflow

二補數加法只有兩種情況會溢位：

1. 兩個正數相加，結果符號位變成 1。
2. 兩個負數相加，結果符號位變成 0。

可寫成：

```text
overflow = (a 與 b 同號) 且 (sum 與 a 不同號)
```

SystemVerilog 中的符號位索引為 `WIDTH-1`。

## TODO 步驟

1. 打開 `starter/parameterized_adder.sv`，先讀懂已提供的延伸一位加法。
2. 由延伸結果拆出 `carry_out` 與 `sum`。
3. 用三個符號位完成 `overflow`。
4. 打開 `starter/tb_parameterized_adder.sv`，補上至少四類測試：一般加法、無號進位、正溢位、負溢位。
5. 完成檢查後，把 testbench 的 `tb_todos_done` 改成 `1'b1`。

## Vivado 第一次模擬

依上一層 README 的共同流程建立 RTL Project。加入這兩個檔案：

- Design Sources：`starter/parameterized_adder.sv`
- Simulation Sources：`starter/tb_parameterized_adder.sv`

啟動 Behavioral Simulation 後，在 Tcl Console 看到 `[TODO]` 代表骨架可正常執行；它不是工具安裝錯誤。完成所有 TODO 後應看到 `[PASS]`。

波形中可把 `a`、`b`、`sum` 的 Radix 設成 **Hexadecimal**，也可設成 **Signed Decimal** 觀察有號數解讀差異。

## 驗收重點

- 修改 `WIDTH` 時不需改任何硬編碼位元索引。
- `8'hff + 8'h01`：`sum=0`、`carry_out=1`、`overflow=0`。
- `8'h7f + 8'h01`：`sum=8'h80`、`carry_out=0`、`overflow=1`。
- `8'h80 + 8'hff`：`sum=8'h7f`、`carry_out=1`、`overflow=1`。
