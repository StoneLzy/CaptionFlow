export interface WorkbenchDefaults {
  inputMode: "upload" | "url";
  sourceLanguage: string;
  targetLanguage: string;
  outputSrt: boolean;
  outputTxt: boolean;
  outputMd: boolean;
  outputJson: boolean;
  mergeEnabled: boolean;
  enableTranslation: boolean;
  minDurationMs: string;
  maxChars: string;
  maxGapMs: string;
  protectSentenceEndings: boolean;
  providerBaseUrl: string;
  providerModel: string;
  systemPrompt: string;
  terminology: string;
  trackMuxEnabled: boolean;
  transcribeFrom: string;
  useShortest: boolean;
  ytdlpPreset: string;
}

const STORAGE_KEY = "tm-workbench-defaults";

export function loadWorkbenchDefaults(): Partial<WorkbenchDefaults> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    return JSON.parse(raw) as Partial<WorkbenchDefaults>;
  } catch {
    return {};
  }
}

export function saveWorkbenchDefaults(defaults: WorkbenchDefaults): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(defaults));
}

export const OUTPUT_LABELS: Record<string, { zh: string; en: string }> = {
  transcript_srt: { zh: "转写字幕 SRT", en: "Transcript SRT" },
  transcript_txt: { zh: "转写 TXT", en: "Transcript TXT" },
  transcript_md: { zh: "转写 Markdown", en: "Transcript Markdown" },
  transcript_json: { zh: "转写 JSON", en: "Transcript JSON" },
  merged_srt: { zh: "合并字幕 SRT", en: "Merged SRT" },
  translation_srt: { zh: "翻译字幕 SRT", en: "Translation SRT" },
  bilingual_txt: { zh: "双语 TXT", en: "Bilingual TXT" },
  bilingual_md: { zh: "双语 Markdown", en: "Bilingual Markdown" },
  input_mp4: { zh: "输入视频", en: "Input video" },
  muxed_mp4: { zh: "合成视频", en: "Muxed video" },
  ytdlp_log: { zh: "yt-dlp 日志", en: "yt-dlp log" },
  download_title: { zh: "下载标题", en: "Download title" },
};
