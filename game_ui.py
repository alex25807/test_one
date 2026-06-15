"""Графический интерфейс игры про шарики."""

from __future__ import annotations

import math
import random
import sys
from typing import List, Optional, Tuple

import pygame

from logic import ColorRGB, GameState, Rect, create_game

# --- Настройки игры (редактируйте здесь) ---

START_BALL_COUNT = 12
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FPS = 60

DELETE_ZONE_SIZE = 100
SPIT_SPEED = 280.0
MIN_SPIT_SPEED = 120.0

START_COLORS: List[ColorRGB] = [
    (230, 60, 60),
    (60, 130, 230),
    (60, 200, 90),
    (240, 180, 40),
    (180, 60, 210),
    (40, 200, 200),
]

# --- Цвета интерфейса ---

WHITE = (255, 255, 255)
BG_COLOR = WHITE
DELETE_ZONE_FILL = (255, 230, 230)
DELETE_ZONE_BORDER = (220, 80, 80)
DELETE_ZONE_TEXT = (180, 50, 50)
SUCK_RING_COLOR = (100, 150, 255, 60)
SUCK_RING_BORDER = (80, 130, 230)
INVENTORY_BG = (245, 245, 245)
INVENTORY_BORDER = (210, 210, 210)
HINT_COLOR = (130, 130, 130)
BALL_OUTLINE = (40, 40, 40, 40)


def _random_velocity(speed_range: Tuple[float, float] = (80.0, 180.0)) -> Tuple[float, float]:
    angle = random.uniform(0, 2 * math.pi)
    speed = random.uniform(*speed_range)
    return math.cos(angle) * speed, math.sin(angle) * speed


def _random_position(margin: float) -> Tuple[float, float]:
    return (
        random.uniform(margin, WINDOW_WIDTH - margin),
        random.uniform(margin, WINDOW_HEIGHT - margin),
    )


def _spawn_initial_balls(game: GameState, count: int) -> None:
    margin = game.config.default_radius + DELETE_ZONE_SIZE + 10
    for i in range(count):
        color = START_COLORS[i % len(START_COLORS)]
        x, y = _random_position(margin)
        vx, vy = _random_velocity()
        game.spawn_ball(x, y, color, vx=vx, vy=vy)


