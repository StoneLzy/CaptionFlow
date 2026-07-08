export const SOURCE_LANGUAGES = [
  { value: "auto", label: "Auto detect" },
  { value: "zh", label: "Chinese" },
  { value: "en", label: "English" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "es", label: "Spanish" },
  { value: "ru", label: "Russian" },
] as const;

export const TARGET_LANGUAGES = [
  { value: "zh-Hans", label: "Simplified Chinese" },
  { value: "ja", label: "Japanese" },
  { value: "en", label: "English" },
  { value: "zh-Hant", label: "Traditional Chinese" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
] as const;

export const DEFAULT_TARGET_LANGUAGE = "zh-Hans";
