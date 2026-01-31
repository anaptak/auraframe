import threading
import time

from .audio import download_image_to_path, recognize_track
from .config import COVER_PATH, IDLE_TO_SLIDESHOW_S, RECOGNIZE_EVERY_S
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
                            self.state.cover_path = str(COVER_PATH)

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
