# Translation Middleware 功能成熟度清查

> 评估日期：2026-05-30（初版） · **更新：2026-05-30（P0/P1 落地后）**
> 对照基准：代码库现状 + `docs/superpowers/specs/2026-05-29-translation-middleware-design.md`

**总体定位**：本地单人工作台 MVP 已跑通，核心流水线稳定可用。P0/P1 硬化项（失败回收、输入护栏、产物下载、任务管理、健康检查、日志）**已基本完成**，适合作为**开发者向 GitHub 开源项目**发布；P2/P3 体验与规模化能力仍属 backlog。

---

## 一、当前能力概览

### 1.1 架构与运行模型（MVP，符合设计）

| 项 | 现状 |
|----|------|
| 无账号 / 多用户 | 设计 Non-Goals，前后端均无 auth |
| 无外部任务队列 | FastAPI `BackgroundTasks` + 进程内 `asyncio.run()` |
| SQLite 单机索引 | 无迁移（Alembic）、无分页/筛选 |
| 进度推送 | 前端 2s 轮询，无 WebSocket/SSE |
| 全局 ASR 后端 | `.env` 里 `TM_ASR_BACKEND`，Job 级不可切换 |

### 1.2 任务生命周期

| 项 | 现状 |
|----|------|
| 删除任务 | ✅ 含磁盘清理 |
| 取消运行中任务 | ✅ 标记 cancelled，runner 检查 |
| 失败重跑 | ✅ `POST /run` 重置后重跑 |
| 重命名 | ✅ `PATCH /api/jobs/{id}` |
| 分阶段重试 | ⚠️ 仅「重试翻译」 |
| 产物获取 | ✅ HTTP 下载 + open-folder |

### 1.3 核心流水线

- **7 阶段进度模型**：upload → download → track_mux → transcription → merge → translation → export
- **三种 ingest**：本地上传 / SRT / yt-dlp URL
- **转写 → 合并 → 批量翻译 → 导出**：happy path 可用
- **转写进度**：基于时长的**估算值**，非 ASR 真实回调
- **失败回收**：✅ `mark_job_failure` + runner/API 顶层 catch；running stage 精确标 FAILED

### 1.4 前端工作台

- 三栏布局：历史 | 配置 | 进度
- 表单配置 + 客户端校验；**默认值持久化**（`localStorage`）
- 中英 i18n
- ✅ **outputs 文件列表 + 浏览器下载**
- ✅ **error_summary + yt-dlp / WhisperKit 日志查看**
- ✅ 加载失败 vs 空列表区分；API `detail` 解析
- ❌ **无字幕预览**（设计文档有，UI 未实现）

### 1.5 测试

- 后端 **~129** 单元/集成测试（含失败路径：download / 转写 / 翻译 / 后台 task 安全网）
- 前端 9 个冒烟测试，无 E2E

---

## 二、仍是 MVP / 已知限制

这些对个人本地使用合理，公开 README 中应继续说明。

### 2.1 输入与安全

| 场景 | 现状 |
|------|------|
| 上传 | 扩展名 + `TM_MAX_UPLOAD_BYTES` 限制；**无 MIME 内容校验** |
| API | **完全开放**，无 auth / 速率限制（README 声明仅本机使用） |
| API Key | ✅ 不入 SQLite；运行时从 `.env` 或请求体（strip 后）解析 |
| `GET /api/settings` | 仍暴露 whisper 路径、WhisperKit workdir 等内部信息 |

### 2.2 媒体与 ASR

- **yt-dlp**：无下载进度写入 stage；失败靠 log + 启发式分类
- **音轨合成**：仅 ffmpeg `-c copy`，codec 不兼容时无重编码 fallback
- **WhisperKit**：每 job 冷启停 server；stderr 已写 `whisperkit.stderr`
- **whisper.cpp**：无 transcriber 端到端集成测试

### 2.3 产物与格式

- 无双语 SRT（双语仅 txt/md）
- 远程/Headless 环境无法「打开文件夹」（下载 API 可替代）

### 2.4 前端体验 backlog

- 无字幕 preview
- 进度条 a11y 不完整（缺 `role="progressbar"` 等）
- 历史无搜索/筛选；列表未展示 `created_at`

---

## 三、P0–P3 清单与完成状态

按投入产出比排序。文档仅定义 **P0–P3**（无 P4 档）。

### P0 — 必须先做

