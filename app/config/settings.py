"""Typed application settings, loaded from environment variables and `.env`."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = "INFO"
    log_dir: Path = PROJECT_ROOT / "logs"
    data_dir: Path = PROJECT_ROOT / "data"

    wake_word_enabled: bool = True
    wake_word_model: str = "hey_jarvis"
    wake_word_threshold: float = 0.5
    # Input device name or index as understood by sounddevice; empty = system default.
    microphone_device: str = ""

    models_dir: Path = PROJECT_ROOT / "data" / "models"
    tts_voice: str = "en_GB-alan-medium"
    tts_speed: float = 1.0
    stt_model: str = "small"
    # Language code for speech-to-text; empty = auto-detect (less reliable on short phrases).
    stt_language: str = "en"

    llm_provider: str = "gemini"  # "gemini" (free tier) or "claude"
    gemini_api_key: str = ""
    # Comma-separated priority list; the next is tried if one is overloaded or unavailable.
    gemini_model: str = "gemini-3.1-flash-lite,gemini-flash-lite-latest,gemini-3-flash-preview"
    claude_api_key: str = ""
    claude_model: str = "claude-opus-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
