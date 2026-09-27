"""Language/multilingual support for torrentio-tui.

Provides language configuration, ISO code mapping, and subtitle language
selection for streams.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Language(Enum):
    """Supported languages with ISO 639-1 codes."""
    
    # Major languages
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    HINDI = "hi"
    BENGALI = "bn"
    TURKISH = "tr"
    POLISH = "pl"
    DUTCH = "nl"
    SWEDISH = "sv"
    NORWEGIAN = "no"
    DANISH = "da"
    FINNISH = "fi"
    CZECH = "cs"
    HUNGARIAN = "hu"
    ROMANIAN = "ro"
    BULGARIAN = "bg"
    CROATIAN = "hr"
    SERBIAN = "sr"
    SLOVAK = "sk"
    SLOVENIAN = "sl"
    ESTONIAN = "et"
    LATVIAN = "lv"
    LITHUANIAN = "lt"
    GREEK = "el"
    HEBREW = "he"
    THAI = "th"
    VIETNAMESE = "vi"
    INDONESIAN = "id"
    MALAY = "ms"
    TAGALOG = "tl"
    UKRAINIAN = "uk"
    
    # Regional variants
    ENGLISH_US = "en-US"
    ENGLISH_GB = "en-GB"
    PORTUGUESE_BR = "pt-BR"
    PORTUGUESE_PT = "pt-PT"
    SPANISH_ES = "es-ES"
    SPANISH_MX = "es-MX"
    FRENCH_FR = "fr-FR"
    FRENCH_CA = "fr-CA"
    CHINESE_SIMPLIFIED = "zh-CN"
    CHINESE_TRADITIONAL = "zh-TW"


# Human-readable names for each language
LANGUAGE_NAMES = {
    Language.ENGLISH: "English",
    Language.SPANISH: "Spanish",
    Language.FRENCH: "French",
    Language.GERMAN: "German",
    Language.ITALIAN: "Italian",
    Language.PORTUGUESE: "Portuguese",
    Language.RUSSIAN: "Russian",
    Language.CHINESE: "Chinese",
    Language.JAPANESE: "Japanese",
    Language.KOREAN: "Korean",
    Language.ARABIC: "Arabic",
    Language.HINDI: "Hindi",
    Language.BENGALI: "Bengali",
    Language.TURKISH: "Turkish",
    Language.POLISH: "Polish",
    Language.DUTCH: "Dutch",
    Language.SWEDISH: "Swedish",
    Language.NORWEGIAN: "Norwegian",
    Language.DANISH: "Danish",
    Language.FINNISH: "Finnish",
    Language.CZECH: "Czech",
    Language.HUNGARIAN: "Hungarian",
    Language.ROMANIAN: "Romanian",
    Language.BULGARIAN: "Bulgarian",
    Language.CROATIAN: "Croatian",
    Language.SERBIAN: "Serbian",
    Language.SLOVAK: "Slovak",
    Language.SLOVENIAN: "Slovenian",
    Language.ESTONIAN: "Estonian",
    Language.LATVIAN: "Latvian",
    Language.LITHUANIAN: "Lithuanian",
    Language.GREEK: "Greek",
    Language.HEBREW: "Hebrew",
    Language.THAI: "Thai",
    Language.VIETNAMESE: "Vietnamese",
    Language.INDONESIAN: "Indonesian",
    Language.MALAY: "Malay",
    Language.TAGALOG: "Tagalog",
    Language.UKRAINIAN: "Ukrainian",
    Language.ENGLISH_US: "English (US)",
    Language.ENGLISH_GB: "English (UK)",
    Language.PORTUGUESE_BR: "Portuguese (Brazil)",
    Language.PORTUGUESE_PT: "Portuguese (Portugal)",
    Language.SPANISH_ES: "Spanish (Spain)",
    Language.SPANISH_MX: "Spanish (Mexico)",
    Language.FRENCH_FR: "French (France)",
    Language.FRENCH_CA: "French (Canada)",
    Language.CHINESE_SIMPLIFIED: "Chinese (Simplified)",
    Language.CHINESE_TRADITIONAL: "Chinese (Traditional)",
}

# Subtitle language codes commonly used by streaming services
SUBTITLE_LANGUAGE_CODES = {
    "eng": Language.ENGLISH,
    "spa": Language.SPANISH,
    "fre": Language.FRENCH,
    "ger": Language.GERMAN,
    "ita": Language.ITALIAN,
    "por": Language.PORTUGUESE,
    "rus": Language.RUSSIAN,
    "chi": Language.CHINESE,
    "jpn": Language.JAPANESE,
    "kor": Language.KOREAN,
    "ara": Language.ARABIC,
    "hin": Language.HINDI,
    "ben": Language.BENGALI,
    "tur": Language.TURKISH,
    "pol": Language.POLISH,
    "dut": Language.DUTCH,
    "swe": Language.SWEDISH,
    "nor": Language.NORWEGIAN,
    "dan": Language.DANISH,
    "fin": Language.FINNISH,
    "cze": Language.CZECH,
    "hun": Language.HUNGARIAN,
    "rum": Language.ROMANIAN,
    "bul": Language.BULGARIAN,
    "hrv": Language.CROATIAN,
    "srp": Language.SERBIAN,
    "slo": Language.SLOVAK,
    "slv": Language.SLOVENIAN,
    "est": Language.ESTONIAN,
    "lav": Language.LATVIAN,
    "lit": Language.LITHUANIAN,
    "gre": Language.GREEK,
    "heb": Language.HEBREW,
    "tha": Language.THAI,
    "vie": Language.VIETNAMESE,
    "ind": Language.INDONESIAN,
    "may": Language.MALAY,
    "tgl": Language.TAGALOG,
    "ukr": Language.UKRAINIAN,
}


@dataclass(slots=True)
class LanguageConfig:
    """Language configuration for the app."""
    
    # Primary UI language (ISO 639-1 code)
    ui_language: str = "en"
    
    # Preferred subtitle languages (in order of preference)
    subtitle_languages: list[str] = field(default_factory=lambda: ["eng", "spa", "fre"])
    
    # Preferred audio languages (in order of preference)
    audio_languages: list[str] = field(default_factory=lambda: ["eng", "jpn", "kor"])
    
    # Auto-translate subtitles if preferred language not available
    auto_translate: bool = True
    
    # Show content in original language with subtitles
    prefer_original_audio: bool = True
    
    def get_ui_language_name(self) -> str:
        """Get human-readable name for the UI language."""
        try:
            lang = Language(self.ui_language)
            return LANGUAGE_NAMES.get(lang, self.ui_language)
        except ValueError:
            return self.ui_language
    
    def get_subtitle_language_names(self) -> list[str]:
        """Get human-readable names for subtitle languages."""
        names = []
        for code in self.subtitle_languages:
            try:
                lang = Language(code)
                names.append(LANGUAGE_NAMES.get(lang, code))
            except ValueError:
                names.append(code)
        return names


# Default language config
DEFAULT_LANGUAGE_CONFIG = LanguageConfig()


def get_language_config() -> LanguageConfig:
    """Get the default language configuration."""
    return DEFAULT_LANGUAGE_CONFIG