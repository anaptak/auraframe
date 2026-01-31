import asyncio
import io
import wave
from typing import Optional, Tuple

import numpy as np
import requests
import sounddevice as sd
from shazamio import Shazam

from .config import (
    CACHE_DIR,
    CHANNELS,
    DEVICE,
    NETWORK_TIMEOUT_S,
    RECORD_SECONDS,
    SAMPLE_RATE,
    SLIDESHOW_DIR,
    SNIPPET_WAV_PATH,
)


def ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SLIDESHOW_DIR.mkdir(parents=True, exist_ok=True)


def record_wav_bytes() -> bytes:
    """Record mono float32, convert to 16-bit PCM WAV bytes."""
    frames = int(SAMPLE_RATE * RECORD_SECONDS)
    audio = sd.rec(frames, samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32", device=DEVICE)
    sd.wait()
    x = np.clip(audio[:, 0], -1.0, 1.0)
    pcm16 = (x * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


async def shazam_recognize_from_wav_bytes(wav_bytes: bytes) -> Optional[dict]:
    """
    Shazamio currently prefers recognize(path). We write a temp WAV to disk.
    """
    ensure_dirs()
    SNIPPET_WAV_PATH.write_bytes(wav_bytes)

    shazam = Shazam()
    try:
        return await shazam.recognize(str(SNIPPET_WAV_PATH))
    except Exception:
        return None


def extract_track_info(res: dict) -> Optional[Tuple[str, str, Optional[str], Optional[str]]]:
    """
    Returns (title, artist, album, cover_url)
    Album is best-effort (may be None).
    """
    if not isinstance(res, dict):
        return None
    track = res.get("track")
    if not isinstance(track, dict):
        return None

    title = track.get("title") or ""
    artist = track.get("subtitle") or ""

    images = track.get("images") or {}
    cover_url = (
        images.get("coverarthq")
        or images.get("coverart")
        or images.get("background")
        or None
    )

    # Best-effort album extraction (often missing)
    album = None
    sections = track.get("sections") or []
    for s in sections:
        if not isinstance(s, dict):
            continue
        metadata = s.get("metadata") or []
        for item in metadata:
            if isinstance(item, dict) and (item.get("title") or "").strip().lower() == "album":
                album = item.get("text")
                break
        if album:
            break

    if not title and not artist:
        return None
    return title, artist, album, cover_url


def download_image_to_path(url: str, out_path) -> bool:
    try:
        r = requests.get(url, timeout=NETWORK_TIMEOUT_S)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return True
    except Exception:
        return False


def recognize_track() -> Optional[Tuple[str, str, Optional[str], Optional[str]]]:
    wav_bytes = record_wav_bytes()
    res = asyncio.run(shazam_recognize_from_wav_bytes(wav_bytes))
    return extract_track_info(res) if res else None
