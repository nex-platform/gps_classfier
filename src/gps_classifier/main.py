"""
main
====

Command-line entry point for the real-time GPS region classification
simulation.

Wires together:

* :class:`~gps_classifier.motion.MotionSimulator` - generates the sensor's
  ground-truth position with a variable-speed parametric path.
* :class:`~gps_classifier.sensors.SensorModule` - exposes
  ``get_dist_a()`` / ``get_dist_b()``.
* :func:`~gps_classifier.classifier.classify` - turns the two distances
  into ``In A`` / ``In B`` / ``Outside``.
* A display (:class:`~gps_classifier.display.ConsoleDisplay` or
  :class:`~gps_classifier.display.LivePlotDisplay`) - presents each tick
  immediately.

Usage:

.. code-block:: bash

    python -m gps_classifier.main
    python -m gps_classifier.main --log-level DEBUG --duration 30
    python -m gps_classifier.main --plot
    python -m gps_classifier.main --config configs/regions.json
    GPS_SIM_LOG_LEVEL=WARNING python -m gps_classifier.main
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from gps_classifier.classifier import classify
from gps_classifier.logging_config import setup_logging
from gps_classifier.motion import MotionConfig, MotionSimulator
from gps_classifier.region_config import (
    RegionConfigError,
    build_default_waypoints,
    default_regions,
    region_from_dict,
)
from gps_classifier.sensors import SensorModule

logger = logging.getLogger("gps_classifier.main")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Real-time GPS region classification simulation."
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=(
            "Logging verbosity. Defaults to the GPS_SIM_LOG_LEVEL "
            "environment variable, or INFO if that is also unset."
        ),
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Total simulated duration in seconds (default: 60).",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.1,
        help="Simulation tick size in seconds (default: 0.1).",
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        default=True,
        help="Pace ticks to wall-clock time using time.sleep (default: on).",
    )
    parser.add_argument(
        "--no-realtime",
        dest="realtime",
        action="store_false",
        help="Run as fast as possible, without sleeping between ticks.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Show a live matplotlib plot in addition to console output.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to a JSON file with 'region_a' and 'region_b' keys "
            "(see configs/regions.example.json). If omitted, built-in "
            "default regions are used."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override the motion simulator's RNG seed.",
    )
    return parser


def load_regions(config_path: Path | None):
    """
    Load region A / B configuration from ``config_path`` if given,
    otherwise fall back to built-in defaults.

    Raises:
        RegionConfigError: if the config file is malformed.
    """
    if config_path is None:
        logger.info("No --config supplied; using default regions.")
        return default_regions()

    logger.info("Loading region configuration from %s", config_path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise RegionConfigError(f"Could not read config file '{config_path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RegionConfigError(f"Invalid JSON in config file '{config_path}': {exc}") from exc

    try:
        region_a = region_from_dict("A", data["region_a"])
        region_b = region_from_dict("B", data["region_b"])
    except KeyError as exc:
        raise RegionConfigError(
            f"Config file '{config_path}' must contain both 'region_a' and 'region_b' keys."
        ) from exc

    if region_a.geom.intersects(region_b.geom):
        logger.warning(
            "Configured regions A and B are not disjoint - this violates the "
            "documented assumption that A and B never overlap."
        )

    return region_a, region_b


def run(args: argparse.Namespace) -> int:
    """
    Run the simulation loop until ``args.duration`` seconds of simulated
    time have elapsed. Returns a process exit code (0 = success).
    """
    try:
        region_a, region_b = load_regions(args.config)
    except RegionConfigError:
        logger.exception("Failed to load region configuration")
        return 1

    waypoints = build_default_waypoints(region_a, region_b)
    motion_config = MotionConfig(
        start=waypoints[0],  # start inside region A, not at arbitrary (-2,-2)
        waypoints=waypoints,
        seed=args.seed if args.seed is not None else 42,
    )

    motion = MotionSimulator(motion_config)
    sensors = SensorModule(motion, region_a, region_b)

    from gps_classifier.display import ConsoleDisplay

    displays = [ConsoleDisplay()]

    if args.plot:
        try:
            from gps_classifier.display import LivePlotDisplay

            displays.append(LivePlotDisplay(region_a, region_b, extra_points=waypoints))
        except ImportError:
            logger.warning("--plot requested but matplotlib is not installed; skipping.")

    logger.info(
        "Starting simulation: duration=%.1fs dt=%.3fs realtime=%s seed=%d waypoints=%s",
        args.duration,
        args.dt,
        args.realtime,
        motion_config.seed,
        waypoints,
    )

    t = 0.0
    try:
        while t < args.duration:
            pos = motion.step(args.dt)
            dist_a = sensors.get_dist_a()
            dist_b = sensors.get_dist_b()
            state = classify(dist_a, dist_b)

            for display in displays:
                display.render(t, pos, dist_a, dist_b, state)

            if args.realtime:
                time.sleep(args.dt)
            t += args.dt
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user.")
    finally:
        for display in displays:
            close = getattr(display, "close", None)
            if close:
                close()

    logger.info("Simulation finished at t=%.2fs", t)
    return 0


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    setup_logging(args.log_level)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
