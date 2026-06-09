"""asr_filter — shared hallucination pattern module for ASR output filtering.

Canonical source of truth for HALLUCINATION_PATTERNS.

Usage (Orchestrator / any Python host-side code):
    from adam.asr_filter import is_hallucination, HALLUCINATION_PATTERNS

Usage note for ASR_WhisperX.py (Docker):
    The Dockerfile copies ONLY ASR_WhisperX.py into /app/Speech/ — this module is NOT
    available inside the Docker container. ASR_WhisperX.py keeps a synchronized local copy
    of _HALLUCINATION_PATTERNS. When adding new patterns, update BOTH files.

Pure stdlib — no external dependencies, no imports from other adam modules.
"""
from __future__ import annotations


def _normalise(s: str) -> str:
    """Lowercase and strip surrounding punctuation/brackets — mirrors ASR_WhisperX.py lookup."""
    return s.lower().strip("[]().,!? \t\n")


# Canonical hallucination pattern set — all patterns stored in normalised form
# (lowercase, no surrounding brackets/punctuation, matching what _normalise() produces).
#
# Categories:
#   1. YouTube-subtitle hallucinations: Whisper-small generates these on near-silence
#      because they appear with high frequency in the YouTube training data.
#   2. Bracket/noise markers: Whisper emits these for non-speech audio events.
#   3. Whisper-small Russian artefacts: near-silence triggers specific to small models.
#   4. YouTube/attention CTAs: common Russian YouTube call-to-action phrases.
#   5. Punctuation-only segments: silence artefacts.
#
# Synchronized with System/Speech/ASR_WhisperX.py _HALLUCINATION_PATTERNS.
# When adding patterns: update BOTH files. This file is the canonical source.
HALLUCINATION_PATTERNS: frozenset[str] = frozenset({
    # --- YouTube subtitle hallucinations (near-silence triggers) ---
    "тревожная музыка",
    "интригующая музыка",
    "спокойная музыка",
    "весёлая музыка",
    "грустная музыка",
    "музыка",
    "субтитры добавлены",
    "спасибо за просмотр",
    "подписывайтесь на канал",
    "продолжение следует",
    "не забудьте подписаться",
    "спасибо за внимание",
    "до встречи",
    "увидимся в следующий раз",
    "оставайтесь с нами",
    "продолжение в следующей части",
    "ссылки в описании",
    # --- Bracket/noise markers (normalised: brackets stripped by _normalise) ---
    "тихая музыка",
    "music",
    "applause",
    "blank_audio",
    "inaudible",
    "шум",
    "тишина",
    "нет звука",
    "аплодисменты",
    "смех",
    # --- Whisper-small Russian artefacts (near-silence hallucinations) ---
    "компиция",
    "цыц",
    "ля ля ля",
    "да да",
    "нет нет",
    "хорошо хорошо",
    "ок ок",
    # --- YouTube/attention CTAs ---
    "лайк и подписка",
    "колокольчик уведомлений",
    "смотрите также",
    "следующее видео",
    "конец видео",
    "до следующего раза",
    "пока пока",
    "поставьте лайк",
    "комментируйте",
    "поделитесь видео",
    # --- Punctuation-only segments ---
    ".",
    ",",
    "...",
})


def is_hallucination(text: str) -> bool:
    """Return True if ``text`` is a known Whisper hallucination pattern.

    Comparison is case-insensitive and ignores surrounding punctuation/brackets,
    matching the normalisation used in ASR_WhisperX.py:
        text.lower().strip("[]().,!? ")

    Args:
        text: Raw transcript string from ASR.

    Returns:
        True if the normalised text matches a known hallucination pattern.
    """
    if not text or not text.strip():
        return False
    return _normalise(text) in HALLUCINATION_PATTERNS
