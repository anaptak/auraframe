import os
import threading
import time

import pygame

from .audio import ensure_dirs
from .config import COVER_PATH, CROSSFADE_MS, FPS, FULLSCREEN, RIGHT_BG, SLIDESHOW_INTERVAL_S
from .imaging import (
    crossfade,
    list_slideshow_images,
    make_fullscreen_surface,
    make_split_nowplaying_surface,
    pick_random_image,
)
from .recognizer import RecognizerThread
from .state import AppState
from .ui import (
    draw_button,
    draw_listening_hint,
    overlay_deadline,
    overlay_geometry,
    overlay_should_hide,
    point_in_rect,
)


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
    button_rect = overlay_geometry((sw, sh))

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

    slides = list_slideshow_images()
    current_slide = ""
    next_slide_at = 0.0

    last_mode = ""
    last_frame = None  # for crossfade
    running = True

    while running:
        now = time.time()

        # Auto-hide overlay
        if overlay_show and overlay_should_hide(overlay_visible_until, now):
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
                overlay_visible_until = overlay_deadline(now)

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
            draw_listening_hint(screen, button_font, (sw, sh))

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
