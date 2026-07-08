# CaptionFlow

本地优先的视频转写与字幕翻译工作台。FastAPI 后端 + React/Vite 前端。macOS
默认使用 WhisperKit，任务状态与产物保存在本机应用支持目录。

> **安全说明**：本项目设计为**本机单人使用**。默认 API 无认证，请勿将服务暴露到公网或不可信局域网。Provider API Key 可通过应用设置保存到 macOS Keychain，也可使用 `.env`；不会写入任务数据库或 `settings.json`。功能成熟度详见 [`docs/maturity-audit.md`](docs/maturity-audit.md)。

## 功能概览

- **视频 / SRT 任务**：上传本地文件，或填写 URL 由 yt-dlp 拉取
- **音轨合成**：可选上传外部音轨，ffmpeg 流拷贝合成后再转写
- **WhisperKit-only 初版**：Apple Silicon / macOS App 初版只携带 WhisperKit runtime 与当前 CoreML 模型
- **字幕流水线**：转写 → 字幕合并 → 批量翻译 → 导出
- **输出格式**：按任务配置导出 SRT / TXT / MD / JSON；开启翻译时还可生成双语 TXT / MD
- **工作台 UI**：任务历史、实时进度、产物下载、打开输出目录、删除 / 取消 / 重命名、失败重跑、仅重试翻译、yt-dlp / WhisperKit 日志查看、表单配置持久化、依赖健康状态提示
- **首次启动与设置**：WhisperKit 运行时检查、Provider 连接测试、macOS Keychain API Key 存储

**当前限制**（详见 maturity audit）：无字幕预览；ASR 进度为时长估算；WhisperKit 每 job 冷启动 server；无双语 SRT 导出。

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

Job 产物默认目录：`~/Library/Application Support/CaptionFlow/Data/jobs/<job_id>/`
（可用 `TM_DATA_DIR` 覆盖）。

## 先决条件

| 组件 | 用途 |
|------|------|
| Conda + Python 3.11+ | 后端 |
| Node.js 18+ / npm | 前端 |
| ffmpeg / ffprobe | 转写抽音、音轨合成、yt-dlp 合并 |
| yt-dlp | URL 下载（可选） |
| OpenAI-compatible API | 翻译（可选） |

**ASR 后端选择**：

- **Apple Silicon Mac / macOS App 初版**：默认并推荐 `TM_ASR_BACKEND=whisperkit_server`
- **当前打包副本**：已移除 MLX / faster-whisper / whisper.cpp 的本地模型与源码资产，只保留 `runtime/whisperkit`
- **Legacy ASR**：代码层仍保留旧后端，若要开发可安装 `.[legacy-asr]` 并自行准备模型

## 快速开始

### 0. 获取代码

```bash
git clone https://github.com/StoneLzy/CaptionFlow.git
cd CaptionFlow
```

### 1. 后端环境

```bash
conda create -n captionflow python=3.11
conda activate captionflow
python -m pip install -e ".[dev]"
```

### 2. 配置 `.env`

仓库根目录创建 `.env`（已 gitignore）。Apple Silicon 最小示例：

