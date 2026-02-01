import random
from typing import List, Optional, Tuple

import pygame
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .config import (
    DOT_SIZE,
    FONT_REG,
    FONT_SEMI,
    RIGHT_BG,
    RIGHT_GAP,
    RIGHT_PAD,
    ROUNDED_RADIUS,
    SHADOW_ALPHA,
    SHADOW_BLUR,
    SHADOW_OFFSET,
    SLIDESHOW_DIR,
    SPLIT_ART_W_FRAC,
    SPLIT_GAP,
    SPLIT_OUTER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
)


def list_slideshow_images() -> List[str]:
    exts = (".jpg", ".jpeg", ".png", ".webp")
    if not SLIDESHOW_DIR.is_dir():
        return []
    files = [path for path in SLIDESHOW_DIR.iterdir() if path.is_file() and path.suffix.lower() in exts]
    return sorted(str(path) for path in files)


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


def rounded_image_rgba(img: Image.Image, radius: int) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=radius, fill=255)
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


def wrap_text_lines(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_w: int,
    draw: ImageDraw.ImageDraw,
    max_lines: int,
) -> List[str]:
    if not text:
        return []
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    idx = 0
    while idx < len(words) and len(lines) < max_lines:
        line_words: List[str] = []
        while idx < len(words):
            candidate = " ".join(line_words + [words[idx]])
            if draw.textlength(candidate, font=font) <= max_w or not line_words:
                line_words.append(words[idx])
                idx += 1
            else:
                break
        line = " ".join(line_words)
        lines.append(line)
    if idx < len(words) and lines:
        remaining = " ".join([lines[-1]] + words[idx:])
        lines[-1] = ellipsize_pil(remaining, font, max_w, draw)
    cleaned = []
    for line in lines:
        if draw.textlength(line, font=font) > max_w:
            cleaned.append(ellipsize_pil(line, font, max_w, draw))
        else:
            cleaned.append(line)
    return cleaned


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
    year: str,
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

    def measure_text_width(text: str, font: ImageFont.FreeTypeFont) -> float:
        if not text:
            return 0.0
        return draw.textlength(text, font=font)

    base_title_px = max(38, min(68, int(sh * 0.085)))

    def scaled_title_px(title_text: str, has_subtitle: bool, max_width: int) -> int:
        base_px = base_title_px
        max_px = max(base_px, min(110, int(sh * 0.14)))
        if not title_text:
            return base_px

        target_fill = 0.88 * max_width
        step = 2
        best_px = base_px
        size = base_px
        max_lines = 2 if has_subtitle else 3
        while size <= max_px:
            font = ImageFont.truetype(FONT_SEMI, size=size)
            lines = wrap_text_lines(title_text, font, max_width, draw, max_lines=max_lines)
            if not lines:
                break
            max_line_w = max(measure_text_width(line, font) for line in lines)
            if max_line_w > max_width:
                break
            best_px = size
            if max_line_w >= target_fill:
                break
            size += step
        return best_px

    # Fonts
    title_px = base_title_px
    artist_px = max(24, min(42, int(sh * 0.056)))
    meta_px = max(18, min(30, int(sh * 0.042)))
    kicker_px = max(14, min(20, int(sh * 0.032)))

    text_max_w = max(50, right_w - 2 * right_pad)
    x0 = right_x + right_pad

    kicker = "NOW PLAYING"
    title_main = title
    subtitle = ""
    if title and title.endswith(")") and " (" in title:
        split_idx = title.rfind(" (")
        if split_idx > 0:
            title_main = title[:split_idx].strip()
            subtitle = title[split_idx + 1 :].strip()

    if subtitle:
        base_title_font = ImageFont.truetype(FONT_SEMI, size=title_px)
        title_lines_full = wrap_text_lines(title, base_title_font, text_max_w, draw, max_lines=2)
        if len(title_main) <= 12 and len(title_lines_full) <= 2:
            title_main = title
            subtitle = ""

    title_px = scaled_title_px(title_main, bool(subtitle), text_max_w)
    subtitle_px = max(24, min(title_px - 4, int(title_px * 0.82)))

    f_title = ImageFont.truetype(FONT_SEMI, size=title_px)
    f_title_sub = ImageFont.truetype(FONT_REG, size=subtitle_px)
    f_artist = ImageFont.truetype(FONT_REG, size=artist_px)
    f_meta = ImageFont.truetype(FONT_REG, size=meta_px)
    f_kicker = ImageFont.truetype(FONT_SEMI, size=kicker_px)
    title_lines = wrap_text_lines(title_main, f_title, text_max_w, draw, max_lines=2 if subtitle else 3)
    subtitle_lines = wrap_text_lines(subtitle, f_title_sub, text_max_w, draw, max_lines=1)
    artist_fit = ellipsize_pil(artist, f_artist, text_max_w, draw)
    meta_text = album or ""
    if year:
        meta_text = f"{meta_text} • {year}" if meta_text else str(year)
    meta_fit = ellipsize_pil(meta_text, f_meta, text_max_w, draw)

    def text_h(sample: str, font: ImageFont.FreeTypeFont) -> int:
        bb = draw.textbbox((0, 0), sample, font=font)
        return bb[3] - bb[1]

    kicker_h = text_h("Ag", f_kicker)
    title_h = text_h("Ag", f_title)
    subtitle_h = text_h("Ag", f_title_sub)
    artist_h = text_h("Ag", f_artist)
    meta_h = text_h("Ag", f_meta)
    title_gap = int(RIGHT_GAP * 0.4)
    title_to_artist_gap = int(RIGHT_GAP * 1.6)
    artist_to_meta_gap = int(RIGHT_GAP * 1.3)
    title_block_h = title_h * max(1, len(title_lines))
    if len(title_lines) > 1:
        title_block_h += title_gap * (len(title_lines) - 1)
    if subtitle_lines:
        title_block_h += title_gap + subtitle_h

    block_h = (
        kicker_h
        + RIGHT_GAP
        + title_block_h
        + title_to_artist_gap
        + artist_h
        + artist_to_meta_gap
        + meta_h
    )
    y = (sh - block_h) // 2

    # Dot + kicker
    dot_r = DOT_SIZE // 2
    dot_cx = x0 + dot_r
    dot_cy = y + kicker_h // 2
    draw.ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill=accent + (255,))
    draw.text((x0 + DOT_SIZE + 12, y), kicker, font=f_kicker, fill=TEXT_TERTIARY + (255,))

    y += kicker_h + RIGHT_GAP
    for idx, line in enumerate(title_lines or [""]):
        draw.text((x0, y), line, font=f_title, fill=TEXT_PRIMARY + (255,))
        y += title_h
        if idx < len(title_lines) - 1:
            y += title_gap
    if subtitle_lines:
        y += title_gap
        for line in subtitle_lines:
            draw.text((x0, y), line, font=f_title_sub, fill=TEXT_PRIMARY + (255,))
            y += subtitle_h
    y += title_to_artist_gap
    draw.text((x0, y), artist_fit, font=f_artist, fill=TEXT_SECONDARY + (255,))
    y += artist_h + artist_to_meta_gap
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
