"""
region_config
=============

Configurable region definitions for the GPS classifier.

Each region (A, B, ...) is described declaratively via :class:`RegionConfig`
- a shape type plus its parameters (center, radius, radii, or vertices).
The corresponding ``shapely`` geometry is built once at construction time
and reused for all subsequent distance queries.

To change region shape/size/position, edit the ``RegionConfig`` instances
(or the JSON/YAML config file loaded by :func:`load_regions_from_dict`) -
no changes to geometry, sensor, or classifier code are required.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from shapely.affinity import scale, translate
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

logger = logging.getLogger(__name__)

# Number of segments per quarter-turn used when approximating circles and
# ellipses as polygons. Higher = smoother boundary, more compute per
# distance query. 64 gives sub-millimetre approximation error at GPS scales.
DEFAULT_CIRCLE_RESOLUTION = 64


class ShapeType(str, Enum):
    """Supported region shapes."""

    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"


class RegionConfigError(ValueError):
    """Raised when a :class:`RegionConfig` is invalid or cannot be built."""


@dataclass(frozen=True)
class RegionConfig:
    """
    Declarative configuration for a single region.

    Exactly one of the following parameter sets must be provided,
    matching ``shape``:

    * ``ShapeType.CIRCLE``  -> ``center`` and ``radius``
    * ``ShapeType.ELLIPSE`` -> ``center`` and ``radii`` (rx, ry)
    * ``ShapeType.POLYGON`` -> ``vertices`` (>= 3 points)

    Attributes:
        name: Human-readable identifier, used in logs (e.g. "A", "B").
        shape: Which shape this region uses.
        center: (x, y) center point. Required for circle/ellipse.
        radius: Circle radius. Required for circle.
        radii: (rx, ry) semi-axes. Required for ellipse.
        vertices: Ordered list of (x, y) polygon vertices. Required for
            polygon. The polygon does not need to be explicitly closed.
        circle_resolution: Segments per quarter-turn for circle/ellipse
            polygon approximation.
        geom: The built ``shapely`` geometry (populated automatically in
            ``__post_init__`` and never reassigned afterwards - the region
            is static for the lifetime of the object).

    This class is frozen (immutable): once constructed, a region's shape,
    size, position, and derived geometry never change. Only the sensor's
    position moves during a simulation run; regions A and B are fixed.
    """

    name: str
    shape: ShapeType
    center: Optional[tuple[float, float]] = None
    radius: Optional[float] = None
    radii: Optional[tuple[float, float]] = None
    vertices: Optional[Sequence[tuple[float, float]]] = None
    circle_resolution: int = DEFAULT_CIRCLE_RESOLUTION

    geom: BaseGeometry = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # dataclass(frozen=True) disallows normal attribute assignment,
        # so __setattr__ is bypassed here - this is the *only* place
        # 'shape' and 'geom' are ever set. After this method returns, the
        # region's geometry is fixed for its lifetime.
        object.__setattr__(self, "shape", ShapeType(self.shape))
        object.__setattr__(self, "geom", self._build_geometry())
        self._validate_geometry()

    # ------------------------------------------------------------------
    # Geometry construction
    # ------------------------------------------------------------------
    def _build_geometry(self) -> BaseGeometry:
        if self.shape == ShapeType.CIRCLE:
            return self._build_circle()
        if self.shape == ShapeType.ELLIPSE:
            return self._build_ellipse()
        if self.shape == ShapeType.POLYGON:
            return self._build_polygon()

        # Defensive: ShapeType(...) above would already raise for unknown
        # values, but keep this for clarity / future-proofing.
        raise RegionConfigError(f"Unsupported shape type: {self.shape!r}")

    def _build_circle(self) -> BaseGeometry:
        if self.center is None or self.radius is None:
            raise RegionConfigError(
                f"Region '{self.name}': CIRCLE requires 'center' and 'radius'."
            )
        if self.radius <= 0:
            raise RegionConfigError(
                f"Region '{self.name}': 'radius' must be > 0, got {self.radius}."
            )

        return Point(self.center).buffer(
            self.radius, quad_segs=self.circle_resolution
        )

    def _build_ellipse(self) -> BaseGeometry:
        if self.center is None or self.radii is None:
            raise RegionConfigError(
                f"Region '{self.name}': ELLIPSE requires 'center' and 'radii'."
            )

        rx, ry = self.radii
        if rx <= 0 or ry <= 0:
            raise RegionConfigError(
                f"Region '{self.name}': 'radii' must both be > 0, got {self.radii}."
            )

        unit_circle = Point(0, 0).buffer(1, quad_segs=self.circle_resolution)
        ellipse = scale(unit_circle, xfact=rx, yfact=ry, origin=(0, 0))
        return translate(ellipse, xoff=self.center[0], yoff=self.center[1])

    def _build_polygon(self) -> BaseGeometry:
        if not self.vertices or len(self.vertices) < 3:
            raise RegionConfigError(
                f"Region '{self.name}': POLYGON requires at least 3 'vertices', "
                f"got {0 if not self.vertices else len(self.vertices)}."
            )

        return Polygon(self.vertices)

    # ------------------------------------------------------------------
    # Validation / repair
    # ------------------------------------------------------------------
    def _validate_geometry(self) -> None:
        if self.geom.is_valid:
            return

        reason = explain_validity(self.geom)
        logger.warning(
            "Region '%s' (%s) produced invalid geometry (%s); "
            "attempting buffer(0) repair.",
            self.name,
            self.shape.value,
            reason,
        )

        repaired = self.geom.buffer(0)
        if not repaired.is_valid or repaired.is_empty:
            raise RegionConfigError(
                f"Region '{self.name}' ({self.shape.value}) has invalid geometry "
                f"that could not be repaired: {reason}"
            )

        object.__setattr__(self, "geom", repaired)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return (minx, miny, maxx, maxy) bounding box of the region."""
        return self.geom.bounds


