# CaptionFlow

本地优先的视频转写与字幕翻译工作台。React/Vite 前端 + FastAPI 后端，macOS 初版以 **Tauri v2 桌面 App** 交付，默认 ASR 为 **WhisperKit**（Apple Silicon / CoreML）。

> **安全说明**：本项目设计为**本机单人使用**。默认 API 无认证、无限流，请勿将服务暴露到公网或不可信局域网。Provider API Key 可通过应用设置保存到 macOS Keychain，也可使用 `.env`；不会写入任务数据库或 `settings.json`。

## 目录

- [功能概览](#功能概览)
- [架构](#架构)
- [处理流水线](#处理流水线)
- [先决条件](#先决条件)
- [快速开始（Web 开发模式）](#快速开始web-开发模式)
- [macOS 桌面应用](#macos-桌面应用)
- [环境变量](#环境变量)
- [ASR 后端](#asr-后端)
- [API 速查](#api-速查)
- [输出格式与产物](#输出格式与产物)
- [开发与测试](#开发与测试)
- [常见问题](#常见问题)
- [已知限制](#已知限制)
- [相关文档](#相关文档)

## 功能概览

### 任务与媒体

- **三种入口**：本地上传视频、上传 SRT、yt-dlp URL 拉取
- **支持格式**：视频 `.mp4 .mkv .webm .mov .avi .m4v .ts .flv`；外部音轨 `.m4a .aac .mp3 .wav .flac .ogg .opus .wma`
- **音轨合成**：可选上传外部音轨，ffmpeg 流拷贝合成后再转写（`transcribe_from`: `external_audio` | `muxed`）
- **yt-dlp**：预设 `best` / `best_1080p` / `best_720p` / `custom`；支持全局或任务级 cookies

### 转写与字幕

- **WhisperKit-only 初版**：macOS App 只携带 WhisperKit runtime 与当前 CoreML 模型
- **源语言**：auto、zh、en、ja、ko、fr、de、es、ru
- **字幕合并**：可配置最小时长、最大字数、句末保护等
- **Legacy ASR**：代码层仍保留 MLX / faster-whisper / whisper.cpp，开发时可安装 `.[legacy-asr]` 并自备模型

### 翻译与导出

- **OpenAI-compatible** 批量翻译，支持自定义 **system_prompt** 与 **术语表**
- **目标语言**：简中（默认）、繁中、en、ja、fr、de
- **输出格式**：SRT / TXT / MD / JSON；开启翻译时还可生成双语 TXT / MD（**无双语 SRT**）
- 默认 `enable_translation: true`；仅转写时在 UI 关闭翻译，或创建任务时在 `config_json` 中设 `"enable_translation": false`

### 工作台 UI

- 三栏布局：任务历史、配置表单、进度时间线
- 任务管理：删除 / 取消 / 重命名、失败重跑、**仅重试翻译**
- 产物下载、打开输出目录、yt-dlp / WhisperKit 日志查看
- 表单默认值持久化、依赖健康状态提示、**中英 i18n**
- 首次启动与设置：WhisperKit 运行时检查、Provider 连接测试、macOS Keychain API Key 存储

## 架构

```text
┌─────────────────────────────────────────────────────────┐
│  macOS App (Tauri v2)                                   │
│  ┌──────────────┐    ┌──────────────────────────────┐  │
│  │ React / Vite │───▶│ FastAPI sidecar (PyInstaller) │  │
│  │   前端 SPA   │    │  BackgroundTasks + SQLite     │  │
│  └──────────────┘    └───────────┬──────────────────┘  │
│                                  │                      │
│                    WhisperKit argmax-cli (CoreML)       │
│                    ffmpeg / yt-dlp（系统或 PATH）        │
└─────────────────────────────────────────────────────────┘
```

Web 开发模式下前后端分离运行；桌面 App 由 Tauri 启动 sidecar 后端并注入 `backend_base_url`。

## 处理流水线

```mermaid
flowchart LR
  ingest[上传或 yt-dlp 下载]
  mux[音轨合成]
  asr[转写]
  merge[字幕合并]
  translate[翻译]
  export[导出]

  ingest --> mux
  mux --> asr
  asr --> merge
  merge --> translate
  translate --> export
```

各阶段会按任务类型自动 **skip**（例如本地上传跳过 download，yt-dlp 已合并 mp4 时跳过 track_mux）。

| 阶段 | 说明 |
|------|------|
| `upload` | 本地上传完成；URL 任务跳过 |
| `download` | yt-dlp 拉取；上传任务跳过 |
| `track_mux` | ffmpeg 流拷贝合成；未启用或 yt-dlp 已合并时跳过 |
| `transcription` | ASR 转写 |
| `merge` | 字幕行合并（可选） |
| `translation` | OpenAI-compatible 批量翻译（可选） |
| `export` | 登记最终 outputs |

Job 产物默认目录：`~/Library/Application Support/CaptionFlow/Data/jobs/<job_id>/`（可用 `TM_DATA_DIR` 覆盖）。

## 先决条件

| 组件 | 用途 |
|------|------|
| Conda + Python 3.11+ | 后端 |
| Node.js 18+ / npm | 前端 |
| ffmpeg / ffprobe | 转写抽音、音轨合成、yt-dlp 合并 |
| yt-dlp | URL 下载（可选） |
| OpenAI-compatible API | 翻译（可选） |
| Rust + Cargo | macOS 桌面构建（可选，见下方） |

**WhisperKit runtime**（`runtime/whisperkit/`，已 gitignore）需在克隆后自行准备，见 [快速开始](#快速开始web-开发模式) 第 1 步。

## 快速开始（Web 开发模式）

### 0. 获取代码

```bash
git clone https://github.com/StoneLzy/CaptionFlow.git
cd CaptionFlow
```

### 1. 准备 WhisperKit runtime

`runtime/` 不在 Git 中。将 `argmax-cli` 与 CoreML 模型复制到：

```text
runtime/whisperkit/bin/argmax-cli
runtime/whisperkit/Models/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB/
```

然后运行检查脚本，它会打印 `.env` 示例：

```bash
./scripts/setup_whisperkit.sh
```

### 2. 后端环境

```bash
conda create -n captionflow python=3.11
conda activate captionflow
python -m pip install -e ".[dev]"
```

### 3. 配置 `.env`

仓库根目录创建 `.env`（已 gitignore）。Apple Silicon 最小示例：

```bash
# 开发时可把数据放在仓库内；不配置时使用 macOS 应用支持目录
TM_DATA_DIR=data
TM_SQLITE_PATH=data/app.db

TM_ASR_BACKEND=whisperkit_server
TM_WHISPERKIT_EXECUTABLE_PATH=/absolute/path/to/CaptionFlow/runtime/whisperkit/bin/argmax-cli
TM_WHISPERKIT_MODEL=large-v3-v20240930_626MB
TM_WHISPERKIT_MODEL_PATH=/absolute/path/to/CaptionFlow/runtime/whisperkit/Models/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB

# 若启用翻译，配置 Provider（仅转写可在 UI 关闭翻译，并省略以下三行）
TM_PROVIDER_BASE_URL=https://api.openai.com/v1
TM_PROVIDER_API_KEY=your-api-key
TM_PROVIDER_MODEL=gpt-4.1-mini
```

完整变量见 [环境变量](#环境变量)。

### 4. 启动服务

**后端**（仓库根目录）：

```bash
conda activate captionflow
python -m uvicorn app.main:app --reload --app-dir backend
```

**健康检查**：

```bash
curl http://127.0.0.1:8000/api/health
```

返回 `status: ok` 表示 ffmpeg、ffprobe 与当前 ASR 后端就绪；`degraded` 表示部分依赖未配置（服务仍可启动，但相关任务可能失败）。`checks` 字段包含 `ffmpeg`、`ffprobe`、`ytdlp`、`asr`、`translation_provider` 等探测结果——其中 **yt-dlp 与翻译 Provider 不影响 `ok` 判定**。

**前端**（另开终端）：

```bash
cd frontend && npm install && npm run dev
```

打开 http://127.0.0.1:5173（API 代理到 `127.0.0.1:8000`）。

首次打开会显示应用设置：

- 确认 `argmax-cli` 与 WhisperKit 模型均为「已就绪」
- 可选填写翻译 Provider Base URL、模型与 API Key
- API Key 保存到 macOS Keychain；其他设置写入 `~/Library/Application Support/CaptionFlow/settings.json`
- 只做本地转写时可以不配置翻译 Provider

## macOS 桌面应用

CaptionFlow 的 macOS 初版以 Tauri App 交付：React 前端 + PyInstaller 打包的 FastAPI sidecar + 内置 WhisperKit runtime。

### 构建先决条件

除 [先决条件](#先决条件) 外，还需：

- **Rust / Cargo**（[rustup](https://rustup.rs/)）
- **Xcode Command Line Tools**
- 已准备好的 `runtime/whisperkit/`（打包时会 bundle 进 App）

### 本地开发与打包

```bash
npm install                      # 根目录（Tauri CLI）
cd frontend && npm install && cd ..

npm run tauri:dev                # sidecar 构建 + 前端 dev + Tauri 窗口
npm run tauri:build              # → release/CaptionFlow.app + .dmg
```

构建产物：

```text
release/CaptionFlow.app
release/CaptionFlow_0.1.0_aarch64.dmg
```

Sidecar 二进制输出至 `src-tauri/binaries/captionflow-backend-aarch64-apple-darwin`。PyInstaller `--onefile` 模式下首次启动 sidecar 可能需数秒解压。

当前为 **ad-hoc 签名**，未经 Apple notarization，公开分发前需配置 Developer ID。更多细节见 [`docs/macos-packaging.md`](docs/macos-packaging.md)。

## 环境变量

前缀 **`TM_`**，从仓库根目录 `.env` 读取。应用设置中保存的 Provider 与 WhisperKit 字段会覆盖对应 `.env` 值；Keychain 中的 Provider API Key 优先于 `TM_PROVIDER_API_KEY`。

### 通用路径

| 变量 | 说明 | 默认（macOS） |
|------|------|---------------|
| `TM_DATA_DIR` | Job 文件目录 | `~/Library/Application Support/CaptionFlow/Data` |
| `TM_SQLITE_PATH` | SQLite 路径 | `~/Library/Application Support/CaptionFlow/app.db` |
| `TM_MODELS_DIR` | 应用管理的模型目录 | `~/Library/Application Support/CaptionFlow/Models` |
| `TM_LOGS_DIR` | 应用日志目录 | `~/Library/Logs/CaptionFlow` |
| `TM_SETTINGS_PATH` | 应用设置文件 | `~/Library/Application Support/CaptionFlow/settings.json` |

### WhisperKit（默认 ASR）

| 变量 | 说明 | 默认 |
|------|------|------|
| `TM_ASR_BACKEND` | ASR 后端 | `whisperkit_server` |
| `TM_WHISPERKIT_EXECUTABLE_PATH` | `argmax-cli` 绝对路径 | — |
| `TM_WHISPERKIT_CLI_WORKDIR` | CLI 工作目录（可选） | 空 |
| `TM_WHISPERKIT_MODEL` | 模型名 | `large-v3-v20240930_626MB` |
| `TM_WHISPERKIT_MODEL_PATH` | 本地 CoreML 模型目录 | — |
| `TM_WHISPERKIT_HOST` | 绑定地址 | `127.0.0.1` |
| `TM_WHISPERKIT_STARTUP_TIMEOUT_SECONDS` | 启动超时 | `120` |
| `TM_WHISPERKIT_REQUEST_TIMEOUT_SECONDS` | 请求超时 | `1800` |

字幕分段（词级 ASR 通用）：

| 变量 | 默认 |
|------|------|
| `TM_ASR_MAX_SUBTITLE_CHARS` | 42 |
| `TM_ASR_MAX_SUBTITLE_DURATION_MS` | 6000 |
| `TM_ASR_MIN_SUBTITLE_DURATION_MS` | 800 |
| `TM_ASR_MAX_WORD_GAP_MS` | 800 |

### 翻译

| 变量 | 说明 | 默认 |
|------|------|------|
| `TM_PROVIDER_BASE_URL` | Chat Completions 兼容地址 | — |
| `TM_PROVIDER_API_KEY` | API Key | — |
| `TM_PROVIDER_MODEL` | 模型名 | — |
| `TM_PROVIDER_TIMEOUT_SECONDS` | 单次请求超时 | 120 |
| `TM_PROVIDER_MAX_RETRIES` | 429/5xx 重试 | 2 |
| `TM_TRANSLATION_BATCH_SIZE` | 每批字幕条数 | 40 |
| `TM_TRANSLATION_CONTEXT_SEGMENTS` | 批间上下文条数 | 2 |

### yt-dlp 与上传

| 变量 | 说明 | 默认 |
|------|------|------|
| `TM_YTDLP_EXECUTABLE` | 可执行文件 | `yt-dlp` |
| `TM_YTDLP_COOKIES_FILE` | Cookies 文件（登录站点） | 空 |
| `TM_MAX_UPLOAD_BYTES` | 单文件上传大小上限（字节） | `2147483648`（2GB） |

### Sidecar（Tauri 打包，非 `TM_` 前缀）

| 变量 | 说明 | 默认 |
|------|------|------|
| `CAPTIONFLOW_BACKEND_HOST` | 绑定地址 | `127.0.0.1` |
| `CAPTIONFLOW_BACKEND_PORT` | 监听端口 | Tauri 动态分配 |
| `CAPTIONFLOW_BACKEND_LOG_LEVEL` | 日志级别 | `warning` |

## ASR 后端

### WhisperKit server（Apple Silicon 默认）

当前打包副本只保留一个可运行 runtime；任务运行时不会临时从 HuggingFace 拉取模型：

```bash
runtime/whisperkit/bin/argmax-cli --help
```

每个视频 job 单独启动 server，结束后终止以释放内存。macOS App 会携带已编译的 `argmax-cli` 与 CoreML 模型（bundle 内 `Contents/Resources/runtime/whisperkit`）。

### Legacy ASR（非初版打包路径）

MLX Whisper、faster-whisper、whisper.cpp 的代码适配仍保留，但当前 macOS 打包副本不携带它们的模型或默认依赖。开发旧后端时：

```bash
python -m pip install -e ".[dev,legacy-asr]"
```

相关变量：`TM_MLX_WHISPER_*`、`TM_FASTER_WHISPER_*`、`TM_WHISPER_*`（见 `backend/app/core/config.py`）。

## API 速查

创建 job 后需调用 `POST /api/jobs/{id}/run` 才会开始处理（Web UI 会自动调用）。失败或已完成的任务也可再次 `POST .../run` 重跑。

### 创建任务

**上传 SRT**

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/srt \
  -F 'config_json={}' \
  -F 'file=@/path/to/sample.srt'
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/run
```

**上传视频**

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/video \
  -F 'config_json={}' \
  -F 'file=@/path/to/sample.mp4'
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/run
```

**视频 + 外部音轨**

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/video \
  -F 'config_json={"track_mux_settings":{"enabled":true,"transcribe_from":"external_audio"}}' \
  -F 'file=@/path/to/video_only.mp4' \
  -F 'audio_file=@/path/to/external_audio.m4a'
```

**URL 下载（yt-dlp）**

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/video-from-url \
  -F 'config_json={"media_source":"ytdlp","ytdlp_settings":{"url":"https://www.youtube.com/watch?v=EXAMPLE","preset":"best_1080p"}}'
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/run
```

预设使用 `bestvideo+bestaudio` 时，yt-dlp 会用 ffmpeg **自动合并**为 mp4，`track_mux` 阶段会跳过。需要登录的站点可配置 `TM_YTDLP_COOKIES_FILE` 或任务级 `ytdlp_settings.cookies_file`。**请仅下载你有权使用的内容。**

### 任务管理与设置

```bash
curl http://127.0.0.1:8000/api/jobs                                    # 列表
curl http://127.0.0.1:8000/api/jobs/{id}                               # 详情
curl http://127.0.0.1:8000/api/settings                                # 当前配置（不含 API Key）
curl -X PATCH http://127.0.0.1:8000/api/jobs/{id} \
  -H 'Content-Type: application/json' \
  -d '{"filename":"my-job-name"}'                                      # 重命名
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/run                   # 启动 / 重跑
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/translate             # 仅重试翻译
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/cancel                # 取消
curl -X DELETE http://127.0.0.1:8000/api/jobs/{id}                     # 删除
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/open-folder           # 打开产物目录
curl http://127.0.0.1:8000/api/jobs/{id}/outputs/transcript_srt/download
curl http://127.0.0.1:8000/api/jobs/{id}/logs/ytdlp                    # yt-dlp 日志
curl http://127.0.0.1:8000/api/jobs/{id}/logs/whisperkit               # WhisperKit stderr
```

Provider 连接测试（`POST /api/settings/provider/test`）会对 `{base_url}/models` 发起 GET 请求。

## 输出格式与产物

任务 `config_json` 中的 `output_formats` 控制写盘与 outputs 登记，例如：

```json
{"output_formats": ["srt", "txt"], "enable_translation": false}
```

可选格式：`srt`、`txt`、`md`、`json`。

| 产物键 | 条件 |
|--------|------|
| `transcript_srt` / `transcript_txt` / `transcript_md` / `transcript_json` | 按勾选格式 |
| `merged_srt` | 启用字幕合并时 |
| `translation_srt` | 勾选 srt 且启用翻译 |
| `bilingual_txt` / `bilingual_md` | 勾选 txt/md 且启用翻译（**无双语 SRT**） |

开启合并/翻译时，内部仍可能生成 `transcript.srt` 供流水线使用，但不会出现在 outputs 中（若未勾选 SRT）。

## 开发与测试

```bash
conda activate captionflow
python -m pytest                 # backend/tests（~130+ 用例）
python -m ruff check backend

cd frontend
npm test                         # Vitest 冒烟测试
npm run build
```

WhisperKit 端到端 smoke（需 `data/smoke-whisperkit.wav`）：

```bash
./scripts/smoke_whisperkit.sh
```

## 常见问题

### `No module named pytest` / `No module named fastapi`

未激活 Conda 环境，或 `uvicorn` 来自其他 Python。应使用：

```bash
conda activate captionflow
python -m uvicorn app.main:app --reload --app-dir backend
python -m pytest
```

### 前端无数据 / 健康检查 degraded

确认后端运行：`curl http://127.0.0.1:8000/api/health`

若 `status` 为 `degraded`，检查 `checks.asr.executable_configured`、`checks.asr.model_configured` 与 `checks.ffmpeg`。开发环境可重新运行 `./scripts/setup_whisperkit.sh` 检查 `runtime/whisperkit` 布局。

### yt-dlp 下载失败

查看 `data/jobs/<job_id>/ytdlp.log` 或 API `GET .../logs/ytdlp`。常见原因：网络/代理、YouTube 需 cookies、format 不可用。更新 yt-dlp：`yt-dlp -U`。

### 数据位置

```text
~/Library/Application Support/CaptionFlow/app.db
~/Library/Application Support/CaptionFlow/Data/jobs/<job_id>/
~/Library/Application Support/CaptionFlow/Models/
~/Library/Logs/CaptionFlow/
```

开发时可继续通过 `.env` 把 `TM_DATA_DIR` 与 `TM_SQLITE_PATH` 指向仓库内 `data/`；该目录已 gitignore。

## 已知限制

适合个人本地使用，公开使用前请了解：

- **无字幕预览**；ASR 进度为时长估算，非真实回调
- **WhisperKit 每 job 冷启动 server**；无双语 SRT 导出
- 无账号/多用户、无外部任务队列；前端 2s 轮询，无 WebSocket
- API 完全开放；上传仅校验扩展名与大小，无 MIME 内容校验
- macOS App 为 ad-hoc 签名，未经 notarization

完整成熟度评估见 [`docs/maturity-audit.md`](docs/maturity-audit.md)。

## 相关文档

| 文档 | 内容 |
|------|------|
| [`docs/maturity-audit.md`](docs/maturity-audit.md) | 功能成熟度、已知限制与 backlog |
| [`docs/macos-packaging.md`](docs/macos-packaging.md) | Tauri 打包架构、sidecar、签名与产物 |

## License

仓库尚未包含 LICENSE 文件。使用前请自行确认授权范围；如需开源发布，建议补充许可证声明。
