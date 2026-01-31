from typing import Tuple

import pygame

from .config import (
    BUTTON_H_RATIO,
    BUTTON_MARGIN_RATIO,
    BUTTON_W_RATIO,
    OVERLAY_HIDE_AFTER_S,
    RIGHT_BG,
)


def point_in_rect(pos, rect: pygame.Rect) -> bool:
    return rect.collidepoint(pos)


def draw_button(screen, rect: pygame.Rect, label: str, font, text_color, bg_alpha=140):
    # semi-transparent background
    surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    surface.fill((0, 0, 0, bg_alpha))
    screen.blit(surface, rect.topleft)

    pygame.draw.rect(screen, (255, 255, 255), rect, width=2, border_radius=18)

    txt = font.render(label, True, text_color)
    tx = rect.x + (rect.width - txt.get_width()) // 2
    ty = rect.y + (rect.height - txt.get_height()) // 2
    screen.blit(txt, (tx, ty))


def overlay_geometry(screen_size: Tuple[int, int]) -> pygame.Rect:
    sw, sh = screen_size
    btn_w = int(sw * BUTTON_W_RATIO)
    btn_h = int(sh * BUTTON_H_RATIO)
    btn_margin = int(min(sw, sh) * BUTTON_MARGIN_RATIO)
    return pygame.Rect(sw - btn_margin - btn_w, btn_margin, btn_w, btn_h)


def overlay_should_hide(overlay_visible_until: float, now: float) -> bool:
    return now > overlay_visible_until


def overlay_deadline(now: float) -> float:
    return now + OVERLAY_HIDE_AFTER_S


def draw_listening_hint(screen: pygame.Surface, font, screen_size: Tuple[int, int]) -> None:
    sw, sh = screen_size
    screen.fill(RIGHT_BG)
    hint = font.render("Listening…", True, (200, 200, 200))
    screen.blit(hint, (sw - hint.get_width() - int(sw * 0.04), int(sh * 0.06)))
