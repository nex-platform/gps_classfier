"""
logging_config
===============

Centralised logging setup for the GPS region classifier simulation.

The log level is configurable at execution time via:

* the ``--log-level`` command line argument, or
* the ``GPS_SIM_LOG_LEVEL`` environment variable (used if ``--log-level``
  is not supplied), or
* falling back to ``INFO`` if neither is set.

Levels are used as follows throughout the package:

============  ================================================================
Level         Meaning in this application
============  ================================================================
DEBUG         Fine-grained internals: per-tick speed/heading, raw geometry
              distance computations, individual sensor reads.
INFO          Per-tick summary: position, dist_a, dist_b, classification.
WARNING       Recoverable anomalies: clipped speed, region overlap detected,
              geometry auto-repair (buffer(0) fix).
ERROR         Unrecoverable configuration/runtime errors (e.g. invalid shape
              type, invalid geometry that cannot be repaired).
============  ================================================================
"""

from __future__ import annotations

import logging
import os
import sys

from gps_classifier.projectpaths import paths
from datetime import datetime

_DEFAULT_LEVEL = "INFO"
_VALID_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-7s] %(name)-12s %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def resolve_log_level(cli_level: str | None = None) -> str:
    """
    Resolve the effective log level from (in order of precedence):

    1. ``cli_level`` (e.g. parsed from ``--log-level``)
    2. the ``GPS_SIM_LOG_LEVEL`` environment variable
    3. the default ``INFO``

    Raises:
        ValueError: if the resolved level string is not a recognised
            logging level.
    """
    level = cli_level or os.environ.get("GPS_SIM_LOG_LEVEL") or _DEFAULT_LEVEL
    level = level.upper()

    if level not in _VALID_LEVELS:
        raise ValueError(
            f"Invalid log level '{level}'. Must be one of: {', '.join(_VALID_LEVELS)}"
        )
    return level

def get_exact_log_file_dir():
    now = datetime.now()
    log_dir = paths.get_logs_dir() / now.strftime("%Y_%m_%d") / now.strftime("%I_%M_%S_%p")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def setup_logging(cli_level: str | None = None) -> str:
    """
    Configure the root logger for the simulation.

    Args:
        cli_level: Optional log level string from the CLI. If ``None``,
            falls back to the ``GPS_SIM_LOG_LEVEL`` environment variable,
            then to ``INFO``.

    Returns:
        The effective log level name that was applied.
    """

    level_name = resolve_log_level(cli_level)
    numeric_level = getattr(logging, level_name)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.handlers.clear()

    #console Logging
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)

    #file Logging
    for level in _VALID_LEVELS:
        current_handler_level = getattr(logging, level)
        if current_handler_level >= numeric_level:
            handler = logging.FileHandler(get_exact_log_file_dir() / f"{level.lower()}.log", mode='w')
            handler.setLevel(current_handler_level)
            handler.addFilter(lambda record, lvl=level: record.levelname == lvl)
            handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
            root.addHandler(handler)

    logging.getLogger(__name__).debug("Logging configured at level %s", level_name)
    return level_name



def set_runtime_log_level(level_name: str) -> None:
    """
    Change the effective log level while the simulation is running.

    Intended for use by an operator-facing control (e.g. a keypress
    handler or a config-file watcher) that allows adjusting verbosity
    mid-run without restarting the process.

    Raises:
        ValueError: if ``level_name`` is not a recognised logging level.
    """
    level_name = level_name.upper()
    if level_name not in _VALID_LEVELS:
        raise ValueError(
            f"Invalid log level '{level_name}'. Must be one of: {', '.join(_VALID_LEVELS)}"
        )

    numeric_level = getattr(logging, level_name)
    logging.getLogger().setLevel(numeric_level)
    logging.getLogger(__name__).info("Log level changed to %s at runtime", level_name)
