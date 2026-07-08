import { FormEvent, useEffect, useState } from "react";

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

interface Props {
  onJobStarted: (job: JobSummary) => void;
  t: Translations;
}

interface JobConfig {
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
  label,
  onClick,
}: {
  checked: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`output-chip${checked ? " selected" : ""}`}
      type="button"
      aria-pressed={checked}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

export function JobWorkbench({ onJobStarted, t }: Props) {
  const storedDefaults = loadWorkbenchDefaults();
  const [inputMode, setInputMode] = useState<"upload" | "url">(storedDefaults.inputMode ?? "upload");
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
      source_language: sourceLanguage,
      target_language: targetLanguage,
      output_formats: outputFormats.length > 0 ? outputFormats : ["srt"],
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
      onJobStarted(created);
      const started = await runJob(created.id);
      onJobStarted(started);
      saveWorkbenchDefaults({
        inputMode,
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

  const isSrt = inputMode === "upload" && file ? isSrtFile(file) : false;
  const canSubmit =
    inputMode === "url" ? videoUrl.trim().length > 0 : file !== null;
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
      <section className="task-strip">
        <div className="task-strip-copy">
          <h2>{t.newJob}</h2>
          <p>{t.newJobHint}</p>
        </div>
        <div className="task-strip-files">
          <div className="chip-row">
            <OutputChip
              checked={inputMode === "upload"}
              label={t.inputModeUpload}
              onClick={() => {
                setInputMode("upload");
                setError(null);
              }}
            />
            <OutputChip
              checked={inputMode === "url"}
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
          {inputMode === "upload" ? (
            <>
              <label className="file-drop">
                <span>{t.fileLabel}</span>
                <strong>{file ? file.name : t.fileHint}</strong>
                <input
                  aria-label={t.fileLabel}
                  type="file"
                  accept="video/*,.srt"
                  onChange={(event) => {
                    const nextFile = event.target.files?.[0] ?? null;
                    setFile(nextFile);
                    if (!nextFile || isSrtFile(nextFile)) {
                      setTrackMuxEnabled(false);
                      setAudioFile(null);
                    }
                  }}
                />
              </label>
              {file && !isSrt ? (
                <label className={`file-drop${trackMuxEnabled ? "" : " optional"}`}>
                  <span>{t.audioFileLabel}</span>
                  <strong>{audioFile ? audioFile.name : t.audioFileHint}</strong>
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
            </>
          ) : (
            <label className="flow-select-field">
              <span>{t.videoUrlLabel}</span>
              <input
                aria-label={t.videoUrlLabel}
                type="url"
                value={videoUrl}
                placeholder={t.videoUrlPlaceholder}
                onChange={(event) => setVideoUrl(event.target.value)}
              />
              <p className="field-hint">{t.videoUrlHint}</p>
            </label>
          )}
        </div>
        <button className="primary-button" type="submit" disabled={submitting || !canSubmit}>
          {submitting ? t.starting : t.startJob}
        </button>
      </section>

      <section className="config-section">
        <div className="section-kicker">{t.basicSettings}</div>
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
              <OutputChip checked={outputSrt} label="SRT" onClick={() => setOutputSrt(!outputSrt)} />
              <OutputChip checked={outputTxt} label="TXT" onClick={() => setOutputTxt(!outputTxt)} />
              <OutputChip checked={outputMd} label="MD" onClick={() => setOutputMd(!outputMd)} />
              <OutputChip checked={outputJson} label="JSON" onClick={() => setOutputJson(!outputJson)} />
            </div>
            <p className="output-control-hint">{t.outputHint}</p>
          </div>
          {inputMode === "url" ? (
            <>
              <label>
                {t.ytdlpFormatPreset}
                <select
                  aria-label={t.ytdlpFormatPreset}
                  value={ytdlpPreset}
                  onChange={(event) => setYtdlpPreset(event.target.value)}
                >
                  <option value="best">{t.ytdlpFormatBest}</option>
                  <option value="best_1080p">{t.ytdlpFormat1080}</option>
                  <option value="best_720p">{t.ytdlpFormat720}</option>
                  <option value="custom">{t.ytdlpFormatCustom}</option>
                </select>
              </label>
              {ytdlpPreset === "custom" ? (
                <label>
                  {t.ytdlpCustomFormat}
                  <input
                    aria-label={t.ytdlpCustomFormat}
                    type="text"
                    value={ytdlpCustomFormat}
                    placeholder={t.ytdlpCustomFormatPlaceholder}
                    onChange={(event) => setYtdlpCustomFormat(event.target.value)}
                  />
                </label>
              ) : null}
            </>
          ) : null}
        </div>
      </section>

      <section className="config-section">
        <div className="section-kicker">{t.processingFlow}</div>
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
            {inputMode === "upload" && file && !isSrt && asrBackend === "whisper_cpp" ? (
              <div className="timestamp-grid">
                <label>
                  {t.timestampPrecision}
                  <select
                    aria-label={t.timestampPrecision}
                    value={timestampPrecision}
                    onChange={(event) => setTimestampPrecision(event.target.value)}
                  >
                    {WHISPER_TIMESTAMP_PRECISIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t.timestampPrecisionLabels[option.value] ?? option.label}
                      </option>
                    ))}
                  </select>
                  <p className="field-hint">
                    {t.timestampPrecisionHints[timestampPrecision] ?? ""}
                  </p>
                </label>
                {timestampPrecision === "word_dtw" ? (
                  <label>
                    {t.dtwPreset}
                    <select
                      aria-label={t.dtwPreset}
                      value={dtwPreset}
                      onChange={(event) => setDtwPreset(event.target.value)}
                    >
                      {DTW_PRESET_OPTIONS.map((preset) => (
                        <option key={preset || "auto"} value={preset}>
                          {preset ? preset : t.dtwAuto}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>
            ) : null}
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
            <div className="param-grid">
              <label>
                {t.minimumDuration}
                <input
                  type="text"
                  inputMode="numeric"
                  value={minDurationMs}
                  placeholder={String(MERGE_DEFAULTS.min_duration_ms)}
                  disabled={!mergeEnabled}
                  onChange={(event) =>
                    setMinDurationMs(normalizeDigitsInput(event.target.value))
                  }
                />
              </label>
              <label>
                {t.maximumCharacters}
                <input
                  type="text"
                  inputMode="numeric"
                  value={maxChars}
                  placeholder={String(MERGE_DEFAULTS.max_chars)}
                  disabled={!mergeEnabled}
                  onChange={(event) => setMaxChars(normalizeDigitsInput(event.target.value))}
                />
              </label>
              <label>
                {t.maximumGap}
                <input
                  type="text"
                  inputMode="numeric"
                  value={maxGapMs}
                  placeholder={String(MERGE_DEFAULTS.max_gap_ms)}
                  disabled={!mergeEnabled}
                  onChange={(event) => setMaxGapMs(normalizeDigitsInput(event.target.value))}
                />
              </label>
            </div>
            <SwitchControl
              checked={protectSentenceEndings}
              label={t.protectSentenceEndings}
              onChange={setProtectSentenceEndings}
            />
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

      {enableTranslation ? (
        <section className="config-section">
          <div className="section-kicker">{t.providerSettings}</div>
          <div className="provider-grid two-columns">
            <label>
              {t.providerBaseUrl}
              <input
                aria-label={t.providerBaseUrl}
                type="url"
                value={providerBaseUrl}
                onChange={(event) => setProviderBaseUrl(event.target.value)}
              />
            </label>
            <label>
              {t.providerModel}
              <input
                aria-label={t.providerModel}
                type="text"
                value={providerModel}
                onChange={(event) => setProviderModel(event.target.value)}
              />
            </label>
          </div>
          <p className="provider-footnote">
            {providerApiKeyConfigured
              ? t.providerApiKeyConfigured
              : t.providerApiKeyMissing}
          </p>
        </section>
      ) : null}
      {enableTranslation ? (
        <section className="config-section">
          <div className="section-kicker">{t.promptAndTerminology}</div>
          <div className="text-grid">
            <label>
              {t.systemPrompt}
              <textarea
                rows={4}
                value={systemPrompt}
                onChange={(event) => setSystemPrompt(event.target.value)}
              />
            </label>
            <label>
              {t.terminology}
              <textarea
                aria-label={t.terminology}
                rows={4}
                placeholder={t.terminologyPlaceholder}
                value={terminology}
                onChange={(event) => setTerminology(event.target.value)}
              />
            </label>
          </div>
        </section>
      ) : null}
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  );
}
