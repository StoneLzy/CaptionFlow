import type { JobStatus, StageName, StageStatus } from "./types";

export type UiLanguage = "zh" | "en";

export interface Translations {
  appTitle: string;
  appSubtitle: string;
  settings: string;
  settingsTitle: string;
  settingsDescription: string;
  firstRun: string;
  firstRunDescription: string;
  closeSettings: string;
  settingsLoading: string;
  saveSettings: string;
  savingSettings: string;
  settingsSaved: string;
  settingsSaveError: string;
  whisperKitRuntime: string;
  whisperKitRuntimeHint: string;
  whisperKitExecutablePath: string;
  whisperKitModel: string;
  whisperKitModelPath: string;
  whisperKitSetupHint: string;
  runtimeReady: string;
  runtimeNotReady: string;
  providerOptionalHint: string;
  providerApiKeyStored: string;
  providerApiKeyPlaceholder: string;
  clearProviderApiKey: string;
  testProvider: string;
  testingProvider: string;
  providerConnectionOk: string;
  providerConnectionError: string;
  applicationData: string;
  applicationModels: string;
  applicationLogs: string;
  about: string;
  aboutTitle: string;
  aboutDescription: string;
  aboutFeatures: string[];
  aboutLocalOnly: string;
  aboutGithub: string;
  aboutReadme: string;
  aboutMaturityDoc: string;
  aboutVersion: string;
  closeAbout: string;
  languageZh: string;
  languageEn: string;
  historyTitle: string;
  historyCount: (count: number) => string;
  noJobs: string;
  newJob: string;
  newJobHint: string;
  jobNameLabel: string;
  jobNamePlaceholder: string;
  jobNameHint: string;
  outputDirectoryLabel: string;
  outputDirectoryPlaceholder: string;
  outputDirectoryHint: string;
  chooseOutputDirectory: string;
  clearOutputDirectory: string;
  fileLabel: string;
  fileHint: string;
  sourceLanguage: string;
  targetLanguage: string;
  outputFormats: string;
  transcriptionBackend: string;
  timestampSettings: string;
  timestampPrecision: string;
  dtwPreset: string;
  dtwAuto: string;
  pipeline: string;
  enableTranslation: string;
  pipelineHintVideo: string;
  pipelineHintSrt: string;
  subtitleMerge: string;
  enableSubtitleMerge: string;
  minimumDuration: string;
  maximumCharacters: string;
  maximumGap: string;
  protectSentenceEndings: string;
  provider: string;
  providerBaseUrl: string;
  providerApiKey: string;
  providerModel: string;
  systemPrompt: string;
  terminology: string;
  terminologyPlaceholder: string;
  chooseFileError: string;
  srtNeedsWorkError: string;
  mergeSettingsError: string;
  submitError: string;
  startJob: string;
  starting: string;
  selectedJob: string;
  status: string;
  openOutputFolder: string;
  openOutputFolderError: string;
  retryTranslation: string;
  retryTranslationHint: string;
  retryTranslationError: string;
  retryingTranslation: string;
  progress: string;
  noSelection: string;
  backendLabel: string;
  defaultModel: string;
  configuredModel: string;
  transcriptOnlyHint: string;
  basicSettings: string;
  processingFlow: string;
  providerSettings: string;
  promptAndTerminology: string;
  on: string;
  off: string;
  alwaysOn: string;
  skippedForSrt: string;
  waitingForFile: string;
  mergeHint: string;
  translationHint: string;
  outputHint: string;
  translationBatchDetail: (batch: number, total: number) => string;
  stageCount: (processed: number, total: number) => string;
  trackMux: string;
  trackMuxHint: string;
  audioFileLabel: string;
  audioFileHint: string;
  transcribeFrom: string;
  transcribeFromExternal: string;
  transcribeFromMuxed: string;
  useShortest: string;
  trackMuxNeedsAudioError: string;
  inputModeUpload: string;
  inputModeUrl: string;
  videoUrlLabel: string;
  videoUrlHint: string;
  videoUrlPlaceholder: string;
  ytdlpFormatPreset: string;
  ytdlpFormatBest: string;
  ytdlpFormat1080: string;
  ytdlpFormat720: string;
  ytdlpFormatCustom: string;
  ytdlpCustomFormat: string;
  ytdlpCustomFormatPlaceholder: string;
  ytdlpMergeHint: string;
  urlRequiredError: string;
  jobsLoadError: string;
  settingsLoadError: string;
  loadingJobs: string;
  outputsTitle: string;
  downloadOutput: string;
  viewLog: string;
  deleteJob: string;
  deleteJobError: string;
  renameJob: string;
  renameJobError: string;
  saveRename: string;
  cancelRename: string;
  renameJobPlaceholder: string;
  historyExpandHint: string;
  cancelJob: string;
  cancelJobError: string;
  rerunJob: string;
  rerunJobError: string;
  providerApiKeyConfigured: string;
  providerApiKeyMissing: string;
  backendDegraded: string;
  noLogAvailable: string;
  createdAt: string;
  stageLabels: Record<StageName, string>;
  stageStatusLabels: Record<StageStatus, string>;
  jobStatusLabels: Record<JobStatus, string>;
  sourceLanguageLabels: Record<string, string>;
  targetLanguageLabels: Record<string, string>;
  timestampPrecisionLabels: Record<string, string>;
  timestampPrecisionHints: Record<string, string>;
}

