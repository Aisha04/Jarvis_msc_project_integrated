"""Jarvis's voice and ears.

speak:  Microsoft neural voices via edge-tts (free, natural-sounding, needs internet)
        -> retried up to 3 times if the service hiccups
        -> falls back to the built-in Windows voice if it still fails, so Jarvis is never silent
listen: your microphone -> text via SpeechRecognition

Settings in .env:
  JARVIS_VOICE        en-GB-RyanNeural (default), en-GB-ThomasNeural, en-US-AndrewNeural, en-GB-SoniaNeural ...
  JARVIS_VOICE_RATE   "+4%"   (speed: "-10%" slower, "+15%" faster)
  JARVIS_VOICE_PITCH  "-4Hz"
  JARVIS_VOLUME       1.0     (0.0 - 1.0)
List all voices:  edge-tts --list-voices
"""
import asyncio
import os
import re
import tempfile
import threading
import time

_mixer_lock = threading.Lock()      # pygame audio must only be started once
_online_slots = threading.Semaphore(2)   # don't flood the voice service with parallel requests
_offline_lock = threading.Lock()    # the Windows voice engine is not thread-safe
_mixer_ready = False

mic_open = threading.Event()        # set while the microphone is recording
speaking = threading.Event()        # set while Jarvis is talking


def _log(msg):
    print(f"[voice] {msg}", flush=True)


# ---------------- audio output ----------------

def _mixer():
    global _mixer_ready
    with _mixer_lock:
        if not _mixer_ready:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame
            pygame.mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=1024)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(4)
            _mixer_ready = True
            _log(f"audio ready {pygame.mixer.get_init()}")
    import pygame
    return pygame


def init():
    """Start the audio system early (call once at startup)."""
    try:
        _mixer()
    except Exception as e:
        _log(f"could not start audio output: {e}")


def clean(text):
    """Make text safe and natural to speak: drop markdown, emoji and odd symbols."""
    t = re.sub(r"[*_`#>|~]+", " ", text or "")
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)             # [link](url) -> link
    t = t.replace("×", " x ").replace("&", " and ")
    t = re.sub(r"[^\w\s.,!?;:'\"()%°/+\-–—@]", " ", t)        # emoji etc.
    return re.sub(r"\s+", " ", t).strip()


# ---------------- online voice (edge-tts) ----------------

def _synth_online(text, path):
    import edge_tts

    async def run():
        await edge_tts.Communicate(
            text,
            os.getenv("JARVIS_VOICE", "en-GB-RyanNeural"),
            rate=os.getenv("JARVIS_VOICE_RATE", "+4%"),
            pitch=os.getenv("JARVIS_VOICE_PITCH", "-4Hz"),
        ).save(path)

    asyncio.run(asyncio.wait_for(run(), timeout=20))
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        raise RuntimeError("voice service returned no audio")


# ---------------- offline voice (Windows built-in) ----------------

def _synth_offline(text, path):
    with _offline_lock:
        try:
            import comtypes                      # Windows: allow the voice engine in this thread
            comtypes.CoInitialize()
        except Exception:
            pass
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.save_to_file(text, path)
        engine.runAndWait()
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        raise RuntimeError("offline voice produced no audio")


def synthesize(text):
    """Turn text into an audio file and return its path. Tries hard never to fail."""
    text = clean(text)
    if not text:
        raise ValueError("nothing to say")
    base = os.path.join(tempfile.gettempdir(), f"jarvis_{time.time_ns()}")

    with _online_slots:
        for attempt in range(1, 4):
            path = base + ".mp3"
            try:
                _synth_online(text, path)
                return path
            except Exception as e:
                _log(f"online voice failed (try {attempt}/3): {type(e).__name__}: {e}")
                _cleanup(path)
                time.sleep(0.4 * attempt)

    _log("using the offline Windows voice for this sentence")
    path = base + ".wav"
    _synth_offline(text, path)
    return path


def load(path):
    """Load audio and measure its loudness every 50 ms (drives the orb)."""
    pygame = _mixer()
    sound = pygame.mixer.Sound(path)
    sound.set_volume(float(os.getenv("JARVIS_VOLUME", "1.0")))
    if sound.get_length() < 0.05:
        raise RuntimeError("audio file is empty")
    try:
        import numpy as np
        samples = pygame.sndarray.array(sound).astype(np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        freq = pygame.mixer.get_init()[0]
        win = max(1, freq // 20)
        n = len(samples) // win
        rms = np.sqrt((samples[: n * win].reshape(n, win) ** 2).mean(axis=1))
        peak = np.percentile(rms, 95) or 1.0
        envelope = [round(float(v), 3) for v in np.clip(rms / peak, 0, 1) ** 0.8]
    except Exception:
        envelope = []  # orb falls back to a simulated pulse
    return sound, envelope


def play(sound):
    """Play and block until finished."""
    pygame = _mixer()
    # the mic being open while we talk can mute Bluetooth headsets on Windows,
    # so give any recording in progress a moment to finish first
    waited = 0
    while mic_open.is_set() and waited < 2.5:
        time.sleep(0.05)
        waited += 0.05

    speaking.set()
    try:
        channel = sound.play()
        if channel is None:                      # no free channel: stop everything and retry
            pygame.mixer.stop()
            channel = sound.play()
        if channel is None:
            _log("could not start playback")
            return
        limit = time.time() + sound.get_length() + 3
        while channel.get_busy() and time.time() < limit:
            pygame.time.wait(30)
    finally:
        time.sleep(0.25)                         # let the speaker tail off before the mic re-opens
        speaking.clear()


def speak(text):
    """Simple one-call version for the terminal app."""
    try:
        path = synthesize(text)
        sound, _ = load(path)
        play(sound)
        _cleanup(path)
    except Exception as e:
        _log(f"could not speak: {e}")


def _cleanup(path):
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------- ears ----------------

_rec = _mic = None


def listen(timeout=4, phrase_limit=10):
    """Record one phrase from the mic and return the text ("" if nothing heard)."""
    global _rec, _mic
    import speech_recognition as sr
    while speaking.is_set():                     # never record while Jarvis is talking
        time.sleep(0.05)
    if _rec is None:
        _rec, _mic = sr.Recognizer(), sr.Microphone()
        _rec.pause_threshold = 0.8
        _rec.dynamic_energy_threshold = True
        mic_open.set()
        try:
            with _mic as src:
                _rec.adjust_for_ambient_noise(src, duration=0.8)
        finally:
            mic_open.clear()
    mic_open.set()
    try:
        with _mic as src:
            audio = _rec.listen(src, timeout=timeout, phrase_time_limit=phrase_limit)
    except sr.WaitTimeoutError:
        return ""
    finally:
        mic_open.clear()
    try:
        return _rec.recognize_google(audio)
    except sr.UnknownValueError:
        return ""
