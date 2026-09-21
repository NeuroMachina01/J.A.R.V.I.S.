# core/language.py
# Zero-dependency language detector for the JARVIS pipeline.
# Detects Hindi (Devanagari script) vs English from raw text.
# Used as a fallback when Whisper language detection is unavailable
# (e.g., typed input from the Web UI).

import re
import logging

logger = logging.getLogger(__name__)

# Devanagari Unicode block: U+0900 to U+097F
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

# Edge-TTS voice map — one female voice per supported language
VOICE_MAP = {
    "en": "en-IN-NeerjaNeural",    # Indian English female
    "hi": "hi-IN-SwaraNeural",     # Hindi female
}

# Whisper returns full language names; map them to ISO-639-1 codes
_WHISPER_LANG_MAP = {
    "english": "en",
    "hindi": "hi",
    "hinglish": "hi",
    "urdu": "hi",       # Close enough for TTS voice selection
    "bengali": "hi",    # Fallback to Hindi voice for Indic languages
    "tamil": "hi",
    "telugu": "hi",
    "marathi": "hi",
    "gujarati": "hi",
    "kannada": "hi",
    "punjabi": "hi",
    "malayalam": "hi",
}


def detect_language(text: str) -> str:
    """
    Detects the dominant language of the input text.

    Strategy:
        1. Count Devanagari characters vs total alphabetic characters.
        2. If Devanagari ratio exceeds 30%, classify as Hindi ("hi").
           The 30% threshold handles Hinglish (mixed Hindi-English) well —
           even a few Hindi words in a mostly English sentence will trigger
           Hindi mode, which is the correct behavior for Indian users.
        3. Otherwise, classify as English ("en").

    Returns:
        ISO-639-1 language code: "hi" or "en"
    """
    if not text or not text.strip():
        return "en"

    devanagari_count = len(_DEVANAGARI_RE.findall(text))
    # Count all alphabetic characters (Latin + Devanagari + others)
    alpha_count = sum(1 for ch in text if ch.isalpha())

    if alpha_count == 0:
        return "en"

    ratio = devanagari_count / alpha_count

    detected = "hi" if ratio > 0.30 else "en"
    logger.debug(
        f"Language detection: {devanagari_count}/{alpha_count} Devanagari "
        f"(ratio={ratio:.2f}) → {detected}"
    )
    return detected


def normalize_whisper_language(whisper_lang: str) -> str:
    """
    Converts the full language name returned by Whisper's verbose_json
    response (e.g., "english", "hindi") into an ISO-639-1 code.

    Falls back to "en" for any unrecognized language.
    """
    if not whisper_lang:
        return "en"
    code = _WHISPER_LANG_MAP.get(whisper_lang.lower().strip(), "en")
    logger.debug(f"Whisper language '{whisper_lang}' → '{code}'")
    return code


def get_voice(language: str) -> str:
    """
    Returns the Edge-TTS voice name for the given language code.
    Falls back to Indian English if the language is not in the map.
    """
    return VOICE_MAP.get(language, VOICE_MAP["en"])
