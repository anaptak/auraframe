import threading
import time

from .audio import download_image_to_path, recognize_track
from .config import COVER_PATH, IDLE_TO_SLIDESHOW_S, RECOGNIZE_EVERY_S, STALE_TRACK_TO_SLIDESHOW_S
from .state import AppState


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
                info = recognize_track()

                if info:
                    title, artist, album, year, cover_url = info

                    art_ok = False
                    with self.lock:
                        prev_url = self.state.cover_url
                        prev_title = self.state.title
                        prev_artist = self.state.artist
                        prev_album = self.state.album
                        prev_year = self.state.year
                        prev_mode = self.state.mode

                    if cover_url and cover_url != prev_url:
                        art_ok = download_image_to_path(cover_url, COVER_PATH)

                    with self.lock:
                        next_album = album or ""
                        next_year = year or ""
                        next_cover_url = cover_url or ""

                        content_changed = any(
                            [
                                title != prev_title,
                                artist != prev_artist,
                                next_album != prev_album,
                                next_year != prev_year,
                                next_cover_url != prev_url,
                            ]
                        )
                        mode_changed = prev_mode != "nowplaying"

                        if content_changed or mode_changed:
                            self.state.title = title
                            self.state.artist = artist
                            self.state.album = next_album
                            self.state.year = next_year
                            self.state.cover_url = next_cover_url
                            if art_ok:
                                self.state.cover_path = str(COVER_PATH)
                            self.state.mode = "nowplaying"
                            self.state.last_update_ts = now_ts

                        self.state.last_match_ts = now_ts

                else:
                    # No match: keep "listening" briefly, then switch to slideshow
                    with self.lock:
                        has_known_track = bool(self.state.title or self.state.artist)
                        should_keep_nowplaying = self.state.mode == "nowplaying" or has_known_track
                        if self.state.last_match_ts == 0:
                            self.state.last_match_ts = now_ts

                        idle_limit = STALE_TRACK_TO_SLIDESHOW_S if has_known_track else IDLE_TO_SLIDESHOW_S
                        if (now_ts - self.state.last_match_ts) >= idle_limit:
                            if self.state.mode != "slideshow":
                                self.state.mode = "slideshow"
                                self.state.last_update_ts = now_ts
                        elif should_keep_nowplaying:
                            if self.state.mode != "nowplaying":
                                self.state.mode = "nowplaying"
                                self.state.last_update_ts = now_ts
                        else:
                            if self.state.mode != "listening":
                                self.state.mode = "listening"
                                self.state.last_update_ts = now_ts

            except Exception:
                with self.lock:
                    now_ts = time.time()
                    has_known_track = bool(self.state.title or self.state.artist)
                    should_keep_nowplaying = self.state.mode == "nowplaying" or has_known_track
                    if self.state.last_match_ts == 0:
                        self.state.last_match_ts = now_ts

                    idle_limit = STALE_TRACK_TO_SLIDESHOW_S if has_known_track else IDLE_TO_SLIDESHOW_S
                    if (now_ts - self.state.last_match_ts) >= idle_limit:
                        if self.state.mode != "slideshow":
                            self.state.mode = "slideshow"
                            self.state.last_update_ts = now_ts
                    elif should_keep_nowplaying:
                        if self.state.mode != "nowplaying":
                            self.state.mode = "nowplaying"
                            self.state.last_update_ts = now_ts
                    else:
                        if self.state.mode != "listening":
                            self.state.mode = "listening"
                            self.state.last_update_ts = now_ts

            elapsed = time.time() - start
            sleep_for = max(1.0, RECOGNIZE_EVERY_S - elapsed)
            for _ in range(int(sleep_for * 10)):
                if self._stop.is_set():
                    break
                time.sleep(0.1)