```bash
# 开发时可继续把数据放在仓库内；不配置时使用 macOS 应用支持目录
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

完整变量见下方 [环境变量](#环境变量)。

### 3. 启动服务

**后端**（仓库根目录）：

```bash
conda activate captionflow
python -m uvicorn app.main:app --reload --app-dir backend
```

**健康检查**：

```bash
curl http://127.0.0.1:8000/api/health
```

返回 `status: ok` 表示 ffmpeg 与当前 ASR 后端就绪；`degraded` 表示部分依赖未配置（服务仍可启动，但相关任务可能失败）。`checks` 字段包含 `ffmpeg`、`ffprobe`、`ytdlp`、`asr`、`translation_provider` 等探测结果。

**前端**（另开终端）：

```bash
cd frontend && npm install && npm run dev
```

打开 http://127.0.0.1:5173（API 代理到 `127.0.0.1:8000`）。

首次打开会显示应用设置：

- 确认 `argmax-cli` 与 WhisperKit 模型均为“已就绪”
- 可选填写翻译 Provider Base URL、模型与 API Key
- API Key 保存到 macOS Keychain；其他设置写入
  `~/Library/Application Support/CaptionFlow/settings.json`
- 只做本地转写时可以不配置翻译 Provider

## 环境变量

### 通用

| 变量 | 说明 | 默认 |
|------|------|------|
| `TM_DATA_DIR` | Job 文件目录 | `~/Library/Application Support/CaptionFlow/Data` |
| `TM_SQLITE_PATH` | SQLite 路径 | `~/Library/Application Support/CaptionFlow/app.db` |
| `TM_MODELS_DIR` | 应用管理的模型目录 | `~/Library/Application Support/CaptionFlow/Models` |
| `TM_LOGS_DIR` | 应用日志目录 | `~/Library/Logs/CaptionFlow` |
| `TM_SETTINGS_PATH` | 应用设置文件 | `~/Library/Application Support/CaptionFlow/settings.json` |

应用设置中保存的 Provider 与 WhisperKit 字段会覆盖对应 `.env` 值；
Keychain 中的 Provider API Key 优先于 `TM_PROVIDER_API_KEY`。

### ASR（按 backend 选用）

| 变量 | 说明 |
|------|------|
| `TM_ASR_BACKEND` | 初版固定使用 `whisperkit_server` |
| `TM_WHISPERKIT_EXECUTABLE_PATH` | `argmax-cli` 绝对路径；当前本地副本使用 `runtime/whisperkit/bin/argmax-cli` |
| `TM_WHISPERKIT_MODEL` | WhisperKit 模型名 |
| `TM_WHISPERKIT_MODEL_PATH` | 本地 CoreML 模型目录 |
| `TM_WHISPERKIT_HOST` | 绑定地址，默认 `127.0.0.1` |
| `TM_WHISPERKIT_*_TIMEOUT_SECONDS` | 启动 / 请求超时 |

字幕重建（词级 ASR 通用）：

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

### yt-dlp

| 变量 | 说明 | 默认 |
|------|------|------|
| `TM_YTDLP_EXECUTABLE` | 可执行文件 | `yt-dlp` |
| `TM_YTDLP_COOKIES_FILE` | Cookies 文件（登录站点） | 空 |
| `TM_MAX_UPLOAD_BYTES` | 单文件上传大小上限（字节） | `2147483648`（2GB） |

## ASR 后端说明

### WhisperKit server（Apple Silicon 默认）

当前打包副本只保留一个可运行 runtime；任务运行时不会临时从 HuggingFace 拉取模型：

```bash
runtime/whisperkit/bin/argmax-cli --help
```

```bash
TM_ASR_BACKEND=whisperkit_server
TM_WHISPERKIT_EXECUTABLE_PATH=/absolute/path/to/CaptionFlow/runtime/whisperkit/bin/argmax-cli
TM_WHISPERKIT_MODEL=large-v3-v20240930_626MB
TM_WHISPERKIT_MODEL_PATH=/absolute/path/to/CaptionFlow/runtime/whisperkit/Models/whisperkit-coreml/openai_whisper-large-v3-v20240930_626MB
```

macOS App 会携带已编译的 `argmax-cli`，模型由首次启动流程安装到应用模型目录。
每个视频 job 单独启动 server，结束后终止以释放内存。

### Legacy ASR（非初版打包路径）

MLX Whisper、faster-whisper、whisper.cpp 的代码适配仍保留，但当前 macOS
打包副本不携带它们的模型、源码 checkout 或默认依赖。若后续需要开发旧后端，
可安装：

```bash
python -m pip install -e ".[dev,legacy-asr]"
```

## API 示例

创建 job 后需调用 `POST /api/jobs/{id}/run` 才会开始处理（Web UI 会自动调用；curl 需手动执行）。失败或已完成的任务也可再次 `POST .../run` 重跑。

### 上传 SRT

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/srt \
  -F 'config_json={}' \
  -F 'file=@/path/to/sample.srt'

curl -X POST http://127.0.0.1:8000/api/jobs/{id}/run
```

### 上传视频

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/video \
  -F 'config_json={}' \
  -F 'file=@/path/to/sample.mp4'

curl -X POST http://127.0.0.1:8000/api/jobs/{id}/run
```

### 视频 + 外部音轨（音轨合成）

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/video \
  -F 'config_json={"track_mux_settings":{"enabled":true,"transcribe_from":"external_audio"}}' \
  -F 'file=@/path/to/video_only.mp4' \
  -F 'audio_file=@/path/to/external_audio.m4a'
```

`transcribe_from`：`external_audio`（默认）或 `muxed`。

### URL 下载（yt-dlp）

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/video-from-url \
  -F 'config_json={"media_source":"ytdlp","ytdlp_settings":{"url":"https://www.youtube.com/watch?v=EXAMPLE","preset":"best_1080p"}}'

