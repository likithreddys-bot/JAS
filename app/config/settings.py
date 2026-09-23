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
    # "porcupine" = say just "Jarvis" (needs a free Picovoice AccessKey); "openwakeword" = "Hey Jarvis".
    wake_word_engine: str = "openwakeword"
    picovoice_access_key: str = ""
    porcupine_keyword: str = "jarvis"
    porcupine_sensitivity: float = 0.5
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
    # Names and words speech recognition should expect (people, apps, places), comma-separated.
    stt_vocabulary: str = "Jarvis, Notepad, WhatsApp, VS Code, Chrome, YouTube"

    # Google (Calendar, Gmail, Contacts): sign in once with scripts/google_login.py
    google_client_file: Path = PROJECT_ROOT / "data" / "google_client.json"
    google_token_file: Path = PROJECT_ROOT / "data" / "google_token.json"

    # Wake JARVIS from anywhere without the wake word.
    hotkey: str = "ctrl+space"

    # Personal
    user_name: str = "Likki"
    home_city: str = "Bengaluru"
    # Start in rest mode (and rest again after the laptop wakes from sleep); "wake up Jarvis" gives the briefing.
    start_resting: bool = True
    # Played in your Chrome after the morning briefing (YouTube search; a different top result each day).
    morning_music: str = "calm good morning instrumental music"
    # Suggest a break after this many minutes of continuous screen use (0 = off).
    break_reminder_minutes: int = 90

    # Listening: seconds of silence that end your sentence, how long to wait for you to start, max length.
    listen_end_silence: float = 1.5
    listen_start_timeout: float = 8.0
    listen_max_seconds: float = 30.0

    # After answering, keep listening this many seconds for a follow-up without the wake word (0 = off).
    follow_up_seconds: float = 6.0

    # Folder JARVIS may read/write for coding help (never AppData, keys or .env files inside it).
    files_root: Path = Path.home()

    # Your Chrome profile for websites and music (name as shown in Chrome); empty = last used.
    chrome_profile: str = ""
    # Invisible browser used only for web research (search, reading pages).
    browser_profile_dir: Path = PROJECT_ROOT / "data" / "browser-profile"

    llm_provider: str = "gemini"  # "gemini" (free tier) or "claude"
    gemini_api_key: str = ""
    # Comma-separated priority list; the next is tried if one is overloaded or unavailable.
    gemini_model: str = "gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-flash-lite-latest"
    # How much Gemini thinks before acting: minimal (fastest) / low / medium / high; empty = model default.
    gemini_thinking: str = "minimal"
    claude_api_key: str = ""
    claude_model: str = "claude-opus-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
