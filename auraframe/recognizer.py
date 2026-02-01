import logging
import threading
import time

from .audio import download_image_to_path, recognize_track
from .canonical import CanonicalReleaseCache, build_candidate, resolve_canonical_release
from .config import (
    COVER_PATH,
    ENABLE_ALT_METADATA_LOOKUP,
    IDLE_TO_SLIDESHOW_S,
    RECOGNIZE_EVERY_S,
    RELEASE_UPGRADE_WINDOW_S,
    STALE_TRACK_TO_SLIDESHOW_S,
)
from .state import AppState

LOG = logging.getLogger("auraframe.recognizer")


class RecognizerThread(threading.Thread):
    def __init__(self, state: AppState, lock: threading.Lock):
        super().__init__(daemon=True)
        self.state = state
        self.lock = lock
        self._stop = threading.Event()
        self._canonical_cache = CanonicalReleaseCache()
        self._current_choice_key = ""
        self._current_choice_score = None
        self._current_choice_ts = 0.0
        self._current_choice_upgraded = False

    def _alternate_candidates(self, primary: dict) -> list:
        if not ENABLE_ALT_METADATA_LOOKUP:
            return []
        LOG.info("Alternate metadata lookup is enabled, but no providers are configured.")
        return []

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
                    primary = build_candidate(
                        title,
                        artist,
                        album,
                        year,
                        cover_url,
                        provider="shazam",
                    )
                    alternates = self._alternate_candidates(primary)
                    best_release, best_score = resolve_canonical_release(
                        primary,
                        alternates=alternates,
                        cache=self._canonical_cache,
                    )

                    key = CanonicalReleaseCache.make_key(
                        best_release.get("artist") or artist,
                        best_release.get("title") or title,
                    )
                    if key != self._current_choice_key:
                        self._current_choice_key = key
                        self._current_choice_score = None
                        self._current_choice_ts = now_ts
                        self._current_choice_upgraded = False

                    should_accept = self._current_choice_score is None
                    if not should_accept:
                        is_better = best_score > (self._current_choice_score or 0.0)
                        within_upgrade_window = (now_ts - self._current_choice_ts) <= RELEASE_UPGRADE_WINDOW_S
                        if (
                            is_better
                            and within_upgrade_window
                            and not self._current_choice_upgraded
                        ):
                            should_accept = True
                            self._current_choice_upgraded = True

                    art_ok = False
                    with self.lock:
                        prev_url = self.state.cover_url
                        prev_title = self.state.title
                        prev_artist = self.state.artist
                        prev_album = self.state.album
                        prev_year = self.state.year
                        prev_mode = self.state.mode

                    if should_accept:
                        self._current_choice_score = best_score
                        self._current_choice_ts = now_ts
                        title = best_release.get("title") or title
                        artist = best_release.get("artist") or artist
                        album = best_release.get("album") or album
                        year = best_release.get("year") or year
                        cover_url = best_release.get("cover_url") or cover_url
                    else:
                        title = prev_title
                        artist = prev_artist
                        album = prev_album
                        year = prev_year
                        cover_url = prev_url

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
