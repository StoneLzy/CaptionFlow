import { FormEvent, type ReactNode, useEffect, useState } from "react";
import {
  AudioLines,
  Captions,
  ChevronDown,
  FileVideo2,
  FolderOpen,
  HardDrive,
  Languages as LanguagesIcon,
  Link2,
  MessageSquareText,
  Play,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  UploadCloud,
  Workflow,
} from "lucide-react";

import {
  createSrtJob,
  createVideoFromUrlJob,
  createVideoJob,
  fetchSettings,
  runJob,
} from "../api/client";
import {
  DEFAULT_TARGET_LANGUAGE,
  SOURCE_LANGUAGES,
  TARGET_LANGUAGES,
} from "../constants/languages";
import {
  DEFAULT_WHISPER_TIMESTAMP_PRECISION,
  DTW_PRESET_OPTIONS,
  WHISPER_TIMESTAMP_PRECISIONS,
} from "../constants/whisper";
import { loadWorkbenchDefaults, saveWorkbenchDefaults } from "../formDefaults";
import type { Translations } from "../i18n";
import type { JobSummary } from "../types";
import { selectDirectory } from "../utils/selectDirectory";

interface Props {
  onJobCreated: (job: JobSummary) => void;
  onJobStarted: (job: JobSummary) => void;
  t: Translations;
}

interface JobConfig {
  job_name: string;
  output_directory: string;
  source_language: string;
  target_language: string;
  output_formats: string[];
  merge_settings: {
    enabled: boolean;
    min_duration_ms: number;
    max_chars: number;
    max_gap_ms: number;
    protect_sentence_endings: boolean;
  };
  enable_translation: boolean;
  whisper_settings: {
    timestamp_precision: string;
    dtw_preset: string;
  };
  system_prompt: string;
  terminology: { source: string; target: string }[];
  provider_settings: {
    base_url: string;
    api_key: string;
    model: string;
  };
  track_mux_settings: {
    enabled: boolean;
    transcribe_from: string;
    use_shortest: boolean;
  };
  media_source?: string;
  ytdlp_settings?: {
    url: string;
    preset: string;
    custom_format: string;
  };
}

const MERGE_DEFAULTS = {
  min_duration_ms: 1200,
  max_chars: 80,
  max_gap_ms: 800,
};

function normalizeDigitsInput(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (digits === "") {
    return "";
  }
  return String(Number(digits));
}

function parseMergeField(
  value: string,
  fallback: number,
  min: number,
): number | null {
  const trimmed = value.trim();
  if (trimmed === "") {
    return fallback;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < min) {
    return null;
  }
  return parsed;
}

function resolveMergeSettings(
  mergeEnabled: boolean,
  values: { minDurationMs: string; maxChars: string; maxGapMs: string },
): { values: { min_duration_ms: number; max_chars: number; max_gap_ms: number }; error: boolean } {
  const minDuration = parseMergeField(values.minDurationMs, MERGE_DEFAULTS.min_duration_ms, 0);
  const maxCharsValue = parseMergeField(values.maxChars, MERGE_DEFAULTS.max_chars, 1);
  const maxGap = parseMergeField(values.maxGapMs, MERGE_DEFAULTS.max_gap_ms, 0);
  if (mergeEnabled && (minDuration === null || maxCharsValue === null || maxGap === null)) {
    return { values: MERGE_DEFAULTS, error: true };
  }
  return {
    values: {
      min_duration_ms: minDuration ?? MERGE_DEFAULTS.min_duration_ms,
      max_chars: maxCharsValue ?? MERGE_DEFAULTS.max_chars,
      max_gap_ms: maxGap ?? MERGE_DEFAULTS.max_gap_ms,
    },
    error: false,
  };
}

function parseTerminology(text: string): { source: string; target: string }[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [source, target] = line.split("=>").map((part) => part.trim());
      return { source: source ?? "", target: target ?? "" };
    })
    .filter((entry) => entry.source && entry.target);
}

function isSrtFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".srt");
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function SwitchControl({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="switch-control">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="switch-track" aria-hidden="true">
        <span />
      </span>
      <span>{label}</span>
    </label>
  );
}

function OutputChip({
  checked,
  disabled = false,
  icon,
  label,
  onClick,
}: {
  checked: boolean;
  disabled?: boolean;
  icon?: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`output-chip${checked ? " selected" : ""}`}
      type="button"
      aria-pressed={checked}
      disabled={disabled}
      onClick={onClick}
    >
      {icon}
      {label}
    </button>
  );
}

export function JobWorkbench({ onJobCreated, onJobStarted, t }: Props) {
  const storedDefaults = loadWorkbenchDefaults();
  const [inputMode, setInputMode] = useState<"upload" | "url">(storedDefaults.inputMode ?? "upload");
  const [jobName, setJobName] = useState("");
  const [outputDirectory, setOutputDirectory] = useState(storedDefaults.outputDirectory ?? "");
  const [videoUrl, setVideoUrl] = useState("");
  const [ytdlpPreset, setYtdlpPreset] = useState(storedDefaults.ytdlpPreset ?? "best");
  const [ytdlpCustomFormat, setYtdlpCustomFormat] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [trackMuxEnabled, setTrackMuxEnabled] = useState(storedDefaults.trackMuxEnabled ?? false);
  const [transcribeFrom, setTranscribeFrom] = useState(storedDefaults.transcribeFrom ?? "external_audio");
  const [useShortest, setUseShortest] = useState(storedDefaults.useShortest ?? false);
  const [sourceLanguage, setSourceLanguage] = useState(storedDefaults.sourceLanguage ?? "auto");
  const [targetLanguage, setTargetLanguage] = useState(storedDefaults.targetLanguage ?? DEFAULT_TARGET_LANGUAGE);
  const [outputSrt, setOutputSrt] = useState(storedDefaults.outputSrt ?? true);
  const [outputTxt, setOutputTxt] = useState(storedDefaults.outputTxt ?? false);
  const [outputMd, setOutputMd] = useState(storedDefaults.outputMd ?? false);
  const [outputJson, setOutputJson] = useState(storedDefaults.outputJson ?? false);
  const [mergeEnabled, setMergeEnabled] = useState(storedDefaults.mergeEnabled ?? false);
  const [enableTranslation, setEnableTranslation] = useState(storedDefaults.enableTranslation ?? true);
  const [timestampPrecision, setTimestampPrecision] = useState(
    DEFAULT_WHISPER_TIMESTAMP_PRECISION,
  );
  const [dtwPreset, setDtwPreset] = useState("");
  const [minDurationMs, setMinDurationMs] = useState(
    storedDefaults.minDurationMs ?? String(MERGE_DEFAULTS.min_duration_ms),
  );
  const [maxChars, setMaxChars] = useState(storedDefaults.maxChars ?? String(MERGE_DEFAULTS.max_chars));
  const [maxGapMs, setMaxGapMs] = useState(storedDefaults.maxGapMs ?? String(MERGE_DEFAULTS.max_gap_ms));
  const [protectSentenceEndings, setProtectSentenceEndings] = useState(
    storedDefaults.protectSentenceEndings ?? true,
  );
  const [providerBaseUrl, setProviderBaseUrl] = useState(storedDefaults.providerBaseUrl ?? "");
  const [providerModel, setProviderModel] = useState(storedDefaults.providerModel ?? "");
  const [systemPrompt, setSystemPrompt] = useState(storedDefaults.systemPrompt ?? "");
  const [terminology, setTerminology] = useState(storedDefaults.terminology ?? "");
  const [asrBackend, setAsrBackend] = useState("");
  const [mlxWhisperModel, setMlxWhisperModel] = useState("");
  const [whisperKitModel, setWhisperKitModel] = useState("");
  const [providerApiKeyConfigured, setProviderApiKeyConfigured] = useState(false);
  const [settingsLoadError, setSettingsLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then((settings) => {
        setAsrBackend(settings.asr_backend);
        setMlxWhisperModel(settings.mlx_whisper_model);
        setWhisperKitModel(settings.whisperkit_model);
        setProviderBaseUrl((current) => current || settings.provider_base_url);
        setProviderModel((current) => current || settings.provider_model);
        setProviderApiKeyConfigured(settings.provider_api_key_configured);
        setTimestampPrecision(
          settings.whisper_timestamp_precision || DEFAULT_WHISPER_TIMESTAMP_PRECISION,
        );
        setDtwPreset(settings.whisper_dtw_preset || "");
        setSettingsLoadError(null);
      })
      .catch((settingsError) => {
        setSettingsLoadError(
          settingsError instanceof Error ? settingsError.message : t.settingsLoadError,
        );
      });
  }, [t.settingsLoadError]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inputMode === "url") {
      if (!videoUrl.trim()) {
        setError(t.urlRequiredError);
        return;
      }
    } else if (!file) {
      setError(t.chooseFileError);
      return;
    }
    if (inputMode === "upload" && file && isSrtFile(file) && !mergeEnabled && !enableTranslation) {
      setError(t.srtNeedsWorkError);
      return;
    }
    if (inputMode === "upload" && file && !isSrtFile(file) && trackMuxEnabled && !audioFile) {
      setError(t.trackMuxNeedsAudioError);
      return;
    }
    if (inputMode === "url" && ytdlpPreset === "custom" && !ytdlpCustomFormat.trim()) {
      setError(t.ytdlpCustomFormat);
      return;
    }
    if (![outputSrt, outputTxt, outputMd, outputJson].some(Boolean)) {
      setError(t.outputFormatRequiredError);
      return;
    }

    const mergeSettings = resolveMergeSettings(mergeEnabled, {
      minDurationMs,
      maxChars,
      maxGapMs,
    });
    if (mergeSettings.error) {
      setError(t.mergeSettingsError);
      return;
    }

    const outputFormats = [
      outputSrt ? "srt" : null,
      outputTxt ? "txt" : null,
      outputMd ? "md" : null,
      outputJson ? "json" : null,
    ].filter((format): format is string => format !== null);

    const config: JobConfig = {
      job_name: jobName.trim(),
      output_directory: outputDirectory.trim(),
      source_language: sourceLanguage,
      target_language: targetLanguage,
      output_formats: outputFormats,
      merge_settings: {
        enabled: mergeEnabled,
        min_duration_ms: mergeSettings.values.min_duration_ms,
        max_chars: mergeSettings.values.max_chars,
        max_gap_ms: mergeSettings.values.max_gap_ms,
        protect_sentence_endings: protectSentenceEndings,
      },
      enable_translation: enableTranslation,
      whisper_settings: {
        timestamp_precision: timestampPrecision,
        dtw_preset: dtwPreset,
      },
      system_prompt: systemPrompt,
      terminology: parseTerminology(terminology),
      provider_settings: {
        base_url: providerBaseUrl,
        api_key: "",
        model: providerModel,
      },
      track_mux_settings:
        inputMode === "url"
          ? {
              enabled: false,
              transcribe_from: "muxed",
              use_shortest: false,
            }
          : {
              enabled: trackMuxEnabled,
              transcribe_from: transcribeFrom,
              use_shortest: useShortest,
            },
      media_source: inputMode === "url" ? "ytdlp" : "upload",
      ...(inputMode === "url"
        ? {
            ytdlp_settings: {
              url: videoUrl.trim(),
              preset: ytdlpPreset,
              custom_format: ytdlpPreset === "custom" ? ytdlpCustomFormat.trim() : "",
            },
          }
        : {}),
    };

    const formData = new FormData();
    formData.append("config_json", JSON.stringify(config));
    if (inputMode === "upload" && file) {
      formData.append("file", file);
      if (!isSrtFile(file) && trackMuxEnabled && audioFile) {
        formData.append("audio_file", audioFile);
      }
    }

    setSubmitting(true);
    setError(null);
    try {
      const created =
        inputMode === "url"
          ? await createVideoFromUrlJob(formData)
          : file && isSrtFile(file)
            ? await createSrtJob(formData)
            : await createVideoJob(formData);
      onJobCreated(created);
      const started = await runJob(created.id);
      onJobStarted(started);
      saveWorkbenchDefaults({
        inputMode,
        outputDirectory,
        sourceLanguage,
        targetLanguage,
        outputSrt,
        outputTxt,
        outputMd,
        outputJson,
        mergeEnabled,
        enableTranslation,
        minDurationMs,
        maxChars,
        maxGapMs,
        protectSentenceEndings,
        providerBaseUrl,
        providerModel,
        systemPrompt,
        terminology,
        trackMuxEnabled,
        transcribeFrom,
        useShortest,
        ytdlpPreset,
      });
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : t.submitError;
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleSourceFile(nextFile: File | null) {
    setAudioFile(null);
    setTrackMuxEnabled(false);
    setUseShortest(false);
    setFile(nextFile);
    setError(null);
  }

  const isSrt = inputMode === "upload" && file ? isSrtFile(file) : false;
  const selectedOutputCount = [outputSrt, outputTxt, outputMd, outputJson].filter(Boolean).length;
  const canSubmit =
    (inputMode === "url" ? videoUrl.trim().length > 0 : file !== null) && selectedOutputCount > 0;
  const backendText =
    asrBackend === "mlx_whisper"
      ? `MLX Whisper: ${mlxWhisperModel || t.defaultModel}`
      : asrBackend === "whisperkit_server"
        ? `WhisperKit: ${whisperKitModel || t.configuredModel}`
        : asrBackend === "whisper_cpp"
          ? "whisper.cpp"
          : asrBackend
            ? `${t.backendLabel}: ${asrBackend}`
            : t.waitingForFile;

  return (
    <form className="workbench" onSubmit={handleSubmit}>
      <header className="create-view-heading">
        <p className="workspace-kicker">
          <Sparkles size={14} aria-hidden="true" />
          CAPTION STUDIO
        </p>
        <h2>{t.newJob}</h2>
        <p>{t.newJobHint}</p>
      </header>

      <section className="task-strip">
        <header className="task-card-heading">
          <span className="section-icon source-icon"><FileVideo2 size={19} aria-hidden="true" /></span>
          <div>
            <p className="section-step">STEP 01</p>
            <h3>{t.fileLabel}</h3>
          </div>
        </header>

        <div className="input-mode-tabs" aria-label="Input mode">
          <OutputChip
            checked={inputMode === "upload"}
            icon={<UploadCloud size={16} aria-hidden="true" />}
            label={t.inputModeUpload}
            onClick={() => {
              setInputMode("upload");
              setError(null);
            }}
          />
          <OutputChip
            checked={inputMode === "url"}
            icon={<Link2 size={16} aria-hidden="true" />}
            label={t.inputModeUrl}
            onClick={() => {
              setInputMode("url");
              setFile(null);
              setAudioFile(null);
              setTrackMuxEnabled(false);
              setError(null);
            }}
          />
        </div>

        <div className="source-grid">
          <div className="source-primary">
            {inputMode === "upload" ? (
              <label
                className={`file-drop primary-drop${dragActive ? " drag-active" : ""}${file ? " has-file" : ""}`}
                onDragEnter={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                    setDragActive(false);
                  }
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragActive(false);
                  handleSourceFile(event.dataTransfer.files?.[0] ?? null);
                }}
              >
                <span className="file-drop-icon" aria-hidden="true">
                  {file ? <FileVideo2 size={28} /> : <UploadCloud size={29} />}
                </span>
                <span className="file-drop-copy">
                  <strong>{file ? file.name : t.fileHint}</strong>
                  <small>
                    {file
                      ? `${isSrtFile(file) ? "SRT" : "VIDEO"} · ${formatFileSize(file.size)}`
                      : t.fileLabel}
                  </small>
                </span>
                <span className="browse-pill">{t.inputModeUpload}</span>
                <input
                  aria-label={t.fileLabel}
                  type="file"
                  accept="video/*,.srt"
                  onChange={(event) => handleSourceFile(event.target.files?.[0] ?? null)}
                />
              </label>
            ) : (
              <label className="source-url-card">
                <span className="file-drop-icon" aria-hidden="true"><Link2 size={25} /></span>
                <span className="source-url-copy">
                  <strong>{t.videoUrlLabel}</strong>
                  <small>{t.videoUrlHint}</small>
                </span>
                <input
                  aria-label={t.videoUrlLabel}
                  type="url"
                  value={videoUrl}
                  placeholder={t.videoUrlPlaceholder}
                  onChange={(event) => setVideoUrl(event.target.value)}
                />
              </label>
            )}
          </div>

          <div className="source-fields">
            <label>
              <span className="field-label-with-icon">{t.jobNameLabel}</span>
              <input
                aria-label={t.jobNameLabel}
                type="text"
                value={jobName}
                placeholder={t.jobNamePlaceholder}
                onChange={(event) => setJobName(event.target.value)}
              />
              <p className="field-hint">{t.jobNameHint}</p>
            </label>

            <div className="field-group">
              <label className="field-label-with-icon" htmlFor="job-output-directory">
                <HardDrive size={14} aria-hidden="true" />{t.outputDirectoryLabel}
              </label>
              <div className="path-picker-row">
                <input
                  id="job-output-directory"
                  aria-label={t.outputDirectoryLabel}
                  type="text"
                  value={outputDirectory}
                  placeholder={t.outputDirectoryPlaceholder}
                  onChange={(event) => setOutputDirectory(event.target.value)}
                />
                <button
                  type="button"
                  className="icon-button path-picker-button"
                  aria-label={t.chooseOutputDirectory}
                  title={t.chooseOutputDirectory}
                  onClick={async () => {
                    const selected = await selectDirectory(outputDirectory);
                    if (selected) {
                      setOutputDirectory(selected);
                    }
                  }}
                >
                  <FolderOpen size={16} aria-hidden="true" />
                </button>
                {outputDirectory ? (
                  <button type="button" className="ghost-button compact" onClick={() => setOutputDirectory("")}>
                    {t.clearOutputDirectory}
                  </button>
                ) : null}
              </div>
            </div>

            {inputMode === "upload" && file && !isSrt ? (
              <label className={`file-drop audio-drop${trackMuxEnabled ? " selected" : ""}`}>
                <span className="file-drop-icon" aria-hidden="true"><AudioLines size={18} /></span>
                <span className="file-drop-copy">
                  <strong>{audioFile ? audioFile.name : t.audioFileLabel}</strong>
                  <small>{audioFile ? formatFileSize(audioFile.size) : t.audioFileHint}</small>
                </span>
                <input
                  aria-label={t.audioFileLabel}
                  type="file"
                  accept="audio/*,.m4a,.aac,.mp3,.wav,.flac"
                  onChange={(event) => {
                    const nextAudio = event.target.files?.[0] ?? null;
                    setAudioFile(nextAudio);
                    if (nextAudio) {
                      setTrackMuxEnabled(true);
                    }
                  }}
                />
              </label>
            ) : null}

            {inputMode === "url" ? (
              <div className="url-options-row">
                <label>
                  {t.ytdlpFormatPreset}
                  <select aria-label={t.ytdlpFormatPreset} value={ytdlpPreset} onChange={(event) => setYtdlpPreset(event.target.value)}>
                    <option value="best">{t.ytdlpFormatBest}</option>
                    <option value="best_1080p">{t.ytdlpFormat1080}</option>
                    <option value="best_720p">{t.ytdlpFormat720}</option>
                    <option value="custom">{t.ytdlpFormatCustom}</option>
                  </select>
                </label>
                {ytdlpPreset === "custom" ? (
                  <label>
                    {t.ytdlpCustomFormat}
                    <input aria-label={t.ytdlpCustomFormat} type="text" value={ytdlpCustomFormat} placeholder={t.ytdlpCustomFormatPlaceholder} onChange={(event) => setYtdlpCustomFormat(event.target.value)} />
                  </label>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <section className="config-section essentials-section">
        <header className="section-heading-new">
          <span className="section-icon"><LanguagesIcon size={18} aria-hidden="true" /></span>
          <div>
            <p className="section-step">STEP 02</p>
            <h3>{t.basicSettings}</h3>
          </div>
        </header>
        {settingsLoadError ? (
          <p className="form-error" role="alert">
            {settingsLoadError}
          </p>
        ) : null}
        <div className="basic-grid">
          <label>
            {t.sourceLanguage}
            <select
              aria-label={t.sourceLanguage}
              value={sourceLanguage}
              onChange={(event) => setSourceLanguage(event.target.value)}
            >
              {SOURCE_LANGUAGES.map((language) => (
                <option key={language.value} value={language.value}>
                  {t.sourceLanguageLabels[language.value] ?? language.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t.targetLanguage}
            <select
              aria-label={t.targetLanguage}
              value={targetLanguage}
              onChange={(event) => setTargetLanguage(event.target.value)}
            >
              {TARGET_LANGUAGES.map((language) => (
                <option key={language.value} value={language.value}>
                  {t.targetLanguageLabels[language.value] ?? language.label}
                </option>
              ))}
            </select>
          </label>
          <div className="output-control">
            <span className="field-label">{t.outputFormats}</span>
            <div className="chip-row">
              <OutputChip checked={outputSrt} disabled={outputSrt && selectedOutputCount === 1} label="SRT" onClick={() => setOutputSrt(!outputSrt)} />
              <OutputChip checked={outputTxt} disabled={outputTxt && selectedOutputCount === 1} label="TXT" onClick={() => setOutputTxt(!outputTxt)} />
              <OutputChip checked={outputMd} disabled={outputMd && selectedOutputCount === 1} label="MD" onClick={() => setOutputMd(!outputMd)} />
              <OutputChip checked={outputJson} disabled={outputJson && selectedOutputCount === 1} label="JSON" onClick={() => setOutputJson(!outputJson)} />
            </div>
            <p className="output-control-hint">{t.outputHint}</p>
          </div>
        </div>
      </section>

      <section className="config-section pipeline-section">
        <header className="section-heading-new">
          <span className="section-icon"><Workflow size={18} aria-hidden="true" /></span>
          <div>
            <p className="section-step">STEP 03</p>
            <h3>{t.processingFlow}</h3>
          </div>
        </header>
        <div className="flow-grid">
          {inputMode === "upload" && file && !isSrt ? (
            <article className={`flow-card ${trackMuxEnabled ? "active" : ""}`}>
            <div className="flow-card-header">
              <span className="flow-index">1</span>
                <div className="flow-copy">
                  <h3>{t.stageLabels.track_mux}</h3>
                  <p>{t.trackMuxHint}</p>
                </div>
                <SwitchControl
                  checked={trackMuxEnabled}
                  label={trackMuxEnabled ? t.on : t.off}
                  onChange={(checked) => {
                    setTrackMuxEnabled(checked);
                    if (!checked) {
                      setAudioFile(null);
                    }
                  }}
                />
              </div>
              {trackMuxEnabled ? (
                <>
                  <label className="flow-select-field">
                    {t.transcribeFrom}
                    <select
                      aria-label={t.transcribeFrom}
                      value={transcribeFrom}
                      onChange={(event) => setTranscribeFrom(event.target.value)}
                    >
                      <option value="external_audio">{t.transcribeFromExternal}</option>
                      <option value="muxed">{t.transcribeFromMuxed}</option>
                    </select>
                  </label>
                  <SwitchControl
                    checked={useShortest}
                    label={t.useShortest}
                    onChange={setUseShortest}
                  />
                </>
              ) : null}
            </article>
          ) : null}

          <article className={`flow-card ${inputMode === "url" || !file || !isSrt ? "active" : "muted"}`}>
            <div className="flow-card-header">
              <span className="flow-index">{inputMode === "url" ? "1" : file && !isSrt ? "2" : "1"}</span>
              <div className="flow-copy">
                <h3>{t.stageLabels.transcription}</h3>
                <p>
                  {inputMode === "url"
                    ? t.ytdlpMergeHint
                    : isSrt
                      ? t.skippedForSrt
                      : t.pipelineHintVideo}
                </p>
              </div>
              <span className="flow-badge">
                {inputMode === "url" ? t.stageLabels.download : isSrt ? t.skippedForSrt : t.alwaysOn}
              </span>
            </div>
            <div className="flow-meta">
              <span>{t.transcriptionBackend}</span>
              <strong>{backendText}</strong>
            </div>
          </article>

          <article className={`flow-card ${mergeEnabled ? "active" : ""}`}>
            <div className="flow-card-header">
              <span className="flow-index">
                {inputMode === "url" ? "2" : file && !isSrt ? "3" : "2"}
              </span>
              <div className="flow-copy">
                <h3>{t.stageLabels.merge}</h3>
                <p>{t.mergeHint}</p>
              </div>
              <SwitchControl
                checked={mergeEnabled}
                label={mergeEnabled ? t.on : t.off}
                onChange={setMergeEnabled}
              />
            </div>
            <div className="flow-meta">
              <span>{t.maximumCharacters}</span>
              <strong>{mergeEnabled ? maxChars : t.off}</strong>
            </div>
          </article>

          <article className={`flow-card ${enableTranslation ? "active" : ""}`}>
            <div className="flow-card-header">
              <span className="flow-index">
                {inputMode === "url" ? "3" : file && !isSrt ? "4" : "3"}
              </span>
              <div className="flow-copy">
                <h3>{t.stageLabels.translation}</h3>
                <p>{isSrt ? t.pipelineHintSrt : t.translationHint}</p>
              </div>
              <SwitchControl
                checked={enableTranslation}
                label={enableTranslation ? t.on : t.off}
                onChange={setEnableTranslation}
              />
            </div>
            <div className="flow-meta">
              <span>{t.providerModel}</span>
              <strong>{providerModel || t.configuredModel}</strong>
            </div>
          </article>
        </div>
      </section>

      <details className="advanced-settings">
        <summary>
          <span className="section-icon"><SlidersHorizontal size={18} aria-hidden="true" /></span>
          <span className="advanced-summary-copy">
            <strong>{t.advancedSettings}</strong>
            <small>{t.subtitleMerge} · {t.timestampSettings} · {t.providerSettings}</small>
          </span>
          <ChevronDown className="advanced-chevron" size={18} aria-hidden="true" />
        </summary>

        <div className="advanced-settings-body">
          <section className="advanced-group">
            <header className="advanced-group-heading">
              <span className="section-icon subtle"><Captions size={17} aria-hidden="true" /></span>
              <div>
                <h3>{t.subtitleMerge} · {t.minimumDuration}</h3>
                <p>{t.mergeHint}</p>
              </div>
            </header>
            <div className="param-grid">
              <label>
                {t.minimumDuration}
                <input type="text" inputMode="numeric" value={minDurationMs} placeholder={String(MERGE_DEFAULTS.min_duration_ms)} disabled={!mergeEnabled} onChange={(event) => setMinDurationMs(normalizeDigitsInput(event.target.value))} />
              </label>
              <label>
                {t.maximumCharacters}
                <input type="text" inputMode="numeric" value={maxChars} placeholder={String(MERGE_DEFAULTS.max_chars)} disabled={!mergeEnabled} onChange={(event) => setMaxChars(normalizeDigitsInput(event.target.value))} />
              </label>
              <label>
                {t.maximumGap}
                <input type="text" inputMode="numeric" value={maxGapMs} placeholder={String(MERGE_DEFAULTS.max_gap_ms)} disabled={!mergeEnabled} onChange={(event) => setMaxGapMs(normalizeDigitsInput(event.target.value))} />
              </label>
            </div>
            <SwitchControl checked={protectSentenceEndings} label={t.protectSentenceEndings} onChange={setProtectSentenceEndings} />
          </section>

          {inputMode === "upload" && file && !isSrt && asrBackend === "whisper_cpp" ? (
            <section className="advanced-group">
              <header className="advanced-group-heading">
                <span className="section-icon subtle"><AudioLines size={17} aria-hidden="true" /></span>
                <div><h3>{t.timestampSettings}</h3></div>
              </header>
              <div className="timestamp-grid">
                <label>
                  {t.timestampPrecision}
                  <select aria-label={t.timestampPrecision} value={timestampPrecision} onChange={(event) => setTimestampPrecision(event.target.value)}>
                    {WHISPER_TIMESTAMP_PRECISIONS.map((option) => (
                      <option key={option.value} value={option.value}>{t.timestampPrecisionLabels[option.value] ?? option.label}</option>
                    ))}
                  </select>
                  <p className="field-hint">{t.timestampPrecisionHints[timestampPrecision] ?? ""}</p>
                </label>
                {timestampPrecision === "word_dtw" ? (
                  <label>
                    {t.dtwPreset}
                    <select aria-label={t.dtwPreset} value={dtwPreset} onChange={(event) => setDtwPreset(event.target.value)}>
                      {DTW_PRESET_OPTIONS.map((preset) => <option key={preset || "auto"} value={preset}>{preset || t.dtwAuto}</option>)}
                    </select>
                  </label>
                ) : null}
              </div>
            </section>
          ) : null}

          {enableTranslation ? (
            <section className="advanced-group">
              <header className="advanced-group-heading">
                <span className="section-icon subtle"><Settings2 size={17} aria-hidden="true" /></span>
                <div><h3>{t.providerSettings}</h3><p>{providerApiKeyConfigured ? t.providerApiKeyConfigured : t.providerApiKeyMissing}</p></div>
              </header>
              <div className="provider-grid two-columns">
                <label>
                  {t.providerBaseUrl}
                  <input aria-label={t.providerBaseUrl} type="url" value={providerBaseUrl} onChange={(event) => setProviderBaseUrl(event.target.value)} />
                </label>
                <label>
                  {t.providerModel}
                  <input aria-label={t.providerModel} type="text" value={providerModel} onChange={(event) => setProviderModel(event.target.value)} />
                </label>
              </div>
            </section>
          ) : null}

          {enableTranslation ? (
            <section className="advanced-group">
              <header className="advanced-group-heading">
                <span className="section-icon subtle"><MessageSquareText size={17} aria-hidden="true" /></span>
                <div><h3>{t.promptAndTerminology}</h3></div>
              </header>
              <div className="text-grid">
                <label>
                  {t.systemPrompt}
                  <textarea rows={4} value={systemPrompt} onChange={(event) => setSystemPrompt(event.target.value)} />
                </label>
                <label>
                  {t.terminology}
                  <textarea aria-label={t.terminology} rows={4} placeholder={t.terminologyPlaceholder} value={terminology} onChange={(event) => setTerminology(event.target.value)} />
                </label>
              </div>
            </section>
          ) : null}
        </div>
      </details>

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="submit-bar">
        <div className="submit-note">
          <ShieldCheck size={18} aria-hidden="true" />
          <span>{t.aboutLocalOnly}</span>
        </div>
        <button className="primary-button start-button" type="submit" disabled={submitting || !canSubmit}>
          <Play size={17} fill="currentColor" aria-hidden="true" />
          {submitting ? t.starting : t.startJob}
        </button>
      </div>
    </form>
  );
}
