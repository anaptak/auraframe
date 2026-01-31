from dataclasses import dataclass

from .config import COVER_PATH


@dataclass
class AppState:
    listening_enabled: bool = True  # when False: no mic recording and no network calls
    mode: str = "listening"         # "nowplaying" / "listening" / "slideshow"

    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    cover_url: str = ""
    cover_path: str = COVER_PATH

    last_update_ts: float = 0.0
    last_match_ts: float = 0.0
