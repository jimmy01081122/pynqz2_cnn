# Lab01（W1–W2）：從零開始的 CIFAR-10 小型 CNN

本 Lab 是六天課程的第 1 天，對象是沒有 Vivado、PyTorch 或硬體加速器經驗的學生。這一天先在電腦上建立「可重現的軟體基準」，之後才會把相同的權重格式接到 RTL 與 Vivado。

> 重要：預設流程使用 synthetic（合成）影像，完全不會連線下載資料。合成資料只用來確認程式能跑，不能當作模型準確率成果。

## 你會完成什麼

1. 檢查 Python、PyTorch、torchvision 與 CUDA 環境。
2. 用 synthetic 模式跑一個極小的 smoke test。
3. 在已經準備好的 CIFAR-10 上訓練小型 CNN baseline。
4. 做 PTQ-ish 權重量化與 activation range 校正。
5. 對卷積層與全連接層做 2:4 結構化剪枝。
6. 把量化後權重打包為 Vivado/RTL 可讀的 memh 檔。

## 先理解四個名詞

- baseline：未剪枝、未量化的浮點模型，是後續比較基準。
- PTQ：訓練完成後量化。這裡的 PTQ-ish 會量化權重、記錄 activation scale，再以反量化權重做軟體準確率檢查；它不是 bit-accurate 的整數 RTL 模擬。
- INT8 / INT4：每個權重分別用 8 bit 或 4 bit 有號整數表示。
- 2:4 sparsity：每連續 4 個權重保留絕對值最大的 2 個，其餘設為 0。

## 0. 資料夾導覽

    Lab01_W1_W2/
    ├── README.md
    ├── requirements.txt
    ├── scripts/
    │   ├── check_env.py
    │   ├── train_baseline.py
    │   ├── quantize_ptq.py
    │   ├── prune_2to4.py
    │   ├── export_hex.py
    │   └── smoke_test.py
    ├── src/
    │   ├── data.py
    │   ├── tiny_cnn.py
    │   ├── quant_utils.py
    │   ├── prune_utils.py
    │   └── hex_utils.py
    └── board_demo/                 # optional：PYNQ-Z2 無 clock 加法器
        ├── rtl/、tb/、sim/
        └── constraints/pynq_z2_adder_demo.xdc

所有命令都從本 Lab 資料夾執行。

## 1. 建立 Python 環境

Windows PowerShell：

    py -3 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

Linux / macOS：

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

若課堂電腦不能上網，請由老師預先準備好 Python wheel 或已安裝 PyTorch 的環境；本 Lab 不會偷偷下載套件或資料集。

先檢查環境：

    python scripts/check_env.py

看到 torch 或 torchvision 為 MISSING 時，先安裝 requirements；看到 CUDA 不可用不是錯誤，CPU 仍可完成 Lab。

## 2. 完全離線 smoke test

不需要 PyTorch 的快速測試：

    python scripts/smoke_test.py

檢查訓練參數但不載入 PyTorch：

    python scripts/train_baseline.py --dry-run --smoke

有 PyTorch 後，跑兩個 mini-batch：

    python scripts/train_baseline.py --smoke --output artifacts/baseline_smoke.pt

此結果只證明資料流、模型與 checkpoint 正常，不能報告其準確率。

## 3. 訓練 baseline

### 3.1 使用 synthetic 資料熟悉流程

    python scripts/train_baseline.py --data-mode synthetic --epochs 2 --output artifacts/baseline_synthetic.pt

### 3.2 使用真正 CIFAR-10

程式預設 download=False。請把 CIFAR-10 事先放在 data/cifar-10-batches-py，然後執行：

    python scripts/train_baseline.py --data-mode cifar10 --data-root data --epochs 20 --output artifacts/baseline_cifar10.pt

只有在你確定允許連網時，才明確加上：

    python scripts/train_baseline.py --data-mode cifar10 --data-root data --download --epochs 20 --output artifacts/baseline_cifar10.pt

建議把 baseline 的 test_accuracy、seed、epoch 數與執行裝置記入實驗紀錄。

## 4. 2:4 剪枝

先用內建小陣列理解規則：

    python scripts/prune_2to4.py --demo

再處理 checkpoint：

    python scripts/prune_2to4.py artifacts/baseline_cifar10.pt --output artifacts/baseline_2to4.pt

每一列會先在尾端補 0 到 4 的倍數，再一起決定 2:4；因此即使第一層每列有 27 個權重，最後一組仍有合法的 4-bit mask。checkpoint 的 `pruning_masks` 會保存每組 **explicit mask nibble**，包含 padding lane。它記錄的是剪枝時「保留哪兩個位置」，不是由後續量化值是否為 0 反推。若不允許 padding，可加 `--strict`，讓列寬不是 4 的倍數時停止。

## 5. PTQ-ish 量化

INT8：

    python scripts/quantize_ptq.py artifacts/baseline_2to4.pt --bits 8 --output artifacts/model_int8_2to4.pt

