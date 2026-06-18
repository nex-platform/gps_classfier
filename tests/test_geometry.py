import math

import pytest

from gps_classifier.geometry import signed_distance
from gps_classifier.region_config import RegionConfig, RegionConfigError, ShapeType


class TestCircle:
    def setup_method(self):
        self.region = RegionConfig(name="A", shape=ShapeType.CIRCLE, center=(0, 0), radius=5)

    def test_center_is_inside(self):
        d = signed_distance((0, 0), self.region)
        assert d == pytest.approx(-5.0, abs=1e-2)

    def test_point_outside(self):
        d = signed_distance((10, 0), self.region)
        assert d == pytest.approx(5.0, abs=1e-2)

    def test_point_on_boundary(self):
        d = signed_distance((5, 0), self.region)
        assert d == pytest.approx(0.0, abs=1e-2)

    def test_point_well_inside(self):
        d = signed_distance((1, 0), self.region)
        assert d == pytest.approx(-4.0, abs=1e-2)


class TestEllipse:
    def setup_method(self):
        self.region = RegionConfig(
            name="B", shape=ShapeType.ELLIPSE, center=(15, 5), radii=(4, 2.5)
        )

    def test_center_is_inside(self):
        d = signed_distance((15, 5), self.region)
        assert d < 0

    def test_far_point_is_outside(self):
        d = signed_distance((100, 100), self.region)
        assert d > 0

    def test_translation_applied(self):
        # A point at the un-translated ellipse's center (origin) should be
        # outside, since the ellipse was translated to (15, 5).
        d = signed_distance((0, 0), self.region)
        assert d > 0


class TestPolygon:
    def setup_method(self):
        self.region = RegionConfig(
            name="C",
            shape=ShapeType.POLYGON,
            vertices=[(0, 0), (10, 0), (10, 10), (0, 10)],
        )

    def test_center_is_inside(self):
        d = signed_distance((5, 5), self.region)
        assert d == pytest.approx(-5.0, abs=1e-6)

    def test_outside_point(self):
        d = signed_distance((20, 20), self.region)
        assert d == pytest.approx(math.hypot(10, 10), abs=1e-6)

    def test_vertex_is_on_boundary(self):
        d = signed_distance((0, 0), self.region)
        assert d == pytest.approx(0.0, abs=1e-6)


class TestRegionConfigValidation:
    def test_circle_requires_radius(self):
        with pytest.raises(RegionConfigError):
            RegionConfig(name="A", shape=ShapeType.CIRCLE, center=(0, 0))

    def test_circle_rejects_nonpositive_radius(self):
        with pytest.raises(RegionConfigError):
            RegionConfig(name="A", shape=ShapeType.CIRCLE, center=(0, 0), radius=0)

    def test_ellipse_requires_radii(self):
        with pytest.raises(RegionConfigError):
            RegionConfig(name="B", shape=ShapeType.ELLIPSE, center=(0, 0))

    def test_polygon_requires_three_vertices(self):
        with pytest.raises(RegionConfigError):
            RegionConfig(name="C", shape=ShapeType.POLYGON, vertices=[(0, 0), (1, 1)])

    def test_unknown_shape_rejected(self):
        with pytest.raises(ValueError):
            RegionConfig(name="X", shape="triangle", vertices=[(0, 0), (1, 0), (0, 1)])
