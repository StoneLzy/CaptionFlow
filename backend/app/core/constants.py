from enum import StrEnum


class SourceLanguage(StrEnum):
    AUTO = "auto"
    CHINESE = "zh"
    ENGLISH = "en"
    JAPANESE = "ja"
    KOREAN = "ko"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    RUSSIAN = "ru"


class TargetLanguage(StrEnum):
    SIMPLIFIED_CHINESE = "zh-Hans"
    JAPANESE = "ja"
    ENGLISH = "en"
    TRADITIONAL_CHINESE = "zh-Hant"
    FRENCH = "fr"
    GERMAN = "de"


DEFAULT_TARGET_LANGUAGE = TargetLanguage.SIMPLIFIED_CHINESE
