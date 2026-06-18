"""
motion
======

Generates a realistic 2D motion path for the simulated GPS sensor.

Two motion modes are supported:

* **Waypoint mode** (default when ``waypoints`` is set): the sensor steers
  toward a sequence of target points, cycling through them in order. This
  guarantees the trajectory visits every configured waypoint - e.g. inside
  region A, outside, inside region B, outside, repeat - so the
  classification demo actually exercises all three states (``In A``,
  ``In B``, ``Outside``) rather than relying on an undirected random walk
  that might never reach a small/far region within the simulated duration.

* **Free random-walk mode** (when ``waypoints`` is ``None`` or empty): the
  original undirected motion - heading drifts via Gaussian jitter only.

In both modes, *speed* still varies over time rather than being constant:

* a slow sinusoidal "cruise speed" drift (e.g. speeding up on a straight,
  slowing for a turn), plus
* small Gaussian jitter on speed (sensor/driver noise).

In waypoint mode, heading is computed as "bearing toward the current
target" plus a small Gaussian jitter, so the path still looks organic
(slight wobble) while remaining goal-directed.

The simulator is deterministic given a fixed ``seed``, which makes the
demo reproducible and testable.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from typing import Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class MotionConfig:
    """
    Tunable parameters controlling the generated path.

    Attributes:
        start: Initial (x, y) position.
        start_heading_rad: Initial heading, in radians. Used as-is in
            free random-walk mode; in waypoint mode it is only the
            starting heading before the first bearing correction.
        base_speed: Nominal cruise speed (distance units / second).
        speed_variation_amplitude: Fractional amplitude of the sinusoidal
            speed drift, relative to ``base_speed`` (e.g. 0.4 = +/-40%).
        speed_variation_period_s: Period, in seconds, of the sinusoidal
            speed drift.
        speed_jitter_std: Standard deviation of Gaussian noise added to
            speed each tick.
        heading_jitter_std: Standard deviation of Gaussian noise (radians)
            added to heading each tick - produces gentle, organic
            wobble/turns.
        min_speed: Speed is clamped to this minimum so the sensor never
            stops dead or reverses due to noise.
        seed: Seed for the internal RNG, for reproducibility.
        waypoints: Ordered list of (x, y) target points to cycle through.
            When set (non-empty), the sensor steers toward
            ``waypoints[0]``, then ``waypoints[1]``, ... looping back to
            ``waypoints[0]`` after the last one. When ``None`` or empty,
            the simulator falls back to free random-walk mode.
        waypoint_arrival_radius: Distance threshold for considering a
            waypoint "reached", at which point the simulator advances to
            the next one.
    """

    start: tuple[float, float] = (-2.0, -2.0)
    start_heading_rad: float = 0.0
    base_speed: float = 1.5
    speed_variation_amplitude: float = 0.4
    speed_variation_period_s: float = 30.0
    speed_jitter_std: float = 0.05
    heading_jitter_std: float = 0.05
    min_speed: float = 0.05
    seed: int = 42
    waypoints: Optional[Sequence[tuple[float, float]]] = None
    waypoint_arrival_radius: float = 0.5

    def __post_init__(self) -> None:
        if self.base_speed <= 0:
            raise ValueError("base_speed must be > 0")
        if self.min_speed <= 0:
            raise ValueError("min_speed must be > 0")
        if self.speed_variation_period_s <= 0:
            raise ValueError("speed_variation_period_s must be > 0")
        if self.waypoint_arrival_radius <= 0:
            raise ValueError("waypoint_arrival_radius must be > 0")
        if self.waypoints is not None and len(self.waypoints) == 0:
            raise ValueError("waypoints must be None or a non-empty sequence")


class MotionSimulator:
    """
    Stateful generator of the sensor's ground-truth (x, y) position.

    Call :meth:`step` once per simulation tick to advance the position by
    ``dt`` seconds.
    """

    def __init__(self, config: MotionConfig | None = None) -> None:
        self.config = config or MotionConfig()
        self._rng = random.Random(self.config.seed)

        self.t: float = 0.0
        self.pos: tuple[float, float] = self.config.start
        self.heading: float = self.config.start_heading_rad
        self.current_speed: float = self.config.base_speed
        self._waypoint_index: int = 0

        logger.debug(
            "MotionSimulator initialised: start=%s heading=%.4f base_speed=%.3f "
            "seed=%d waypoints=%s",
            self.pos,
            self.heading,
            self.config.base_speed,
            self.config.seed,
            self.config.waypoints,
        )

    @property
    def current_target(self) -> Optional[tuple[float, float]]:
        """The waypoint the sensor is currently steering toward, if any."""
        if not self.config.waypoints:
            return None
        return self.config.waypoints[self._waypoint_index]

    def _compute_speed(self) -> float:
        cfg = self.config
        omega = 2.0 * math.pi / cfg.speed_variation_period_s

        raw_speed = (
            cfg.base_speed * (1.0 + cfg.speed_variation_amplitude * math.sin(omega * self.t))
            + self._rng.gauss(0.0, cfg.speed_jitter_std)
        )

        speed = max(raw_speed, cfg.min_speed)
        if speed != raw_speed:
            logger.warning(
                "Speed clipped at t=%.3f: raw=%.4f -> %.4f (min_speed=%.3f)",
                self.t,
                raw_speed,
                speed,
                cfg.min_speed,
            )
        return speed

    def _update_heading_waypoint(self) -> None:
        """Steer heading toward the current waypoint, with small jitter,
        and advance to the next waypoint if the current one is reached."""
        cfg = self.config
        target = cfg.waypoints[self._waypoint_index]

        dx = target[0] - self.pos[0]
        dy = target[1] - self.pos[1]
        distance = math.hypot(dx, dy)

        if distance <= cfg.waypoint_arrival_radius:
            old_index = self._waypoint_index
            self._waypoint_index = (self._waypoint_index + 1) % len(cfg.waypoints)
            logger.debug(
                "Waypoint %d reached at t=%.3f pos=(%.3f, %.3f); next target -> "
                "waypoint %d %s",
                old_index,
                self.t,
                self.pos[0],
                self.pos[1],
                self._waypoint_index,
                cfg.waypoints[self._waypoint_index],
            )
            target = cfg.waypoints[self._waypoint_index]
            dx = target[0] - self.pos[0]
            dy = target[1] - self.pos[1]

        bearing = math.atan2(dy, dx)
        self.heading = bearing + self._rng.gauss(0.0, cfg.heading_jitter_std)

    def _update_heading_random_walk(self) -> None:
        self.heading += self._rng.gauss(0.0, self.config.heading_jitter_std)

    def step(self, dt: float) -> tuple[float, float]:
        """
        Advance the simulation by ``dt`` seconds and return the new
        ``(x, y)`` position.

        Args:
            dt: Time step in seconds. Must be > 0.

        Returns:
            The updated (x, y) position.
        """
        if dt <= 0:
            raise ValueError(f"dt must be > 0, got {dt}")

        cfg = self.config
        speed = self._compute_speed()

        if cfg.waypoints:
            self._update_heading_waypoint()
        else:
            self._update_heading_random_walk()

        dx = speed * math.cos(self.heading) * dt
        dy = speed * math.sin(self.heading) * dt
        self.pos = (self.pos[0] + dx, self.pos[1] + dy)
        self.current_speed = speed
        self.t += dt

        logger.debug(
            "step: t=%.3f speed=%.4f heading=%.4f pos=(%.4f, %.4f) target=%s",
            self.t,
            speed,
            self.heading,
            self.pos[0],
            self.pos[1],
            self.current_target,
        )
        return self.pos
