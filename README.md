# 诗词答题自动化工具（Windows）

这是一个用于**模拟器/窗口内诗词答题**的自动化工具：截取题目区域 → OCR 识别题干与选项 → 调用 AI 选择答案 → 自动点击选项。

当前版本已实现 **fast_rec（固定 ROI + 仅识别 rec-only）**，可将 OCR 从秒级降到 **200–400ms**（视机器与模型而定），并支持失败回退到全流程 OCR。

---

## 功能
- **区域截图**：可框选识别区域（`capture_region`）。
- **OCR 识别**：默认全流程 OCR（det+rec），支持 fast_rec 模式提速。
- **AI 选答案**：通过 DeepSeek 接口返回 A/B/C/D。
- **自动点击**：按识别坐标点击选项。
- **日志与耗时统计**：每轮输出分段耗时（截图/OCR/解析/AI/DB/点击）。

---

## 目录结构（核心文件）
- `main.py`：GUI 与主流程（截图→OCR→解析→AI→点击）。
- `ocr_engine.py`：OCR 引擎（全流程 OCR + fast_rec）。
- `question_parser.py`：题目/选项解析（已支持不依赖前缀）。
- `screen_capture.py`：截图模块（mss）。
- `ai_client.py` / `ai_providers/deepseek.py`：AI 调用。
- `database.py`：SQLite 记录/统计（已修复锁等待导致卡顿问题）。
- `config.json`：运行配置。
- `log.txt`：运行日志输出（GUI 同步显示）。

---

## 环境要求
- Windows 10/11
- Python（建议 3.10+；以你本地环境为准）
- `venv/`：项目自带虚拟环境（已保留）

> 说明：即使你有 NVIDIA 显卡，**没有安装 GPU 版 Paddle 依赖时也会走 CPU**。fast_rec 默认会尝试 `gpu:0`，失败会自动回退 `cpu`。

---

## 快速开始

### 1) 配置 API Key
推荐使用 **方案A（本地私有配置）**：
- 复制 `config.example.json` 为 `config.local.json`
- 在 `config.local.json` 里填写：`ai_providers.deepseek.api_key`
- `config.local.json` 已被 `.gitignore` 忽略，不会上传到 GitHub

不使用方案A时，也可以直接编辑 `config.json`（但请确保不要把 key 提交到仓库）。

### 2) 运行
在项目目录运行：

```bash
python main.py
```

### 3) 框选识别区域
GUI 点击 **“设置区域”**，框住题目与 4 个选项所在区域。

---

## 配置说明（config.json）

### OCR（默认全流程）

```json
"ocr": {
  "language": "ch",
  "use_angle_cls": true,
  "use_gpu": false
}
```

- `use_angle_cls`：方向分类（一般更慢；若画面不旋转可关）。

### OCR 极速模式：fast_rec（推荐）
fast_rec 核心思路：**不跑检测(det)**，直接按固定布局裁剪 6 块 ROI（title/question/A/B/C/D），只跑识别(rec-only)，速度大幅提升。

开启：

```json
"ocr": {
  "fast_rec": {
    "enabled": true,
    "device": "gpu:0",
    "model_name": "PP-OCRv4_mobile_rec",
    "batch_size": 6,
    "min_score": 0.5,
    "rois": {
      "title":   { "x": 0.06, "y": 0.02, "w": 0.88, "h": 0.12 },
      "question":{ "x": 0.06, "y": 0.14, "w": 0.88, "h": 0.22 },
      "A":       { "x": 0.04, "y": 0.46, "w": 0.44, "h": 0.20 },
      "B":       { "x": 0.52, "y": 0.46, "w": 0.44, "h": 0.20 },
      "C":       { "x": 0.04, "y": 0.70, "w": 0.44, "h": 0.20 },
      "D":       { "x": 0.52, "y": 0.70, "w": 0.44, "h": 0.20 }
    }
  }
}
```

字段含义：
- `enabled`：是否开启 fast_rec。
- `device`：优先设备（`gpu:0` / `cpu`）。
- `model_name`：rec-only 模型，`*_mobile_rec` 更快，`*_server_rec` 更准但更慢。
- `min_score`：低分阈值。当前逻辑是 **只有文本明显无效才回退**，不会因为分数低但文本可用而回退。
- `rois`：ROI 相对坐标（0~1）。如果识别错字/漏字，优先微调 ROI，让裁剪更贴合气泡文本区域。

### 点击延迟（总耗时大头之一）

```json
"click": {
  "delay_before_click": 0.5,
  "delay_after_click": 1.0,
  "click_duration": 0.1,
  "offset_y": 20
}
```

如果你追求“整轮更快”，优先调小 `delay_before_click`/`delay_after_click`。

---

## 日志怎么看（性能与问题定位）
日志里会有：
- `耗时拆分: 截图..., OCR..., AI..., DB..., 点击...`：定位每轮瓶颈。
- fast_rec 开启后会有：
  - `fast_rec启用: model=..., device=..., total=..., rec=..., crop=...`
  - `fast_rec[title/question/A/B/C/D]: ... (score=...)`

常见情况：
- **看不到 fast_rec启用**：说明 `ocr.fast_rec.enabled` 没开，或者没读到正确的 `config.json`。
- **fast_rec回退**：日志会打印回退原因 + 每个 ROI 的 text/score，用于调 ROI 或模型。

---

## 常见问题（FAQ）

### 1) 明明有显卡，为什么还是 CPU？
需要 Python 环境具备 GPU 推理依赖（例如 paddle 的 GPU 版本 + CUDA/cuDNN）。否则 `gpu:0` 初始化会失败并自动回退 `cpu`。

### 2) fast_rec 很快但有错字怎么办？
优先做两件事：
- **微调 ROI**：尽量只裁到气泡文字本体，减少背景/边框干扰。
- **更换 rec-only 模型**：例如从 `PP-OCRv4_mobile_rec` 换成 `PP-OCRv5_server_rec`（更准但更慢）。

### 3) 数据库曾经卡 5 秒 / database is locked？
已在 `database.py` 修复：同事务写入统计，降低锁等待超时，并启用 WAL（尽量减少卡顿）。

---

## 备注
- `dist/`、`build/` 等打包产物已按需清理（如需重新打包参考 `打包说明.md`）。