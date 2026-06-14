"""Игровая логика шариков: движение, инвентарь, смешивание цветов, зона удаления."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

ColorRGB = Tuple[int, int, int]
Vec2 = Tuple[float, float]


@dataclass
class Rect:
    """Прямоугольная область на экране."""

    x: float
    y: float
    width: float
    height: float

    def contains(self, px: float, py: float) -> bool:
        return (
            self.x <= px <= self.x + self.width
            and self.y <= py <= self.y + self.height
        )


@dataclass
class Ball:
    """Шарик на игровом поле или в инвентаре."""

    id: str
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: ColorRGB

    @classmethod
    def create(
        cls,
        x: float,
        y: float,
        color: ColorRGB,
        radius: float = 20.0,
        vx: float = 0.0,
        vy: float = 0.0,
    ) -> Ball:
        return cls(
            id=str(uuid.uuid4()),
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            radius=radius,
            color=color,
        )


def mix_colors(color_a: ColorRGB, color_b: ColorRGB) -> ColorRGB:
    """Смешивает два цвета как среднее арифметическое их RGB-компонент."""
    return (
        round((color_a[0] + color_b[0]) / 2),
        round((color_a[1] + color_b[1]) / 2),
        round((color_a[2] + color_b[2]) / 2),
    )


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _balls_overlap(a: Ball, b: Ball) -> bool:
    return _distance(a.x, a.y, b.x, b.y) < a.radius + b.radius


@dataclass
class GameConfig:
    """Настройки игрового поля и поведения шариков."""

    width: float = 800.0
    height: float = 600.0
    default_radius: float = 20.0
    suck_radius: float = 80.0
    suck_capture_distance: float = 18.0
    suck_pull_speed: float = 320.0
    delete_zone: Rect = field(
        default_factory=lambda: Rect(x=0.0, y=0.0, width=100.0, height=100.0)
    )
    max_inventory: int = 20
    merge_overlap_ratio: float = 0.85


@dataclass
class GameState:
    """
    Состояние игры: шарики на поле, инвентарь, зона удаления.

    Интерфейс должен вызывать методы update / suck / spit / spawn и читать
    balls, inventory, delete_zone для отрисовки.
    """

    config: GameConfig = field(default_factory=GameConfig)
    balls: List[Ball] = field(default_factory=list)
    inventory: List[Ball] = field(default_factory=list)

    @property
    def width(self) -> float:
        return self.config.width

    @property
    def height(self) -> float:
        return self.config.height

    @property
    def delete_zone(self) -> Rect:
        return self.config.delete_zone

    def spawn_ball(
        self,
        x: float,
        y: float,
        color: ColorRGB,
        radius: Optional[float] = None,
        vx: float = 0.0,
        vy: float = 0.0,
    ) -> Ball:
        """Создаёт шарик на поле."""
        ball = Ball.create(
            x=x,
            y=y,
            color=color,
            radius=radius or self.config.default_radius,
            vx=vx,
            vy=vy,
        )
        self.balls.append(ball)
        return ball

    def update(self, dt: float) -> None:
        """Один игровой тик: движение, отражение от стен, смешивание, удаление."""
        self._move_balls(dt)
        self._resolve_color_mixing()
        self._remove_balls_in_delete_zone()

    def suck(self, mouse_x: float, mouse_y: float, dt: float) -> Optional[Ball]:
        """
        Всасывает ближайший шарик в радиусе suck_radius.

        Шарик притягивается к курсору; при достаточной близости попадает в инвентарь.
        Возвращает шарик, попавший в инвентарь, или None если всасывание ещё идёт.
        """
        if len(self.inventory) >= self.config.max_inventory:
            return None

        target = self._find_suck_target(mouse_x, mouse_y)
        if target is None:
            return None

        dist = _distance(target.x, target.y, mouse_x, mouse_y)
        capture_dist = self.config.suck_capture_distance + target.radius * 0.3

        if dist <= capture_dist:
            self.balls.remove(target)
            target.vx = 0.0
            target.vy = 0.0
            self.inventory.append(target)
            return target

        if dist > 0:
            step = min(self.config.suck_pull_speed * dt, dist - capture_dist * 0.5)
            target.x += (mouse_x - target.x) / dist * step
            target.y += (mouse_y - target.y) / dist * step

        target.vx = 0.0
        target.vy = 0.0
        return None

    def spit(
        self,
        mouse_x: float,
        mouse_y: float,
        velocity: Vec2,
        inventory_index: int = -1,
    ) -> Optional[Ball]:
        """
        Выплёвывает шарик из инвентаря на поле.

        inventory_index: индекс в инвентаре (-1 — последний добавленный).
        velocity: (vx, vy) начальной скорости.
        """
        if not self.inventory:
            return None

        idx = inventory_index if inventory_index >= 0 else len(self.inventory) - 1
        if idx >= len(self.inventory):
            return None

        ball = self.inventory.pop(idx)
        ball.x = mouse_x
        ball.y = mouse_y
        ball.vx, ball.vy = velocity
        self.balls.append(ball)
        return ball

    def delete_from_inventory(self, index: int = -1) -> Optional[Ball]:
        """Удаляет шарик из инвентаря без возврата на поле."""
        if not self.inventory:
            return None
        idx = index if index >= 0 else len(self.inventory) - 1
        if idx >= len(self.inventory):
            return None
        return self.inventory.pop(idx)

    def ball_at(self, x: float, y: float) -> Optional[Ball]:
        """Возвращает верхний шарик в точке (для выбора UI)."""
        for ball in reversed(self.balls):
            if _distance(ball.x, ball.y, x, y) <= ball.radius:
                return ball
        return None

    def _move_balls(self, dt: float) -> None:
        w, h = self.config.width, self.config.height

        for ball in self.balls:
            ball.x += ball.vx * dt
            ball.y += ball.vy * dt

            if ball.x - ball.radius < 0:
                ball.x = ball.radius
                ball.vx = abs(ball.vx)
            elif ball.x + ball.radius > w:
                ball.x = w - ball.radius
                ball.vx = -abs(ball.vx)

            if ball.y - ball.radius < 0:
                ball.y = ball.radius
                ball.vy = abs(ball.vy)
            elif ball.y + ball.radius > h:
                ball.y = h - ball.radius
                ball.vy = -abs(ball.vy)

    def _resolve_color_mixing(self) -> None:
        """
        При касании шарики сливаются в один с новым цветом.

        Шарики не отталкиваются — физического разведения нет.
        """
        merged = True
        while merged:
            merged = False
            for i in range(len(self.balls)):
                for j in range(i + 1, len(self.balls)):
                    a, b = self.balls[i], self.balls[j]
                    if not _balls_overlap(a, b):
                        continue

                    overlap = (a.radius + b.radius) - _distance(a.x, a.y, b.x, b.y)
                    min_overlap = min(a.radius, b.radius) * self.config.merge_overlap_ratio
                    if overlap < min_overlap:
                        continue

                    self._merge_balls(a, b)
                    merged = True
                    break
                if merged:
                    break

    def _merge_balls(self, a: Ball, b: Ball) -> None:
        total_mass = a.radius ** 2 + b.radius ** 2
        if total_mass == 0:
            return

        new_x = (a.x * a.radius ** 2 + b.x * b.radius ** 2) / total_mass
        new_y = (a.y * a.radius ** 2 + b.y * b.radius ** 2) / total_mass
        new_vx = (a.vx * a.radius ** 2 + b.vx * b.radius ** 2) / total_mass
        new_vy = (a.vy * a.radius ** 2 + b.vy * b.radius ** 2) / total_mass
        new_radius = math.sqrt(a.radius ** 2 + b.radius ** 2)
        new_color = mix_colors(a.color, b.color)

        merged = Ball(
            id=str(uuid.uuid4()),
            x=new_x,
            y=new_y,
            vx=new_vx,
            vy=new_vy,
            radius=min(new_radius, max(self.config.width, self.config.height) * 0.15),
            color=new_color,
        )

        self.balls.remove(a)
        self.balls.remove(b)
        self.balls.append(merged)

    def _remove_balls_in_delete_zone(self) -> None:
        zone = self.config.delete_zone
        self.balls = [
            ball for ball in self.balls if not zone.contains(ball.x, ball.y)
        ]

    def _find_suck_target(self, mouse_x: float, mouse_y: float) -> Optional[Ball]:
        best: Optional[Ball] = None
        best_dist = self.config.suck_radius

        for ball in self.balls:
            dist = _distance(ball.x, ball.y, mouse_x, mouse_y)
            if dist <= self.config.suck_radius and dist < best_dist:
                best = ball
                best_dist = dist

        return best


def create_game(
    width: float = 800.0,
    height: float = 600.0,
    delete_zone: Optional[Rect] = None,
) -> GameState:
    """Фабрика начального состояния игры."""
    config = GameConfig(width=width, height=height)
    if delete_zone is not None:
        config.delete_zone = delete_zone
    return GameState(config=config)
