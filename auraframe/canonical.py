import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .config import CACHE_DIR

LOG = logging.getLogger("auraframe.canonical")

# Heuristics: penalize compilation/low-quality releases, prefer clean official titles,
# and stabilize choices via caching + limited in-cycle upgrades.
SUSPICIOUS_TOKENS = [
    "presents",
    "best of",
    "greatest",
    "hits",
    "collection",
    "compilation",
    "karaoke",
    "tribute",
    "cover",
    "made famous by",
    "originally performed by",
    "various artists",
    "soundtrack",
    "theme",
    "instrumental",
    "relaxing",
    "study",
    "sleep",
    "background",
    "music presents",
    "bd music",
]

ALLOWLIST_OVERRIDES = [
    {"artist": "miles davis", "track": "so what", "album": "Kind of Blue"},
]

OFFICIAL_PROVIDERS = {"shazam"}
EP_SINGLE_TOKENS = {"ep", "single"}

YEAR_SUFFIX_RE = re.compile(r"\s*[-(]\s*(19|20)\d{2}\s*\)?\s*$")

CACHE_PATH = CACHE_DIR / "canonical_release_cache.json"
CACHE_TTL_S = 14 * 24 * 60 * 60
CACHE_BONUS = 200.0


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def build_candidate(
    title: Optional[str],
    artist: Optional[str],
    album: Optional[str],
    year: Optional[str],
    cover_url: Optional[str],
    provider: str,
) -> Dict[str, Optional[str]]:
    return {
        "title": title or "",
        "artist": artist or "",
        "album": album or "",
        "year": year or "",
        "cover_url": cover_url or "",
        "provider": provider,
    }


def _has_ep_or_single(album: str) -> bool:
    album_norm = normalize_text(album)
    return any(token in album_norm.split() for token in EP_SINGLE_TOKENS)


def _is_official(provider: Optional[str]) -> bool:
    return (provider or "").lower() in OFFICIAL_PROVIDERS


def _allowlist_bonus(preferred: Dict[str, str], album: str) -> float:
    preferred_artist = normalize_text(preferred.get("artist"))
    preferred_track = normalize_text(preferred.get("title"))
    album_norm = normalize_text(album)
    for entry in ALLOWLIST_OVERRIDES:
        allowlist_album = normalize_text(entry["album"])
        if (
            preferred_artist == entry["artist"]
            and preferred_track == entry["track"]
            and album_norm == allowlist_album
        ):
            return 120.0
    return 0.0


def _suspicious_tokens(album: str) -> List[str]:
    album_norm = normalize_text(album)
    return [token for token in SUSPICIOUS_TOKENS if token in album_norm]


def _has_suspicious_tokens(album: str) -> bool:
    return bool(_suspicious_tokens(album))


def _apply_allowlist_override(
    candidate: Dict[str, Optional[str]],
    preferred: Dict[str, str],
    logger: logging.Logger = LOG,
) -> Dict[str, Optional[str]]:
    preferred_artist = normalize_text(preferred.get("artist"))
    preferred_track = normalize_text(preferred.get("title"))
    if not preferred_artist or not preferred_track:
        return candidate
    album = candidate.get("album") or ""
    album_norm = normalize_text(album)
    for entry in ALLOWLIST_OVERRIDES:
        if preferred_artist == entry["artist"] and preferred_track == entry["track"]:
            canonical_album = entry["album"]
            canonical_norm = normalize_text(canonical_album)
            if album_norm != canonical_norm and canonical_norm in album_norm:
                logger.info(
                    "Allowlist override: forcing album '%s' for '%s' - '%s'",
                    canonical_album,
                    candidate.get("artist") or "",
                    candidate.get("title") or "",
                )
                updated = dict(candidate)
                updated["album"] = canonical_album
                return updated
    return candidate


def score_release(
    candidate: Dict[str, Optional[str]],
    preferred: Dict[str, str],
    has_non_ep: bool,
    logger: logging.Logger = LOG,
) -> float:
    album = candidate.get("album") or ""
    album_norm = normalize_text(album)
    score = 0.0

    if not album:
        score -= 30.0

    tokens = _suspicious_tokens(album)
    if tokens:
        logger.info("Rejecting suspicious tokens %s in album '%s'", tokens, album)
        score -= 40.0 * len(tokens)

    if YEAR_SUFFIX_RE.search(album):
        score -= 12.0

    if has_non_ep and _has_ep_or_single(album):
        score -= 15.0

    length_penalty = min(len(album), 80) / 20.0
    score -= length_penalty
    score += max(0.0, 40.0 - len(album)) / 10.0

    preferred_artist = normalize_text(preferred.get("artist"))
    candidate_artist = normalize_text(candidate.get("artist"))
    if preferred_artist and candidate_artist:
        if preferred_artist == candidate_artist:
            score += 20.0
        else:
            score -= 10.0

    if _is_official(candidate.get("provider")):
        score += 10.0

    score += _allowlist_bonus(preferred, album)

    return score


