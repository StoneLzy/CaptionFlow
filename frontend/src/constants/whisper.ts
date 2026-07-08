export const WHISPER_TIMESTAMP_PRECISIONS = [
  {
    value: "standard",
    label: "Standard (~1s segments)",
    hint: "Default whisper.cpp segment timestamps.",
  },
  {
    value: "word",
    label: "Word-level (-ml 1 -sow)",
    hint: "Split on words with sub-second timestamps. Slower, more subtitle lines.",
  },
  {
    value: "word_dtw",
    label: "Word-level + DTW",
    hint: "Word timestamps refined with DTW. Best effort; needs a matching DTW preset.",
  },
] as const;

export const DEFAULT_WHISPER_TIMESTAMP_PRECISION = "standard";

export const DTW_PRESET_OPTIONS = [
  "",
  "large.v3.turbo",
  "large.v3",
  "large.v2",
  "large.v1",
  "medium",
  "medium.en",
  "small",
  "small.en",
  "base",
  "base.en",
  "tiny",
  "tiny.en",
] as const;
