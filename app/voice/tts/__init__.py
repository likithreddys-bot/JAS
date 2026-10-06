

def make_speaker(settings):
    """Kokoro (TTS_ENGINE=kokoro, the default) or Piper. If Kokoro can't load - the package or its
    model is missing, or the download fails - say so in the log and fall back to Piper, so the
    assistant is never left without a voice."""
    import logging

    log = logging.getLogger("jarvis.voice.tts")
    if settings.tts_engine.strip().lower() == "kokoro":
        try:
            from app.voice.tts.kokoro_speaker import KokoroSpeaker

            return KokoroSpeaker(settings.kokoro_voice, settings.models_dir / "kokoro", settings.tts_speed,
                                 settings.kokoro_voice_higher)
        except Exception:
            log.exception("Kokoro voice unavailable; falling back to Piper")
    from app.voice.tts.speaker import Speaker

    return Speaker(settings.tts_voice, settings.models_dir / "piper", settings.tts_speed,
                   settings.tts_voice_higher)
