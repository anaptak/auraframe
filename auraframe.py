#!/usr/bin/env python3
import asyncio
import io
import os
import random
import threading
import time
import wave
from dataclasses import dataclass
from typing import Optional, Tuple, List

import numpy as np
import requests
from PIL import Image, ImageFilter, ImageOps, ImageDraw, ImageFont

import sounddevice as sd
import pygame
from shazamio import Shazam


# -----------------------
# Config (tweak these)
# -----------------------
DEVICE = 1                 # sounddevice input device index
SAMPLE_RATE = 44100
CHANNELS = 1

RECORD_SECONDS = 5        # 6–9 is a good range
RECOGNIZE_EVERY_S = 7     # how often to attempt recognition while listening is ON
NETWORK_TIMEOUT_S = 6   

FULLSCREEN = True
FPS = 60

# Mode switching
IDLE_TO_SLIDESHOW_S = 12   # if no match for 12s, switch to slideshow (while listening is ON)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cache
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
SNIPPET_WAV_PATH = os.path.join(CACHE_DIR, "snippet.wav")
COVER_PATH = os.path.join(CACHE_DIR, "cover.jpg")

# Slideshow
SLIDESHOW_DIR = os.path.join(BASE_DIR, "slideshow")
SLIDESHOW_INTERVAL_S = 60  # change slide every N seconds


# -----------------------
# Clean split layout (Option A)
# -----------------------
# Fonts (Inter)
FONT_REG = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
FONT_SEMI = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

RIGHT_BG = (18, 18, 18)
TEXT_PRIMARY = (245, 245, 245)
TEXT_SECONDARY = (205, 205, 205)
TEXT_TERTIARY = (155, 155, 155)

SPLIT_OUTER = 32           # outer margin around content
SPLIT_GAP = 32             # gap between art and right column
SPLIT_ART_W_FRAC = 0.54    # cap art size by width fraction of screen
RIGHT_PAD = 56             # padding inside right panel
RIGHT_GAP = 18             # vertical rhythm

ROUNDED_RADIUS = 26
SHADOW_BLUR = 22
SHADOW_OFFSET = (0, 14)
SHADOW_ALPHA = 90

DOT_SIZE = 12

CROSSFADE_MS = 320         # subtle fade on track change (visual only)

# Touch UI overlay
OVERLAY_HIDE_AFTER_S = 4.0
BUTTON_W_RATIO = 0.28
BUTTON_H_RATIO = 0.09
BUTTON_MARGIN_RATIO = 0.03


# -----------------------
# Utilities
# -----------------------
def ensure_dirs():
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(SLIDESHOW_DIR, exist_ok=True)


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
    with open(SNIPPET_WAV_PATH, "wb") as f:
        f.write(wav_bytes)

    shazam = Shazam()
    try:
        return await shazam.recognize(SNIPPET_WAV_PATH)
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


def download_image_to_path(url: str, out_path: str) -> bool:
    try:
        r = requests.get(url, timeout=NETWORK_TIMEOUT_S)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
        return True
    except Exception:
        return False


def list_slideshow_images() -> List[str]:
    exts = (".jpg", ".jpeg", ".png", ".webp")
    if not os.path.isdir(SLIDESHOW_DIR):
        return []
    files = [os.path.join(SLIDESHOW_DIR, f) for f in os.listdir(SLIDESHOW_DIR)]
    files = [f for f in files if os.path.isfile(f) and f.lower().endswith(exts)]
    files.sort()
    return files


def pick_random_image(images: List[str], last_path: str) -> Optional[str]:
    if not images:
        return None
    if len(images) == 1:
        return images[0]
    choices = [p for p in images if p != last_path]
    return random.choice(choices) if choices else images[0]


def make_fullscreen_surface(img_path: str, screen_size: Tuple[int, int]) -> pygame.Surface:
    """Fit image to screen (cover/center crop)."""
    sw, sh = screen_size
    img = Image.open(img_path).convert("RGB")
    full = ImageOps.fit(img, (sw, sh), method=Image.LANCZOS, centering=(0.5, 0.5))
    return pygame.image.frombuffer(full.tobytes(), full.size, full.mode).convert()


def point_in_rect(pos, rect: pygame.Rect) -> bool:
    return rect.collidepoint(pos)


def draw_button(screen, rect: pygame.Rect, label: str, font, text_color, bg_alpha=140):
    # semi-transparent background
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    s.fill((0, 0, 0, bg_alpha))
    screen.blit(s, rect.topleft)

    pygame.draw.rect(screen, (255, 255, 255), rect, width=2, border_radius=18)

    txt = font.render(label, True, text_color)
    tx = rect.x + (rect.width - txt.get_width()) // 2
    ty = rect.y + (rect.height - txt.get_height()) // 2
    screen.blit(txt, (tx, ty))