def choose_best_release(
    candidates: Iterable[Dict[str, Optional[str]]],
    preferred: Optional[Dict[str, str]] = None,
    logger: logging.Logger = LOG,
) -> Tuple[Dict[str, Optional[str]], float]:
    candidate_list = [candidate for candidate in candidates if candidate]
    if not candidate_list:
        return {}, 0.0

    preferred_info = preferred or candidate_list[0]
    candidate_list = [
        _apply_allowlist_override(candidate, preferred_info, logger=logger)
        for candidate in candidate_list
    ]
    has_non_ep = any(not _has_ep_or_single(c.get("album") or "") for c in candidate_list)

    best = candidate_list[0]
    best_score = float("-inf")
    for candidate in candidate_list:
        score = score_release(candidate, preferred_info, has_non_ep, logger=logger)
        logger.info("Candidate album '%s' score=%.2f", candidate.get("album") or "", score)
        if score > best_score:
            best = candidate
            best_score = score

    return best, best_score


@dataclass
class CanonicalReleaseCache:
    path: Path = CACHE_PATH
    ttl_s: int = CACHE_TTL_S

    def __post_init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache = self._load()

    @staticmethod
    def make_key(artist: str, title: str) -> str:
        return f"{normalize_text(artist)}::{normalize_text(title)}"

    def _load(self) -> Dict[str, dict]:
        if not self.path.exists():
            return {"version": 1, "entries": {}}
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict):
                return {"version": 1, "entries": {}}
            data.setdefault("version", 1)
            data.setdefault("entries", {})
            if not isinstance(data["entries"], dict):
                data["entries"] = {}
            return data
        except Exception:
            return {"version": 1, "entries": {}}

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self._cache, indent=2, sort_keys=True))
        except Exception:
            LOG.warning("Failed to write canonical cache to %s", self.path)

    def get(self, artist: str, title: str) -> Optional[Dict[str, Optional[str]]]:
        key = self.make_key(artist, title)
        entry = self._cache["entries"].get(key)
        if not entry:
            return None
        timestamp = entry.get("timestamp") or 0
        if time.time() - timestamp > self.ttl_s:
            self._cache["entries"].pop(key, None)
            self._save()
            return None
        LOG.info("Using cached canonical release for %s", key)
        return entry.get("candidate")

    def set(self, artist: str, title: str, candidate: Dict[str, Optional[str]]) -> None:
        key = self.make_key(artist, title)
        self._cache["entries"][key] = {
            "timestamp": time.time(),
            "candidate": candidate,
        }
        self._save()


def resolve_canonical_release(
    primary: Dict[str, Optional[str]],
    alternates: Optional[List[Dict[str, Optional[str]]]] = None,
    cache: Optional[CanonicalReleaseCache] = None,
    logger: logging.Logger = LOG,
) -> Tuple[Dict[str, Optional[str]], float]:
    artist = primary.get("artist") or ""
    title = primary.get("title") or ""
    use_cache = cache and (artist or title)
    cached = cache.get(artist, title) if use_cache else None
    if cached and not _has_suspicious_tokens(cached.get("album") or ""):
        score = score_release(cached, primary, has_non_ep=True, logger=logger) + CACHE_BONUS
        return cached, score

    candidates = [primary]
    if alternates:
        candidates.extend([c for c in alternates if c])

    best, best_score = choose_best_release(candidates, preferred=primary, logger=logger)
    if use_cache and not _has_suspicious_tokens(best.get("album") or ""):
        cache.set(artist, title, best)
    return best, best_score


if __name__ == "__main__":
    primary = build_candidate(
        "So What",
        "Miles Davis",
        "BD Music Presents Kind of Blue - 1959",
        "1959",
        "",
        "shazam",
    )
    alternate = build_candidate("So What", "Miles Davis", "Kind of Blue", "1959", "", "shazam")

    best_release, best_score = choose_best_release([primary, alternate], preferred=primary)
    print("Best album:", best_release.get("album"))
    print("Score:", best_score)
