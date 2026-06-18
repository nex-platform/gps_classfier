"""
sensors
=======

Implements the ``get_dist_a()`` / ``get_dist_b()`` sensor interface.

Per the assignment, these functions take **no inputs** - they report the
shortest signed distance from the sensor's *current* position (tracked
internally by a :class:`~gps_classifier.motion.MotionSimulator`) to the
boundary of region A / region B respectively.

:class:`SensorModule` binds a motion simulator and a pair of
:class:`~gps_classifier.region_config.RegionConfig` objects together, and
exposes ``get_dist_a`` / ``get_dist_b`` as zero-argument bound methods -
matching the required signature while avoiding hidden global state.
"""

from __future__ import annotations

import logging

from gps_classifier.geometry import signed_distance
from gps_classifier.motion import MotionSimulator
from gps_classifier.region_config import RegionConfig

logger = logging.getLogger(__name__)


class SensorModule:
    """
    Provides no-argument distance sensors backed by a shared motion
    simulator and region configuration.

    Args:
        motion: The motion simulator whose current position is read.
        region_a: Region A configuration.
        region_b: Region B configuration.
    """

    def __init__(
        self,
        motion: MotionSimulator,
        region_a: RegionConfig,
        region_b: RegionConfig,
    ) -> None:
        self._motion = motion
        self._region_a = region_a
        self._region_b = region_b

    def get_dist_a(self) -> float:
        """
        Return the signed shortest distance from the sensor's current
        position to the boundary of region A.

        Negative = inside A, positive = outside A, zero = on boundary.
        """
        dist = signed_distance(self._motion.pos, self._region_a)
        logger.debug("get_dist_a() -> %.6f (pos=%s)", dist, self._motion.pos)
        return dist

    def get_dist_b(self) -> float:
        """
        Return the signed shortest distance from the sensor's current
        position to the boundary of region B.

        Negative = inside B, positive = outside B, zero = on boundary.
        """
        dist = signed_distance(self._motion.pos, self._region_b)
        logger.debug("get_dist_b() -> %.6f (pos=%s)", dist, self._motion.pos)
        return dist