# -----------------------
# Split-layout render helpers (PIL -> pygame)
# -----------------------
def rounded_image_rgba(img: Image.Image, radius: int) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask=mask)
    return out


def add_shadow_rgba(base: Image.Image, rect, radius, offset, blur, alpha) -> Image.Image:
    x, y, w, h = rect
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx = x + offset[0]
    sy = y + offset[1]
    sd.rounded_rectangle((sx, sy, sx + w, sy + h), radius=radius, fill=(0, 0, 0, alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(base, shadow)


def ellipsize_pil(text: str, font: ImageFont.FreeTypeFont, max_w: int, draw: ImageDraw.ImageDraw) -> str:
    if not text:
        return ""
    if draw.textlength(text, font=font) <= max_w:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    best = ell
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = text[:mid].rstrip() + ell
        if draw.textlength(cand, font=font) <= max_w:
            best = cand
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def pil_rgba_to_surface(img: Image.Image) -> pygame.Surface:
    img = img.convert("RGBA")
    return pygame.image.frombuffer(img.tobytes(), img.size, "RGBA")


def pick_accent_simple(img_rgb: Image.Image) -> Tuple[int, int, int]:
    # Simple, stable: sample a few points and pick the most saturated-ish
    img = img_rgb.convert("RGB").resize((64, 64))
    pts = [(32, 32), (16, 16), (48, 16), (16, 48), (48, 48)]
    best = (120, 180, 255)
    best_score = -1
    for x, y in pts:
        r, g, b = img.getpixel((x, y))
        l = 0.2126 * r + 0.7152 * g + 0.0722 * b
        if l < 35 or l > 220:
            continue
        c = max(r, g, b) - min(r, g, b)
        if c > best_score:
            best_score = c
            best = (r, g, b)
    return best


def make_split_nowplaying_surface(
    cover_path: str,
    screen_size: Tuple[int, int],
    title: str,
    artist: str,
    album: str,
) -> pygame.Surface:
    sw, sh = screen_size

    canvas = Image.new("RGBA", (sw, sh), RIGHT_BG + (255,))
    draw = ImageDraw.Draw(canvas)

    outer = SPLIT_OUTER
    gap = SPLIT_GAP

    art_size_by_h = sh - 2 * outer
    art_size_by_w = int(sw * SPLIT_ART_W_FRAC)
    art_size = max(240, min(art_size_by_h, art_size_by_w))  # keep sane minimum

    art_x = outer
    art_y = (sh - art_size) // 2

    right_x = art_x + art_size + gap
    right_w = sw - right_x
    right_pad = RIGHT_PAD

    # Load art, center-crop square, resize
    img0 = Image.open(cover_path).convert("RGB")
    w, h = img0.size
    m = min(w, h)
    img0 = img0.crop(((w - m) // 2, (h - m) // 2, (w - m) // 2 + m, (h - m) // 2 + m))
    img0 = img0.resize((art_size, art_size), Image.Resampling.LANCZOS)

    accent = pick_accent_simple(img0)

    # Shadow + rounded art
    canvas = add_shadow_rgba(
        canvas,
        (art_x, art_y, art_size, art_size),
        ROUNDED_RADIUS,
        SHADOW_OFFSET,
        SHADOW_BLUR,
        SHADOW_ALPHA,
    )
    # IMPORTANT: canvas is now a new image; recreate draw handle
    draw = ImageDraw.Draw(canvas)

    art_rounded = rounded_image_rgba(img0, ROUNDED_RADIUS)
    canvas.paste(art_rounded, (art_x, art_y), art_rounded)

    # Right panel block
    rp = Image.new("RGBA", (max(1, right_w), sh), RIGHT_BG + (255,))
    canvas.paste(rp, (right_x, 0))

    # Divider line
    draw.line((right_x, 0, right_x, sh), fill=(35, 35, 35, 255), width=2)

    # Fonts
    title_px = max(34, min(60, int(sh * 0.078)))
    artist_px = max(22, min(38, int(sh * 0.052)))
    meta_px = max(16, min(28, int(sh * 0.040)))
    kicker_px = max(14, min(20, int(sh * 0.032)))

    f_title = ImageFont.truetype(FONT_SEMI, size=title_px)
    f_artist = ImageFont.truetype(FONT_REG, size=artist_px)
    f_meta = ImageFont.truetype(FONT_REG, size=meta_px)
    f_kicker = ImageFont.truetype(FONT_SEMI, size=kicker_px)

    text_max_w = max(50, right_w - 2 * right_pad)
    x0 = right_x + right_pad

    kicker = "NOW PLAYING"
    title_fit = ellipsize_pil(title, f_title, text_max_w, draw)
    artist_fit = ellipsize_pil(artist, f_artist, text_max_w, draw)
    meta_fit = ellipsize_pil(album or "", f_meta, text_max_w, draw)

    def text_h(sample: str, font: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), sample, font=font)
        return bb[3] - bb[1]

    kicker_h = text_h("Ag", f_kicker)
    title_h = text_h("Ag", f_title)
    artist_h = text_h("Ag", f_artist)
    meta_h = text_h("Ag", f_meta)

    block_h = kicker_h + RIGHT_GAP + title_h + int(RIGHT_GAP * 0.8) + artist_h + int(RIGHT_GAP * 1.2) + meta_h
    y = (sh - block_h) // 2

    # Dot + kicker
    dot_r = DOT_SIZE // 2
    dot_cx = x0 + dot_r
    dot_cy = y + kicker_h // 2
    draw.ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill=accent + (255,))
    draw.text((x0 + DOT_SIZE + 12, y), kicker, font=f_kicker, fill=TEXT_TERTIARY + (255,))

    y += kicker_h + RIGHT_GAP
    draw.text((x0, y), title_fit, font=f_title, fill=TEXT_PRIMARY + (255,))
    y += title_h + int(RIGHT_GAP * 0.8)
    draw.text((x0, y), artist_fit, font=f_artist, fill=TEXT_SECONDARY + (255,))
    y += artist_h + int(RIGHT_GAP * 1.2)
    if meta_fit:
        draw.text((x0, y), meta_fit, font=f_meta, fill=TEXT_TERTIARY + (255,))

    return pil_rgba_to_surface(canvas)


def crossfade(screen: pygame.Surface, old: pygame.Surface, new: pygame.Surface, duration_ms: int):
    start = pygame.time.get_ticks()
    while True:
        now = pygame.time.get_ticks()
        t = (now - start) / max(1, duration_ms)
        if t >= 1.0:
            break
        old_a = int((1.0 - t) * 255)
        new_a = int(t * 255)

        screen.fill((0, 0, 0))

        o = old.copy()
        n = new.copy()
        o.set_alpha(old_a)
        n.set_alpha(new_a)

        screen.blit(o, (0, 0))
        screen.blit(n, (0, 0))

        pygame.display.flip()
        pygame.time.delay(16)


# -----------------------
# Shared state
# -----------------------
@dataclass
class AppState:
    listening_enabled: bool = True  # when False: no mic recording and no network calls
    mode: str = "listening"         # "nowplaying" / "listening" / "slideshow"

    title: str = ""
    artist: str = ""
    album: str = ""
    cover_url: str = ""
    cover_path: str = COVER_PATH

    last_update_ts: float = 0.0
    last_match_ts: float = 0.0


# -----------------------
# Recognizer thread
# -----------------------
class RecognizerThread(threading.Thread):
    def __init__(self, state: AppState, lock: threading.Lock):
        super().__init__(daemon=True)
        self.state = state
        self.lock = lock
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            with self.lock:
                enabled = self.state.listening_enabled

            # Listening disabled: do NOTHING (privacy + no upload)
            if not enabled:
                time.sleep(0.2)
                continue

            start = time.time()
            now_ts = time.time()

            try:
                wav_bytes = record_wav_bytes()
                res = asyncio.run(shazam_recognize_from_wav_bytes(wav_bytes))
                info = extract_track_info(res) if res else None

                if info:
                    title, artist, album, cover_url = info

                    art_ok = False
                    with self.lock:
                        prev_url = self.state.cover_url

                    if cover_url and cover_url != prev_url:
                        art_ok = download_image_to_path(cover_url, COVER_PATH)

                    with self.lock:
                        self.state.title = title
                        self.state.artist = artist
                        self.state.album = album or ""
                        self.state.cover_url = cover_url or ""
                        if art_ok:
                            self.state.cover_path = COVER_PATH

                        self.state.last_match_ts = now_ts
                        self.state.mode = "nowplaying"
                        self.state.last_update_ts = now_ts

                else:
                    # No match: keep "listening" briefly, then switch to slideshow
                    with self.lock:
                        if self.state.last_match_ts == 0:
                            self.state.last_match_ts = now_ts

                        if (now_ts - self.state.last_match_ts) >= IDLE_TO_SLIDESHOW_S:
                            if self.state.mode != "slideshow":
                                self.state.mode = "slideshow"
                                self.state.last_update_ts = now_ts
                        else:
                            if self.state.mode != "listening":
                                self.state.mode = "listening"
                                self.state.last_update_ts = now_ts

            except Exception:
                with self.lock:
                    if self.state.mode != "listening":
                        self.state.mode = "listening"
                        self.state.last_update_ts = time.time()

            elapsed = time.time() - start
            sleep_for = max(1.0, RECOGNIZE_EVERY_S - elapsed)
            for _ in range(int(sleep_for * 10)):
                if self._stop.is_set():
                    break
                time.sleep(0.1)


# -----------------------
# Main UI
# -----------------------
def main():
    ensure_dirs()

    pygame.init()
    pygame.font.init()
    pygame.display.set_caption("AuraFrame")

    # Fullscreen in the display's native mode (Wayland-friendly)
    if FULLSCREEN:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
    else:
        screen = pygame.display.set_mode((1280, 720))

    clock = pygame.time.Clock()
    sw, sh = screen.get_size()

    # Button font (pygame)
    button_font = pygame.font.SysFont("Arial", int(sh * 0.038), bold=True)

    # Overlay button geometry (top-right)
    btn_w = int(sw * BUTTON_W_RATIO)
    btn_h = int(sh * BUTTON_H_RATIO)
    btn_margin = int(min(sw, sh) * BUTTON_MARGIN_RATIO)
    button_rect = pygame.Rect(sw - btn_margin - btn_w, btn_margin, btn_w, btn_h)

    overlay_show = False
    overlay_visible_until = 0.0

    # State + thread
    state = AppState()
    lock = threading.Lock()
    recognizer = RecognizerThread(state, lock)
    recognizer.start()

    # Visual buffers
    np_surface = pygame.Surface((sw, sh), pygame.SRCALPHA)
    np_surface.fill((*RIGHT_BG, 255))
    last_np_rendered_ts = 0.0

    slide_full = pygame.Surface((sw, sh))
    slide_full.fill((0, 0, 0))
    slide_text_color = (240, 240, 240)

    slides = list_slideshow_images()
    current_slide = ""
    next_slide_at = 0.0

    last_mode = ""
    last_frame = None  # for crossfade
    running = True

    while running:
        now = time.time()

        # Auto-hide overlay
        if overlay_show and now > overlay_visible_until:
            overlay_show = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Tap anywhere to reveal overlay
                overlay_show = True
                overlay_visible_until = now + OVERLAY_HIDE_AFTER_S

                # Tap button to toggle listening
                if point_in_rect(event.pos, button_rect):
                    with lock:
                        state.listening_enabled = not state.listening_enabled
                        if not state.listening_enabled:
                            state.mode = "slideshow"
                            state.last_update_ts = time.time()
                        else:
                            state.mode = "listening"
                            state.last_match_ts = 0.0
                            state.last_update_ts = time.time()

        # Pull state snapshot
        with lock:
            mode = state.mode
            listening_enabled = state.listening_enabled
            title = state.title
            artist = state.artist
            album = state.album
            cover_path = state.cover_path
            ts = state.last_update_ts

        # Update split now-playing surface when new track arrives
        if mode == "nowplaying" and ts != 0.0 and ts != last_np_rendered_ts and os.path.exists(cover_path):
            try:
                new_np = make_split_nowplaying_surface(cover_path, (sw, sh), title, artist, album)

                # Crossfade only when we already have a previous frame
                if last_frame is not None:
                    crossfade(screen, last_frame, new_np, CROSSFADE_MS)

                np_surface = new_np
                last_frame = np_surface
                last_np_rendered_ts = ts
            except Exception:
                # If render fails for some reason, keep old surface
                pass

        # Slideshow progression
        if mode == "slideshow":
            if int(now) % 15 == 0:
                slides = list_slideshow_images()

            if now >= next_slide_at:
                nxt = pick_random_image(slides, current_slide)
                if nxt and os.path.exists(nxt):
                    try:
                        slide_full = make_fullscreen_surface(nxt, (sw, sh))
                        current_slide = nxt
                    except Exception:
                        slide_full.fill((0, 0, 0))
                        current_slide = ""
                else:
                    slide_full.fill((0, 0, 0))
                    current_slide = ""
                next_slide_at = now + SLIDESHOW_INTERVAL_S

        # Draw main
        if mode == "slideshow":
            screen.blit(slide_full, (0, 0))
        elif mode == "nowplaying":
            screen.blit(np_surface, (0, 0))
        else:
            # "listening" (minimal)
            screen.fill(RIGHT_BG)

            # Minimal hint top-right-ish
            hint = button_font.render("Listening…", True, (200, 200, 200))
            screen.blit(hint, (sw - hint.get_width() - int(sw * 0.04), int(sh * 0.06)))

        # Overlay button (only when user taps)
        if overlay_show:
            label = "Stop Listening" if listening_enabled else "Start Listening"
            # Keep overlay readable regardless of mode
            color = (240, 240, 240)
            draw_button(screen, button_rect, label, button_font, color, bg_alpha=140)

        pygame.display.flip()
        clock.tick(FPS)

        # If mode changed away from nowplaying, don't crossfade from stale last_frame
        if mode != last_mode:
            last_mode = mode
            if mode != "nowplaying":
                last_frame = None

    recognizer.stop()
    pygame.quit()


if __name__ == "__main__":
    main()

