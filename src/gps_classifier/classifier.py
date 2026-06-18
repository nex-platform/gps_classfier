"""
classifier
==========

Run-time classification of sensor position as ``In A``, ``In B``, or
``Outside``, based on the signed distances returned by
``get_dist_a()`` / ``get_dist_b()``.

The classifier is a pure, stateless function: given the two signed
distances, it returns a :class:`RegionState` with no side effects and no
dependency on history - satisfying the "no post-processing" requirement
(each tick is classified independently and immediately).
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class RegionState(str, Enum):
    """Possible run-time classification results."""

    IN_A = "In A"
    IN_B = "In B"
    OUTSIDE = "Outside"
    ON_BOUNDARY_A = "On Perimeter of A "
    ON_BOUNDARY_B = "On Perimeter of B "


def classify(dist_a: float, dist_b: float) -> RegionState:
    """
    Classify the current position based on signed distances to regions
    A and B.

    Args:
        dist_a: Signed distance to region A's boundary
            (negative = inside A).
        dist_b: Signed distance to region B's boundary
            (negative = inside B).

    Returns:
        :class:`RegionState.IN_A` if inside (or on the boundary of) A,
        :class:`RegionState.IN_B` if inside (or on the boundary of) B,
        otherwise :class:`RegionState.OUTSIDE`.

    Note:
        Regions A and B are assumed disjoint. If both ``dist_a <= 0`` and
        ``dist_b <= 0`` simultaneously (which should not happen under that
        assumption), a warning is logged and A takes precedence - this
        keeps the function total (always returns a result) rather than
        raising, since classification must never block the real-time loop.
    """
    in_a = dist_a <= 0.0
    in_b = dist_b <= 0.0

    if in_a and in_b:
        logger.warning(
            "Overlap detected: dist_a=%.6f dist_b=%.6f both <= 0; "
            "regions assumed disjoint. Defaulting to IN_A.",
            dist_a,
            dist_b,
        )
        return RegionState.IN_A

    if in_a:
        return RegionState.IN_A
    if in_b:
        return RegionState.IN_B
    return RegionState.OUTSIDE