curl -X POST http://127.0.0.1:8000/api/jobs/{id}/run
```

预设使用 `bestvideo+bestaudio` 时，yt-dlp 会用 ffmpeg **自动合并**为 mp4，`track_mux` 阶段会跳过。需要登录的站点可配置 `TM_YTDLP_COOKIES_FILE`。**请仅下载你有权使用的内容。**

### 其他

```bash
curl http://127.0.0.1:8000/api/jobs                                    # 列表
curl http://127.0.0.1:8000/api/jobs/{id}                               # 详情
curl http://127.0.0.1:8000/api/settings                                # 当前 ASR/Provider 配置（不含 API Key）
curl -X PATCH http://127.0.0.1:8000/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"provider_base_url":"https://api.openai.com/v1","provider_model":"gpt-4.1-mini","onboarding_completed":true}'
curl -X POST http://127.0.0.1:8000/api/settings/provider/test \
  -H 'Content-Type: application/json' \
  -d '{"base_url":"https://api.openai.com/v1","model":"gpt-4.1-mini","api_key":""}'
curl -X PATCH http://127.0.0.1:8000/api/jobs/{id} \
  -H 'Content-Type: application/json' \
  -d '{"filename":"my-job-name"}'                                      # 重命名
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/run                   # 启动 / 重跑
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/translate             # 仅重试翻译
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/cancel                # 取消运行中任务
curl -X DELETE http://127.0.0.1:8000/api/jobs/{id}                     # 删除任务
curl -X POST http://127.0.0.1:8000/api/jobs/{id}/open-folder           # 打开产物目录（桌面环境）
curl http://127.0.0.1:8000/api/jobs/{id}/outputs/transcript_srt/download  # 下载产物
curl http://127.0.0.1:8000/api/jobs/{id}/logs/ytdlp                    # yt-dlp 日志
curl http://127.0.0.1:8000/api/jobs/{id}/logs/whisperkit               # WhisperKit stderr
```

### 输出格式

任务 `config_json` 中的 `output_formats` 控制写盘与 outputs 登记，例如：

```json
{"output_formats": ["srt", "txt"]}
```

可选：`srt`、`txt`、`md`、`json`。

- **转写产物**：`transcript_srt` / `transcript_txt` / `transcript_md` / `transcript_json`（按勾选格式）
- **翻译产物**：`translation_srt`（勾选 srt 且启用翻译）
- **双语产物**：勾选 `txt` 或 `md` 且启用翻译时，额外生成 `bilingual_txt` / `bilingual_md`（**无双语 SRT**）

开启合并/翻译时，内部仍可能生成 `transcript.srt` 供流水线使用，但不会出现在 outputs 中（若未勾选 SRT）。

## 开发与测试

```bash
conda activate captionflow
python -m pytest
python -m ruff check backend

cd frontend
npm test
npm run build
```

## 常见问题

### `No module named pytest` / `No module named fastapi`

未激活 Conda 环境，或 `uvicorn` 来自其他 Python。应使用：

```bash
conda activate captionflow
python -m uvicorn app.main:app --reload --app-dir backend
python -m pytest
```

若提示符含 `(.venv)`，说明终端仍在尝试激活已删除的 `.venv`：关闭所有终端 → `Cmd+Shift+P` → **Developer: Reload Window**，或 **Python: Select Interpreter** 选 `captionflow`。本项目 `.vscode/settings.json` 已禁用 venv 自动激活，新终端会直接进入 conda 环境。

### 前端无数据 / 健康检查 degraded

确认后端运行：`curl http://127.0.0.1:8000/api/health`

若 `status` 为 `degraded`，检查 `checks.asr.executable_configured`、
`checks.asr.model_configured` 与 `checks.ffmpeg`。开发环境可重新运行
`./scripts/setup_whisperkit.sh` 检查 `runtime/whisperkit` 布局。

### yt-dlp 下载失败

查看 `data/jobs/<job_id>/ytdlp.log` 或 API `GET .../logs/ytdlp`。常见原因：网络/代理、YouTube 需 cookies、format 不可用。更新 yt-dlp：`yt-dlp -U`。

### 数据位置

```text
~/Library/Application Support/CaptionFlow/app.db
~/Library/Application Support/CaptionFlow/Data/jobs/<job_id>/
~/Library/Application Support/CaptionFlow/Models/
~/Library/Logs/CaptionFlow/
```

开发时可继续通过 `.env` 把 `TM_DATA_DIR` 与 `TM_SQLITE_PATH` 指向仓库内
`data/`；该目录已 gitignore。