INT4：

    python scripts/quantize_ptq.py artifacts/baseline_2to4.pt --bits 4 --output artifacts/model_int4_2to4.pt

若要用真實 CIFAR-10 校正 activation range：

    python scripts/quantize_ptq.py artifacts/baseline_2to4.pt --bits 8 --calibration-mode cifar10 --data-root data --output artifacts/model_int8_2to4.pt

這支工具會：

1. 對每個 Conv2d / Linear 權重做對稱 per-tensor 量化。
2. 以 calibration batch 記錄各層輸出的 max-abs 與 scale。
3. 把反量化權重載回浮點模型，檢查 accuracy drop。
4. 保存 integer tensor、scale、反量化 model_state 與校正資訊。

## 6. 匯出 RTL 可讀的十六進位權重

### 6.1 Dense 格式

    python scripts/export_hex.py artifacts/model_int8_2to4.pt --out-dir artifacts/hex_dense_int8

Dense 每行是一個 32-bit word；低索引權重放在較低位元。INT8 每行 4 個權重，INT4 每行 8 個權重，負數使用二補數。

### 6.2 Lab03／Lab04 相容的 2:4 compressed 格式

    python scripts/export_hex.py artifacts/model_int8_2to4.pt --sparse-2to4 --out-dir artifacts/hex_sparse_int8
    python scripts/export_hex.py artifacts/model_int4_2to4.pt --sparse-2to4 --out-dir artifacts/hex_sparse_int4

Sparse 模式固定為 32-bit combined word，並且只讀 checkpoint 裡的 `pruning_masks`，絕不使用 `qvalue != 0` 猜 mask。這很重要：被保留的浮點權重量化後可以剛好等於 0，但它仍占用 mask 指定的位置。

- INT8 一個 word 放一組：`[7:0]=value0`、`[15:8]=value1`、`[19:16]=mask`。例如 `mask=0101, values={1,2}` 是 `00050201`。
- INT4 一個 word 放兩組，布局與 Lab04 `cfg_weight_tdata` 完全相同。例如兩組 `{0101,{1,2}}`、`{1010,{-1,1}}` 是 `00A51F21`。
- INT4 每列若只有奇數組，第二組以 zero values 和合法 `mask=0011` 補齊；不使用會觸發硬體錯誤的 `mask=0000`。
- manifest.json 會記錄 row width、groups/word、words/row、value padding 與 group padding，載入 RTL 時以 manifest 為準。

快速查看兩種格式：

    python scripts/export_hex.py --demo --bits 4
    python scripts/export_hex.py --demo --bits 4 --sparse-2to4

### 6.3 Optional：先做一個 PYNQ-Z2 小 bitstream

若你想先熟悉 Vivado 的 Add Sources、Run Synthesis、Generate Bitstream，可做 `board_demo/` 的純組合 1-bit + 1-bit 加法器。它使用 SW0/SW1（M20/M19）與 LED0～3（R14/P14/N16/M14），沒有 clock，所以 XDC 刻意不包含 H16。完整真值表、模擬命令與 Vivado 點選步驟在 `board_demo/README.md`。

## 7. 建議的四組實驗

| 配置 | checkpoint 流程 | 目的 |
|---|---|---|
| Dense INT8 | baseline → quantize 8 | 精度較穩定的基準 |
| Dense INT4 | baseline → quantize 4 | 觀察低位元誤差 |
| INT8 2:4 | baseline → prune → quantize 8 | 觀察稀疏化收益 |
| INT4 2:4 | baseline → prune → quantize 4 | 資源最省、風險最高 |

不要直接覆蓋 baseline；每一步都使用新的輸出檔，才能追查差異。

## 8. 常見問題

### ModuleNotFoundError: torch

尚未安裝 requirements。先確認虛擬環境已啟用，再安裝套件。

### Dataset not found

這是刻意的離線保護。準備本機 CIFAR-10，或改用 --data-mode synthetic；只有明確允許時才使用 --download。

### synthetic accuracy 很低

正常。synthetic label 沒有真實影像語意，只用於 smoke test。

### 為何 PTQ 結果不是 RTL 的 bit-accurate 模擬

本 Lab 的目的，是先建立權重整數化、scale 與匯出格式。真正的 accumulator 位寬、飽和、rounding 與 activation quantization 必須在後續 RTL/TB 中逐項對齊。

## 9. Lab01 驗收

- scripts/smoke_test.py 顯示 PASS，包含 explicit retained-zero mask 與合法 padding assertions。
- baseline checkpoint 可被 prune 與 quantize 工具讀取，2:4 checkpoint 含 `pruning_masks`。
- 四組配置都有獨立 checkpoint 或明確的建立命令。
- sparse INT8 demo 為 `00050201`，sparse INT4 demo 為 `00A51F21`。
- 匯出的 manifest 與 memh 檔數量相符。
- optional board demo TB 檢查全部四種 SW 組合；XDC 不含不存在的 clock port。
- 報告清楚區分 synthetic smoke、軟體測量與 FPGA 實測。

