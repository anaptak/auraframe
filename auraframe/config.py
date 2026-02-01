from pathlib import Path
from typing import List
import logging

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
IDLE_TO_SLIDESHOW_S = 12        # if no match for 12s and no known track, switch to slideshow
STALE_TRACK_TO_SLIDESHOW_S = 90 # if a known track is showing, wait longer before slideshow

BASE_DIR = Path(__file__).resolve().parents[1]

# Cache
CACHE_DIR = BASE_DIR / "data" / "cache"
SNIPPET_WAV_PATH = CACHE_DIR / "snippet.wav"
COVER_PATH = CACHE_DIR / "cover.jpg"

# Slideshow
SLIDESHOW_DIR = BASE_DIR / "slideshow"
SLIDESHOW_INTERVAL_S = 60  # change slide every N seconds


# -----------------------
# Clean split layout (Option A)
# -----------------------
# Fonts (Inter)
# Place Inter fonts in assets/fonts (see below), or adjust these paths.
# We explicitly load fonts from disk so the Pi doesn't silently fall back.
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
_FONT_LOG = logging.getLogger("auraframe.fonts")

FONT_DIR = BASE_DIR / "assets" / "fonts"
INTER_REGULAR = FONT_DIR / "Inter-Regular.ttf"
INTER_MEDIUM = FONT_DIR / "Inter-Medium.ttf"
INTER_VARIABLE = FONT_DIR / "Inter-VariableFont.ttf"
FALLBACK_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _resolve_font_path(label: str, candidates: List[Path], fallback: Path) -> str:
    attempted = [str(path.resolve()) for path in candidates]
    _FONT_LOG.info("%s font candidates: %s", label, attempted)
    for candidate in candidates:
        if candidate.is_file():
            resolved = str(candidate.resolve())
            _FONT_LOG.info("%s font loaded: %s", label, resolved)
            _FONT_LOG.info("%s font fallback used: %s", label, False)
            return resolved
    fallback_path = str(fallback.resolve())
    if fallback.is_file():
        _FONT_LOG.warning("%s font missing; falling back to %s", label, fallback_path)
        _FONT_LOG.info("%s font fallback used: %s", label, True)
        return fallback_path
    _FONT_LOG.warning("%s font missing and fallback unavailable; last attempt was %s", label, attempted[-1])
    _FONT_LOG.info("%s font fallback used: %s", label, True)
    return attempted[-1]


FONT_REG = _resolve_font_path(
    "Regular",
    [INTER_REGULAR, INTER_VARIABLE],
    FALLBACK_FONT,
)
FONT_MED = _resolve_font_path(
    "Medium",
    [INTER_MEDIUM, INTER_VARIABLE],
    FALLBACK_FONT,
)

RIGHT_BG = (12, 12, 12)
TEXT_PRIMARY = (235, 235, 235)
TEXT_SECONDARY = (200, 200, 200)
TEXT_TERTIARY = (150, 150, 150)

SPLIT_OUTER = 36           # outer margin around content
SPLIT_GAP = 46             # gap between art and right column
SPLIT_ART_W_FRAC = 0.54    # cap art size by width fraction of screen
RIGHT_PAD = 72             # padding inside right panel
RIGHT_GAP = 22             # vertical rhythm
TITLE_SIZE_BASE = 56       # fixed base title size (px)
TITLE_SIZE_MIN = 38        # minimum title size when scaling down
TITLE_SIZE_MAX = TITLE_SIZE_BASE  # never scale above base size
TITLE_BLOCK_MAX_RATIO = 0.26      # max title block height as fraction of screen
TITLE_TRACKING_PX = 1             # subtle tracking for large titles
TITLE_TRACKING_MIN_PX = 52        # only apply tracking above this size

ARTIST_SIZE = 30          # fixed sizes for metadata
META_SIZE = 22
KICKER_SIZE = 14

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
