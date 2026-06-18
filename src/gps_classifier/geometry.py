"""
geometry
========

Signed-distance-to-boundary computation, backed by ``shapely``.

Convention (matches ``get_dist_a`` / ``get_dist_b`` semantics):

* negative  -> point is *inside* the region, magnitude = distance to boundary
* zero      -> point is exactly on the boundary
* positive  -> point is *outside* the region, magnitude = distance to boundary

This module is intentionally free of any simulation state - it operates
purely on a point and a :class:`~gps_classifier.region_config.RegionConfig`,
which makes it trivial to unit test independently of the motion simulator.
"""

from __future__ import annotations

import logging

from shapely.geometry import MultiPolygon, Point, Polygon

from gps_classifier.region_config import RegionConfig

logger = logging.getLogger(__name__)


def signed_distance(point_xy: tuple[float, float], region: RegionConfig) -> float:
    """
    Compute the signed shortest distance from ``point_xy`` to the boundary
    of ``region``.

    Args:
        point_xy: (x, y) coordinates of the point to test.
        region: The region configuration whose ``geom`` defines the area.

    Returns:
        Signed distance as described in the module docstring.
    """
    pt = Point(point_xy)
    geom = region.geom

    boundary_distance = _boundary_distance(pt, geom)
    inside = geom.contains(pt)


    if boundary_distance == 0.0:
        signed = 0.0
    elif inside:
        signed = -boundary_distance
    else:
        signed = boundary_distance

    logger.debug(
        "signed_distance: region=%s shape=%s point=%s -> %.6f (inside=%s)",
        region.name,
        region.shape.value,
        point_xy,
        signed,
        inside,
    )
    return signed


def _boundary_distance(pt: Point, geom) -> float:
    """
    Distance from ``pt`` to the boundary of ``geom``, regardless of whether
    ``geom`` is a single :class:`Polygon` or a :class:`MultiPolygon`.

    ``Polygon.exterior`` is not defined for ``MultiPolygon``, so this
    dispatches to ``geom.boundary`` in that case, which works for both.
    """
    if isinstance(geom, Polygon):
        return geom.exterior.distance(pt)
    if isinstance(geom, MultiPolygon):
        return geom.boundary.distance(pt)

    # Generic fallback for any other shapely geometry type.
    return geom.boundary.distance(pt)