# ----------------------------------------------------------------------
# Config loading helpers (e.g. from JSON/YAML)
# ----------------------------------------------------------------------
def region_from_dict(name: str, data: dict) -> RegionConfig:
    """
    Build a :class:`RegionConfig` from a plain dict, typically loaded from
    a JSON or YAML configuration file.

    Expected keys depend on ``data["shape"]``:

    .. code-block:: json

        {"shape": "circle", "center": [0, 0], "radius": 5}
        {"shape": "ellipse", "center": [15, 5], "radii": [4, 2.5]}
        {"shape": "polygon", "vertices": [[0,0],[10,0],[10,6],[4,9],[0,6]]}

    Raises:
        RegionConfigError: if required keys are missing or values invalid.
    """
    try:
        shape = ShapeType(data["shape"])
    except KeyError as exc:
        raise RegionConfigError(f"Region '{name}': missing 'shape' key.") from exc
    except ValueError as exc:
        raise RegionConfigError(
            f"Region '{name}': unknown shape '{data.get('shape')}'."
        ) from exc

    kwargs: dict = {"name": name, "shape": shape}

    if shape in (ShapeType.CIRCLE, ShapeType.ELLIPSE):
        center = data.get("center")
        if center is not None:
            kwargs["center"] = tuple(center)
    if shape == ShapeType.CIRCLE:
        kwargs["radius"] = data.get("radius")
    if shape == ShapeType.ELLIPSE:
        radii = data.get("radii")
        if radii is not None:
            kwargs["radii"] = tuple(radii)
    if shape == ShapeType.POLYGON:
        vertices = data.get("vertices")
        if vertices is not None:
            kwargs["vertices"] = [tuple(v) for v in vertices]

    if "circle_resolution" in data:
        kwargs["circle_resolution"] = data["circle_resolution"]

    return RegionConfig(**kwargs)


# ----------------------------------------------------------------------
# Default configuration (used when no config file is supplied)
# ----------------------------------------------------------------------
def default_regions() -> tuple[RegionConfig, RegionConfig]:
    """
    Return the default Region A / Region B configuration used when the
    simulation is run without an external config file.

    Region A: circle centred at the origin.
    Region B: ellipse, disjoint from A.
    """
    region_a = RegionConfig(
        name="A",
        shape=ShapeType.CIRCLE,
        center=(0.0, 0.0),
        radius=5.0,
    )
    region_b = RegionConfig(
        name="B",
        shape=ShapeType.ELLIPSE,
        center=(15.0, 5.0),
        radii=(4.0, 2.5),
    )

    if region_a.geom.intersects(region_b.geom):
        logger.warning(
            "Default regions A and B are not disjoint - this violates the "
            "documented assumption that A and B never overlap."
        )

    return region_a, region_b


# ----------------------------------------------------------------------
# Trajectory helpers
# ----------------------------------------------------------------------
def build_default_waypoints(
    region_a: RegionConfig,
    region_b: RegionConfig,
    margin: float = 5.0,
) -> list[tuple[float, float]]:
    """
    Build a waypoint cycle that guarantees the sensor visits the interior
    of region A, an area outside both regions, the interior of region B,
    and another outside area - in that order, looping indefinitely.

    This is purely a function of the (static) region geometry, so it is
    computed once at startup and handed to
    :class:`~gps_classifier.motion.MotionConfig`.

    Args:
        region_a: Region A configuration.
        region_b: Region B configuration.
        margin: Extra distance (beyond each region's bounding box) used
            when picking the two "outside" waypoints, to make sure they
            are clearly outside both regions.

    Returns:
        ``[centroid_a, outside_1, centroid_b, outside_2]``
    """
    centroid_a = (region_a.geom.centroid.x, region_a.geom.centroid.y)
    centroid_b = (region_b.geom.centroid.x, region_b.geom.centroid.y)

    a_minx, a_miny, a_maxx, a_maxy = region_a.bounds
    b_minx, b_miny, b_maxx, b_maxy = region_b.bounds

    # "Outside 1": below-left of region A's bounding box.
    outside_1 = (a_minx - margin, a_miny - margin)

    # "Outside 2": above-right of region B's bounding box.
    outside_2 = (b_maxx + margin, b_maxy + margin)

    waypoints = [centroid_a, outside_1, centroid_b, outside_2]

    for label, point in zip(("centroid_a", "outside_1", "centroid_b", "outside_2"), waypoints):
        if region_a.geom.contains(Point(point)) and label not in ("centroid_a",):
            logger.warning("Waypoint %s=%s unexpectedly falls inside region A", label, point)
        if region_b.geom.contains(Point(point)) and label not in ("centroid_b",):
            logger.warning("Waypoint %s=%s unexpectedly falls inside region B", label, point)

    logger.debug("Default waypoints: %s", waypoints)
    return waypoints