def _draw_ball(surface: pygame.Surface, x: float, y: float, radius: float, color: ColorRGB) -> None:
    ix, iy = int(x), int(y)
    ir = max(2, int(radius))

    shadow = pygame.Surface((ir * 2 + 4, ir * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(shadow, (0, 0, 0, 35), (ir + 2, ir + 3), ir)
    surface.blit(shadow, (ix - ir - 2, iy - ir - 2))

    pygame.draw.circle(surface, color, (ix, iy), ir)
    highlight = (
        min(255, color[0] + 50),
        min(255, color[1] + 50),
        min(255, color[2] + 50),
    )
    pygame.draw.circle(surface, highlight, (ix - ir // 3, iy - ir // 3), max(2, ir // 4))
    pygame.draw.circle(surface, (30, 30, 30), (ix, iy), ir, 1)


def _draw_delete_zone(surface: pygame.Surface, zone: Rect, font: pygame.font.Font) -> None:
    rect = pygame.Rect(int(zone.x), int(zone.y), int(zone.width), int(zone.height))
    pygame.draw.rect(surface, DELETE_ZONE_FILL, rect)
    pygame.draw.rect(surface, DELETE_ZONE_BORDER, rect, 2)

    label = font.render("Удалить", True, DELETE_ZONE_TEXT)
    surface.blit(label, (rect.x + 10, rect.y + 10))

    cx, cy = rect.centerx, rect.centery + 8
    pygame.draw.line(surface, DELETE_ZONE_BORDER, (cx - 14, cy - 10), (cx + 14, cy + 10), 3)
    pygame.draw.line(surface, DELETE_ZONE_BORDER, (cx - 14, cy + 10), (cx + 14, cy - 10), 3)


def _draw_suck_radius(
    surface: pygame.Surface,
    mx: int,
    my: int,
    radius: float,
    target_x: Optional[float],
    target_y: Optional[float],
) -> None:
    overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(overlay, SUCK_RING_COLOR, (mx, my), int(radius))
    pygame.draw.circle(overlay, (*SUCK_RING_BORDER, 180), (mx, my), int(radius), 2)
    surface.blit(overlay, (0, 0))

    if target_x is not None and target_y is not None:
        pygame.draw.line(
            surface,
            SUCK_RING_BORDER,
            (mx, my),
            (int(target_x), int(target_y)),
            2,
        )


def _draw_inventory_bar(
    surface: pygame.Surface,
    game: GameState,
    font: pygame.font.Font,
) -> None:
    bar_height = 56
    bar_y = WINDOW_HEIGHT - bar_height
    bar_rect = pygame.Rect(0, bar_y, WINDOW_WIDTH, bar_height)
    pygame.draw.rect(surface, INVENTORY_BG, bar_rect)
    pygame.draw.line(surface, INVENTORY_BORDER, (0, bar_y), (WINDOW_WIDTH, bar_y), 2)

    label = font.render(f"Инвентарь ({len(game.inventory)}/{game.config.max_inventory})", True, HINT_COLOR)
    surface.blit(label, (12, bar_y + 8))

    slot_x = 160
    slot_y = bar_y + 28
    slot_spacing = 34
    preview_radius = 12

    for i, ball in enumerate(game.inventory):
        _draw_ball(surface, slot_x + i * slot_spacing, slot_y, preview_radius, ball.color)


def _draw_hud(surface: pygame.Surface, font: pygame.font.Font, ball_count: int) -> None:
    hints = [
        f"Шариков на поле: {ball_count}",
        "ЛКМ — всасывать | ПКМ — выпустить (направление = движение мыши)",
    ]
    for i, text in enumerate(hints):
        rendered = font.render(text, True, HINT_COLOR)
        surface.blit(rendered, (WINDOW_WIDTH - rendered.get_width() - 12, 8 + i * 18))


class BallGameApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Шарики")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 16)
        self.small_font = pygame.font.SysFont("segoeui", 14)

        delete_zone = Rect(
            x=0.0,
            y=0.0,
            width=float(DELETE_ZONE_SIZE),
            height=float(DELETE_ZONE_SIZE),
        )
        self.game = create_game(WINDOW_WIDTH, WINDOW_HEIGHT, delete_zone=delete_zone)
        _spawn_initial_balls(self.game, START_BALL_COUNT)

        self.mouse_down_pos: Optional[Tuple[int, int]] = None
        self.running = True

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.mouse_down_pos = event.pos
                elif event.button == 3:
                    self.mouse_down_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:
                    self._spit_ball(event.pos)
                    self.mouse_down_pos = None
                elif event.button == 1:
                    self.mouse_down_pos = None

    def _update(self, dt: float) -> None:
        mouse_buttons = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()

        if mouse_buttons[0]:
            self.game.suck(float(mx), float(my), dt)

        self.game.update(dt)

    def _spit_ball(self, release_pos: Tuple[int, int]) -> None:
        if not self.game.inventory:
            return

        mx, my = release_pos
        if self.mouse_down_pos is not None:
            dx = mx - self.mouse_down_pos[0]
            dy = my - self.mouse_down_pos[1]
        else:
            dx, dy = 1.0, 0.0

        length = math.hypot(dx, dy)
        if length < 5:
            dx, dy = _random_velocity((MIN_SPIT_SPEED, MIN_SPIT_SPEED))
            length = math.hypot(dx, dy)

        speed = max(MIN_SPIT_SPEED, min(SPIT_SPEED, length * 8))
        vx = dx / length * speed
        vy = dy / length * speed

        self.game.spit(float(mx), float(my), (vx, vy))

    def _draw(self) -> None:
        self.screen.fill(BG_COLOR)

        _draw_delete_zone(self.screen, self.game.delete_zone, self.small_font)

        for ball in self.game.balls:
            _draw_ball(self.screen, ball.x, ball.y, ball.radius, ball.color)

        mouse_buttons = pygame.mouse.get_pressed()
        if mouse_buttons[0]:
            mx, my = pygame.mouse.get_pos()
            target = self.game._find_suck_target(float(mx), float(my))
            target_pos = (target.x, target.y) if target else None
            _draw_suck_radius(
                self.screen,
                mx,
                my,
                self.game.config.suck_radius,
                target_pos[0] if target_pos else None,
                target_pos[1] if target_pos else None,
            )

        _draw_inventory_bar(self.screen, self.game, self.small_font)
        _draw_hud(self.screen, self.font, len(self.game.balls))

        pygame.display.flip()


def main() -> None:
    app = BallGameApp()
    app.run()


if __name__ == "__main__":
    main()
    sys.exit(0)
