from pathlib import Path

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
