"""
display
=======

Real-time presentation of simulation ticks.

Two presentation modes are provided:

* :class:`ConsoleDisplay` - prints one line per tick (always available,
  no extra dependencies).
* :class:`LivePlotDisplay` - a ``matplotlib`` animation showing the
  regions, the moving sensor, and the current classification (optional,
  requires ``matplotlib``).

Both display each tick's result immediately as it is produced - neither
buffers ticks for later rendering, satisfying the "no post-processing"
requirement.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from gps_classifier.classifier import RegionState

logger = logging.getLogger(__name__)


class ConsoleDisplay:
    """Prints a single formatted line per simulation tick to stdout."""

    def render(
        self,
        t: float,
        pos: tuple[float, float],
        dist_a: float,
        dist_b: float,
        state: RegionState,
    ) -> None:
        """Emit one line describing the current tick's state."""
        logger.info(
            "t=%6.2f pos=(%7.2f, %7.2f) dist_a=%7.2f dist_b=%7.2f -> %s",
            t,
            pos[0],
            pos[1],
            dist_a,
            dist_b,
            state.value,
        )


class LivePlotDisplay:
    """
    Live ``matplotlib`` view of the regions, sensor trail, and current
    classification.

    Requires ``matplotlib``. Import is deferred to construction time so
    that environments without ``matplotlib`` can still use
    :class:`ConsoleDisplay` without the dependency installed.
    """

    def __init__(
        self,
        region_a,
        region_b,
        history_len: int = 200,
        view_margin: float = 10.0,
        extra_points: Optional[Sequence[tuple[float, float]]] = None,
    ) -> None:
        try:
            import matplotlib
            matplotlib.use('TkAgg')
            import matplotlib.pyplot as plt

        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise ImportError(
                "LivePlotDisplay requires matplotlib. Install it with "
                "'pip install matplotlib' or use ConsoleDisplay instead."
            ) from exc

        self._plt = plt

        self._history_len = history_len
        self._xs: list[float] = []
        self._ys: list[float] = []

        self._fig, self._ax = plt.subplots(figsize=(6, 6))
        self._draw_region(region_a, "A", color="tab:blue")
        self._draw_region(region_b, "B", color="tab:orange")

        (self._trail_line,) = self._ax.plot([], [], "-", color="0.6", linewidth=1)
        (self._point,) = self._ax.plot([], [], "o", color="black", markersize=6)
        self._status_text = self._ax.text(
            0.02, 0.98, "", transform=self._ax.transAxes, va="top", fontsize=12
        )

        # Fix the view to the regions' combined extent (+ margin, + any
        # extra points such as motion waypoints) ONCE. Regions A and B are
        # static and must never appear to move, shrink, or grow as the
        # sensor moves - so the axes are never rescaled again after this
        # point (no relim()/autoscale_view() in render()).
        ax_min, ay_min, ax_max, ay_max = region_a.bounds
        bx_min, by_min, bx_max, by_max = region_b.bounds
        xs = [ax_min, ax_max, bx_min, bx_max]
        ys = [ay_min, ay_max, by_min, by_max]
        for px, py in extra_points or []:
            xs.append(px)
            ys.append(py)

        x_min = min(xs) - view_margin
        x_max = max(xs) + view_margin
        y_min = min(ys) - view_margin
        y_max = max(ys) + view_margin

        self._ax.set_xlim(x_min, x_max)
        self._ax.set_ylim(y_min, y_max)
        self._ax.set_aspect("equal", adjustable="box")
        self._ax.legend(loc="lower right")
        self._ax.set_title("GPS region classification (live)")
        plt.ion()
        plt.show(block=False)

    def _draw_region(self, region, label: str, color: str) -> None:
        x, y = region.geom.exterior.xy
        self._ax.fill(x, y, alpha=0.2, color=color, label=f"Region {label}")
        self._ax.plot(x, y, color=color, linewidth=1)

    def render(
        self,
        t: float,
        pos: tuple[float, float],
        dist_a: float,
        dist_b: float,
        state: RegionState,
    ) -> None:
        """Update the plot with the latest tick's data."""
        self._xs.append(pos[0])
        self._ys.append(pos[1])
        if len(self._xs) > self._history_len:
            self._xs.pop(0)
            self._ys.pop(0)

        # Colour the sensor dot by current classification state so it is
        # immediately obvious which region (or outside) the sensor is in.
        state_color = {
            RegionState.IN_A: "tab:blue",
            RegionState.IN_B: "tab:orange",
            RegionState.OUTSIDE: "black"
        }[state]

        self._trail_line.set_data(self._xs, self._ys)
        self._point.set_data([pos[0]], [pos[1]])
        self._point.set_color(state_color)
        self._status_text.set_text(
            f"t = {t:.2f}s\n"
            f"state  = {state.value}\n"
            f"dist_a = {dist_a:+.2f}\n"
            f"dist_b = {dist_b:+.2f}"
        )
        self._status_text.set_color(state_color)

        # NOTE: deliberately no relim()/autoscale_view() here - the axes
        # limits are fixed once in __init__ based on the static region
        # bounds. Autoscaling per-frame would resize the viewport as the
        # trail grows, making the fixed regions appear to shrink and drift
        # closer together even though their coordinates never change.
        self._fig.canvas.draw_idle()
        self._fig.canvas.flush_events()

    def close(self) -> None:
        """Close the plot window."""
        self._plt.close(self._fig)