export const t: Record<UiLanguage, Translations> = {
  zh: {
    appTitle: "翻译工作台",
    appSubtitle: "本地转写、字幕合并与翻译",
    settings: "设置",
    settingsTitle: "应用设置",
    settingsDescription: "管理 WhisperKit 运行时和翻译服务配置。",
    firstRun: "首次启动",
    firstRunDescription:
      "先确认 WhisperKit 已就绪。翻译服务是可选项，只做本地转写时可以留空。",
    closeSettings: "关闭设置",
    settingsLoading: "正在加载设置…",
    saveSettings: "保存并继续",
    savingSettings: "保存中…",
    settingsSaved: "设置已保存。",
    settingsSaveError: "保存设置失败。",
    whisperKitRuntime: "WhisperKit 运行时",
    whisperKitRuntimeHint: "初版 macOS 应用固定使用 WhisperKit。",
    whisperKitExecutablePath: "argmax-cli 路径",
    whisperKitModel: "WhisperKit 模型",
    whisperKitModelPath: "模型目录",
    whisperKitSetupHint:
      "CLI 或模型尚未就绪。开发环境请运行 setup 脚本；打包版将在首次启动时安装资源。",
    runtimeReady: "已就绪",
    runtimeNotReady: "未就绪",
    providerOptionalHint: "可选。API Key 会存入 macOS Keychain，不写入设置文件。",
    providerApiKeyStored: "已安全存储；留空则保持不变",
    providerApiKeyPlaceholder: "输入 API Key",
    clearProviderApiKey: "清除已保存的 API Key",
    testProvider: "测试连接",
    testingProvider: "测试中…",
    providerConnectionOk: "Provider 连接成功。",
    providerConnectionError: "Provider 连接失败。",
    applicationData: "任务数据",
    applicationModels: "模型目录",
    applicationLogs: "日志目录",
    about: "关于",
    aboutTitle: "CaptionFlow",
    aboutDescription:
      "本地优先的视频转写与字幕翻译工作台。任务与产物保存在本机应用支持目录，适合个人在 Mac 上处理视频字幕。",
    aboutFeatures: [
      "上传视频 / SRT，或通过 yt-dlp 拉取在线视频",
      "macOS 初版以 WhisperKit 作为默认转写后端",
      "可选字幕合并与 OpenAI 兼容 API 批量翻译",
      "任务历史、进度跟踪、产物下载与日志查看",
    ],
    aboutLocalOnly:
      "本项目设计为本机单人使用，请勿将服务暴露到公网；Provider API Key 可安全存储在 macOS Keychain。",
    aboutGithub: "GitHub 仓库",
    aboutReadme: "README",
    aboutMaturityDoc: "功能成熟度说明",
    aboutVersion: "版本 0.1.0",
    closeAbout: "关闭",
    languageZh: "中文",
    languageEn: "EN",
    historyTitle: "历史",
    historyCount: (count) => `${count} 个任务`,
    noJobs: "暂无任务。",
    newJob: "新建任务",
    newJobHint: "视频或 SRT，一页完成配置。",
    jobNameLabel: "任务名称",
    jobNamePlaceholder: "可选，不填则自动命名",
    jobNameHint: "用于历史记录显示；不填时使用文件名、URL 或下载标题。",
    outputDirectoryLabel: "输出目录",
    outputDirectoryPlaceholder: "可选，不填则保存到默认 Job 目录",
    outputDirectoryHint: "最终字幕/TXT/MD/JSON 会复制到这里，中间文件仍保存在应用数据目录。",
    chooseOutputDirectory: "选择",
    clearOutputDirectory: "清空",
    fileLabel: "视频或 SRT 文件",
    fileHint: "选择视频进行转写，或选择 SRT 直接合并/翻译。",
    sourceLanguage: "源语言",
    targetLanguage: "目标语言",
    outputFormats: "输出格式",
    transcriptionBackend: "转写后端",
    timestampSettings: "转写时间戳",
    timestampPrecision: "时间戳精度",
    dtwPreset: "DTW 预设",
    dtwAuto: "根据模型文件名自动检测",
    pipeline: "流水线",
    enableTranslation: "启用翻译",
    pipelineHintVideo: "视频任务会先转写。关闭翻译时只导出转写稿。",
    pipelineHintSrt: "SRT 会跳过转写。请启用字幕合并或翻译。",
    subtitleMerge: "字幕合并",
    enableSubtitleMerge: "启用字幕合并",
    minimumDuration: "时长(ms)",
    maximumCharacters: "字符数",
    maximumGap: "间隔(ms)",
    protectSentenceEndings: "保护句末断点",
    provider: "Provider",
    providerBaseUrl: "Provider Base URL",
    providerApiKey: "Provider API Key",
    providerModel: "Provider 模型",
    systemPrompt: "系统提示词",
    terminology: "术语表",
    terminologyPlaceholder: "源短语 => 目标短语",
    chooseFileError: "请先选择视频或 SRT 文件。",
    srtNeedsWorkError: "SRT 文件需要启用字幕合并或翻译。",
    mergeSettingsError: "请填写有效的字幕合并参数。",
    submitError: "启动任务失败",
    startJob: "开始任务",
    starting: "启动中...",
    selectedJob: "当前任务",
    status: "状态",
    openOutputFolder: "打开输出文件夹",
    openOutputFolderError: "打开输出文件夹失败",
    retryTranslation: "重试翻译",
    retryTranslationHint: "跳过转写，仅重新合并/翻译已有字幕。",
    retryTranslationError: "重试翻译失败",
    retryingTranslation: "重试中...",
    progress: "实时进度",
    noSelection: "选择一个任务查看实时进度。",
    backendLabel: "ASR 后端",
    defaultModel: "默认模型",
    configuredModel: "已配置模型",
    transcriptOnlyHint: "只导出转写",
    basicSettings: "基础设置",
    processingFlow: "处理流程",
    providerSettings: "Provider 设置",
    promptAndTerminology: "提示词与术语",
    on: "开启",
    off: "关闭",
    alwaysOn: "始终开启",
    skippedForSrt: "SRT 跳过",
    waitingForFile: "等待选择文件",
    mergeHint: "合并过短或过碎的字幕行，让阅读节奏更稳定。",
    translationHint: "调用兼容 OpenAI 的模型，把字幕翻译为目标语言。",
    outputHint: "选择要导出的字幕和文本格式。",
    translationBatchDetail: (batch, total) => `翻译批次 ${batch}/${total}`,
    stageCount: (processed, total) => `${processed} / ${total} 条字幕`,
    trackMux: "音轨合成",
    trackMuxHint: "将外部音轨与视频流拷贝合成，再选择转写音源。",
    audioFileLabel: "外部音轨",
    audioFileHint: "可选：选择后将自动启用音轨合成。",
    transcribeFrom: "转写音源",
    transcribeFromExternal: "外部音轨",
    transcribeFromMuxed: "合成后视频",
    useShortest: "按较短流截断",
    trackMuxNeedsAudioError: "启用音轨合成时需要选择外部音轨文件。",
    inputModeUpload: "本地文件",
    inputModeUrl: "在线链接",
    videoUrlLabel: "视频链接",
    videoUrlHint: "粘贴 YouTube 等页面 URL，由 yt-dlp 下载。",
    videoUrlPlaceholder: "https://www.youtube.com/watch?v=...",
    ytdlpFormatPreset: "下载格式",
    ytdlpFormatBest: "最佳（自动合并）",
    ytdlpFormat1080: "1080p（自动合并）",
    ytdlpFormat720: "720p（自动合并）",
    ytdlpFormatCustom: "自定义 format",
    ytdlpCustomFormat: "自定义 format 表达式",
    ytdlpCustomFormatPlaceholder: "bestvideo*+bestaudio/best",
    ytdlpMergeHint: "yt-dlp 在下载分轨后会用 ffmpeg 自动合并为 mp4，音轨合成阶段将自动跳过。",
    urlRequiredError: "请先输入视频链接。",
    jobsLoadError: "无法加载任务列表，请确认后端已启动。",
    settingsLoadError: "无法加载服务端配置。",
    loadingJobs: "正在加载任务…",
    outputsTitle: "输出文件",
    downloadOutput: "下载",
    viewLog: "查看日志",
    deleteJob: "删除任务",
    deleteJobError: "删除任务失败。",
    renameJob: "重命名",
    renameJobError: "重命名失败。",
    saveRename: "保存",
    cancelRename: "取消",
    renameJobPlaceholder: "输入任务名称",
    historyExpandHint: "再次点击可收起/展开完整名称",
    cancelJob: "取消任务",
    cancelJobError: "取消任务失败。",
    rerunJob: "重新运行",
    rerunJobError: "重新运行失败。",
    providerApiKeyConfigured: "API Key 已在应用设置中安全存储。",
    providerApiKeyMissing: "请先在顶部“设置”中配置 Provider API Key。",
    backendDegraded: "部分依赖未就绪，任务可能会失败。",
    noLogAvailable: "暂无可用日志。",
    createdAt: "创建时间",
    stageLabels: {
      upload: "上传",
      download: "下载",
      track_mux: "音轨合成",
      transcription: "转写",
      merge: "字幕合并",
      translation: "翻译",
      export: "导出",
    },
    stageStatusLabels: {
      pending: "等待中",
      running: "进行中",
      completed: "已完成",
      failed: "失败",
      skipped: "已跳过",
    },
    jobStatusLabels: {
      created: "排队中",
      running: "运行中",
      completed: "已完成",
      failed: "失败",
      cancelled: "已取消",
    },
    sourceLanguageLabels: {
      auto: "自动检测",
      zh: "中文",
      en: "英文",
      ja: "日文",
      ko: "韩文",
      fr: "法文",
      de: "德文",
      es: "西班牙文",
      ru: "俄文",
    },
    targetLanguageLabels: {
      "zh-Hans": "简体中文",
      ja: "日文",
      en: "英文",
      "zh-Hant": "繁体中文",
      fr: "法文",
      de: "德文",
    },
    timestampPrecisionLabels: {
      standard: "标准 (~1s 分段)",
      word: "词级 (-ml 1 -sow)",
      word_dtw: "词级 + DTW",
    },
    timestampPrecisionHints: {
      standard: "默认 whisper.cpp 分段时间戳。",
      word: "按词切分，时间戳更细，字幕行会更多。",
      word_dtw: "用 DTW 微调词级时间戳，需要匹配的 DTW 预设。",
    },
  },
  en: {
    appTitle: "Translation Workbench",
    appSubtitle: "Local transcription, subtitle merge, and translation",
    settings: "Settings",
    settingsTitle: "Application settings",
    settingsDescription: "Manage the WhisperKit runtime and translation provider.",
    firstRun: "First launch",
    firstRunDescription:
      "Confirm that WhisperKit is ready. The translation provider is optional for local transcription.",
    closeSettings: "Close settings",
    settingsLoading: "Loading settings…",
    saveSettings: "Save and continue",
    savingSettings: "Saving…",
    settingsSaved: "Settings saved.",
    settingsSaveError: "Failed to save settings.",
    whisperKitRuntime: "WhisperKit runtime",
    whisperKitRuntimeHint: "The initial macOS release uses WhisperKit exclusively.",
    whisperKitExecutablePath: "argmax-cli path",
    whisperKitModel: "WhisperKit model",
    whisperKitModelPath: "Model directory",
    whisperKitSetupHint:
      "The CLI or model is unavailable. Run the setup script in development; the packaged app will install its runtime during first launch.",
    runtimeReady: "Ready",
    runtimeNotReady: "Not ready",
    providerOptionalHint:
      "Optional. The API key is stored in macOS Keychain, never in the settings file.",
    providerApiKeyStored: "Stored securely; leave blank to keep it",
    providerApiKeyPlaceholder: "Enter API key",
    clearProviderApiKey: "Remove the stored API key",
    testProvider: "Test connection",
    testingProvider: "Testing…",
    providerConnectionOk: "Provider connection succeeded.",
    providerConnectionError: "Provider connection failed.",
    applicationData: "Job data",
    applicationModels: "Models",
    applicationLogs: "Logs",
    about: "About",
    aboutTitle: "CaptionFlow",
    aboutDescription:
      "A local-first macOS app for video transcription and subtitle translation. Everything runs on your Mac—jobs, files, and outputs stay in your local app data.",
    aboutFeatures: [
      "Upload video or SRT, or fetch from a URL with yt-dlp",
      "Transcribe with WhisperKit on Apple Silicon",
      "Merge subtitles and translate with OpenAI-compatible APIs",
      "Track jobs, download outputs, and inspect logs",
    ],
    aboutLocalOnly:
      "For personal, local use only. Do not expose the API to the internet. Provider API keys can be stored in macOS Keychain.",
    aboutGithub: "GitHub repository",
    aboutReadme: "README",
    aboutMaturityDoc: "Maturity audit",
    aboutVersion: "Version 0.1.0",
    closeAbout: "Close",
    languageZh: "中文",
    languageEn: "EN",
    historyTitle: "History",
    historyCount: (count) => `${count} jobs`,
    noJobs: "No jobs yet.",
    newJob: "New job",
    newJobHint: "Configure video or SRT jobs in one place.",
    jobNameLabel: "Job name",
    jobNamePlaceholder: "Optional; auto-named if empty",
    jobNameHint: "Used in job history. Empty uses the file name, URL, or download title.",
    outputDirectoryLabel: "Output directory",
    outputDirectoryPlaceholder: "Optional; defaults to the job folder",
    outputDirectoryHint: "Final SRT/TXT/MD/JSON files are copied here; intermediate files stay in app data.",
    chooseOutputDirectory: "Choose",
    clearOutputDirectory: "Clear",
    fileLabel: "Video or SRT file",
    fileHint: "Choose a video for transcription, or an SRT for merge/translation.",
    sourceLanguage: "Source language",
    targetLanguage: "Target language",
    outputFormats: "Output formats",
    transcriptionBackend: "Transcription backend",
    timestampSettings: "Transcription timestamps",
    timestampPrecision: "Timestamp precision",
    dtwPreset: "DTW preset",
    dtwAuto: "Auto-detect from model filename",
    pipeline: "Pipeline",
    enableTranslation: "Enable translation",
    pipelineHintVideo: "Video uploads run transcription first. Disable translation for transcript only.",
    pipelineHintSrt: "SRT uploads skip transcription. Enable merge and/or translation.",
    subtitleMerge: "Subtitle merge",
    enableSubtitleMerge: "Enable subtitle merge",
    minimumDuration: "Minimum duration (ms)",
    maximumCharacters: "Maximum characters",
    maximumGap: "Maximum gap (ms)",
    protectSentenceEndings: "Protect sentence endings",
    provider: "Provider",
    providerBaseUrl: "Provider Base URL",
    providerApiKey: "Provider API key",
    providerModel: "Provider model",
    systemPrompt: "System prompt",
    terminology: "Terminology",
    terminologyPlaceholder: "source phrase => target phrase",
    chooseFileError: "Choose a video or SRT file first.",
    srtNeedsWorkError: "Enable subtitle merge and/or translation for SRT files.",
    mergeSettingsError: "Enter valid subtitle merge settings.",
    submitError: "Failed to start job",
    startJob: "Start job",
    starting: "Starting...",
    selectedJob: "Current job",
    status: "Status",
    openOutputFolder: "Open output folder",
    openOutputFolderError: "Failed to open output folder",
    retryTranslation: "Retry translation",
    retryTranslationHint: "Skip transcription and rerun merge/translation on existing subtitles.",
    retryTranslationError: "Failed to retry translation",
    retryingTranslation: "Retrying...",
    progress: "Live progress",
    noSelection: "Select a job to inspect live progress.",
    backendLabel: "ASR backend",
    defaultModel: "default model",
    configuredModel: "configured model",
    transcriptOnlyHint: "Transcript only",
    basicSettings: "Basic settings",
    processingFlow: "Processing flow",
    providerSettings: "Provider settings",
    promptAndTerminology: "Prompt and terminology",
    on: "On",
    off: "Off",
    alwaysOn: "Always on",
    skippedForSrt: "Skipped for SRT",
    waitingForFile: "Waiting for file",
    mergeHint: "Merge short or fragmented subtitle lines for steadier reading.",
    translationHint: "Call an OpenAI-compatible model to translate subtitles.",
    outputHint: "Choose subtitle and text artifacts to export.",
    translationBatchDetail: (batch, total) => `Translation batch ${batch}/${total}`,
    stageCount: (processed, total) => `${processed} / ${total} subtitles`,
    trackMux: "Track mux",
    trackMuxHint: "Copy-mux an external audio track into the video, then choose the transcription source.",
    audioFileLabel: "External audio",
    audioFileHint: "Optional: selecting a file auto-enables track mux.",
    transcribeFrom: "Transcribe from",
    transcribeFromExternal: "External audio",
    transcribeFromMuxed: "Muxed video",
    useShortest: "Trim to shortest stream",
    trackMuxNeedsAudioError: "Choose an external audio file when track mux is enabled.",
    inputModeUpload: "Local file",
    inputModeUrl: "Online URL",
    videoUrlLabel: "Video URL",
    videoUrlHint: "Paste a page URL for yt-dlp to download.",
    videoUrlPlaceholder: "https://www.youtube.com/watch?v=...",
    ytdlpFormatPreset: "Download format",
    ytdlpFormatBest: "Best (auto-merge)",
    ytdlpFormat1080: "1080p (auto-merge)",
    ytdlpFormat720: "720p (auto-merge)",
    ytdlpFormatCustom: "Custom format",
    ytdlpCustomFormat: "Custom format expression",
    ytdlpCustomFormatPlaceholder: "bestvideo*+bestaudio/best",
    ytdlpMergeHint: "yt-dlp merges separate streams with ffmpeg into mp4; track mux is skipped automatically.",
    urlRequiredError: "Enter a video URL first.",
    jobsLoadError: "Failed to load jobs. Check that the backend is running.",
    settingsLoadError: "Failed to load server settings.",
    loadingJobs: "Loading jobs…",
    outputsTitle: "Outputs",
    downloadOutput: "Download",
    viewLog: "View log",
    deleteJob: "Delete job",
    deleteJobError: "Failed to delete job.",
    renameJob: "Rename",
    renameJobError: "Failed to rename job.",
    saveRename: "Save",
    cancelRename: "Cancel",
    renameJobPlaceholder: "Enter a display name",
    historyExpandHint: "Click again to expand or collapse the full name",
    cancelJob: "Cancel job",
    cancelJobError: "Failed to cancel job.",
    rerunJob: "Run again",
    rerunJobError: "Failed to rerun job.",
    providerApiKeyConfigured: "The API key is stored securely in application settings.",
    providerApiKeyMissing: "Configure the Provider API key from Settings first.",
    backendDegraded: "Some dependencies are unavailable; jobs may fail.",
    noLogAvailable: "No log available.",
    createdAt: "Created",
    stageLabels: {
      upload: "Upload",
      download: "Download",
      track_mux: "Track mux",
      transcription: "Transcription",
      merge: "Subtitle merge",
      translation: "Translation",
      export: "Export",
    },
    stageStatusLabels: {
      pending: "Pending",
      running: "Running",
      completed: "Completed",
      failed: "Failed",
      skipped: "Skipped",
    },
    jobStatusLabels: {
      created: "Queued",
      running: "Running",
      completed: "Completed",
      failed: "Failed",
      cancelled: "Cancelled",
    },
    sourceLanguageLabels: {
      auto: "Auto detect",
      zh: "Chinese",
      en: "English",
      ja: "Japanese",
      ko: "Korean",
      fr: "French",
      de: "German",
      es: "Spanish",
      ru: "Russian",
    },
    targetLanguageLabels: {
      "zh-Hans": "Simplified Chinese",
      ja: "Japanese",
      en: "English",
      "zh-Hant": "Traditional Chinese",
      fr: "French",
      de: "German",
    },
    timestampPrecisionLabels: {
      standard: "Standard (~1s segments)",
      word: "Word-level (-ml 1 -sow)",
      word_dtw: "Word-level + DTW",
    },
    timestampPrecisionHints: {
      standard: "Default whisper.cpp segment timestamps.",
      word: "Split on words with sub-second timestamps. Slower, more subtitle lines.",
      word_dtw: "Word timestamps refined with DTW. Needs a matching DTW preset.",
    },
  },
};

export function readStoredLanguage(): UiLanguage {
  try {
    const value = window.localStorage?.getItem("tm_ui_language");
    return value === "en" || value === "zh" ? value : "zh";
  } catch {
    return "zh";
  }
}

export function storeLanguage(language: UiLanguage): void {
  try {
    window.localStorage?.setItem("tm_ui_language", language);
  } catch {
    return;
  }
}