| # | 项 | 状态 | 说明 |
|---|-----|------|------|
| 1 | 任务失败回收 | ✅ | `backend/app/jobs/failure.py`，runner/API 顶层 catch |
| 2 | 错误反馈体系 | ✅ | `App.tsx` 加载失败区分；`api/errors.ts`；`role="alert"` |
| 3 | 输入护栏 | ⚠️ | `validation.py`：扩展名、大小、`config_json` → 400；无 MIME |
| 4 | 安全基线 | ⚠️ | README 本地使用声明；Key 不入库；无 auth（本地场景可接受） |
| 5 | 产物可见性 | ✅ | outputs 面板 + `GET .../outputs/{key}/download` |

### P1 — 开源推荐

| # | 项 | 状态 | 说明 |
|---|-----|------|------|
| 6 | 任务管理 | ✅ | 删除 / 取消 / 重跑 / 重命名 |
| 7 | 配置体验 | ✅ | `formDefaults.ts`；`.env` Key 已配置提示 |
| 8 | 日志与诊断 | ✅ | `error_summary`；yt-dlp / WhisperKit 日志 API + UI |
| 9 | 依赖健康检查 | ✅ | `backend/app/core/health.py` |
| 10 | 失败路径测试 | ✅ | `test_failure.py`，`test_runner_failures.py`（5 项） |

### P2 — 体验 polish

| # | 项 | 状态 |
|---|-----|------|
| 11 | 字幕预览 | ❌ |
| 12 | 真实进度（ASR / yt-dlp） | ⚠️ 翻译有 batch 进度 |
| 13 | 分阶段重试 | ⚠️ 仅重试翻译 |
| 14 | a11y | ⚠️ 部分 |
| 15 | 历史增强（搜索/筛选） | ⚠️ 有排序，无筛选 |

### P3 — 更大受众

| # | 项 | 状态 |
|---|-----|------|
| 16 | 任务队列（Celery/RQ 等） | ❌ |
| 17 | 翻译 batch 并行 | ❌ |
| 18 | 双语 SRT 导出 | ❌ |
| 19 | E2E + WhisperCpp 集成测试 | ❌ |
| 20 | Settings 管理页 | ❌ |

---

## 四、设计文档 vs 现状

| 设计文档承诺 | 现状 |
|-------------|------|
| whisper.cpp 本地转写 | ✅ 且扩展 MLX / faster-whisper / WhisperKit |
| 字幕 merge + 翻译 | ✅ |
| 阶段进度时间线 | ✅（进度为估算） |
| 字幕 preview | ❌ |
| 错误 summary + log access | ✅ |
| 调整后重试相关阶段 | ⚠️ 仅重试翻译 |
| 无 cancel / 无队列 | ⚠️ 已有 cancel，仍无队列 |
| 产出文件在 UI 链接 | ✅ |
| yt-dlp / 音轨合成 | ✅ MVP 深度 |

---

## 五、结论与建议路径

| 目标 | 建议 |
|------|------|
| **继续自用** | 当前版本足够；按需做 P2（字幕预览） |
| **GitHub 开源（开发者向）** | **可以发布**；README 强调 local-only、无认证；P2 可后置 |
| **公开产品 / 公网** | 需 P0–P3 中 auth、队列、限流等；当前未做 |

**一句话（2026-05-30 更新）**：核心流水线可用，P0/P1 硬化已完成；作为**本机开发者工具**开源发布条件已满足。后续价值主要在 P2 体验（字幕预览、真实进度）而非发布阻塞项。

---

## 六、关键文件索引

| 职责 | 路径 |
|------|------|
| 流水线编排 | `backend/app/jobs/runner.py` |
| 失败处理 | `backend/app/jobs/failure.py` |
| 输入校验 | `backend/app/jobs/validation.py` |
| Job 创建/路由 | `backend/app/jobs/service.py` |
| HTTP API | `backend/app/api/jobs.py` |
| 健康检查 | `backend/app/core/health.py` |
| 失败路径测试 | `backend/tests/test_runner_failures.py` |
| 前端工作台 | `frontend/src/components/JobWorkbench.tsx` |
| 前端主应用 | `frontend/src/App.tsx` |
| 表单持久化 | `frontend/src/formDefaults.ts` |
| 初版设计 | `docs/superpowers/specs/2026-05-29-translation-middleware-design.md` |
