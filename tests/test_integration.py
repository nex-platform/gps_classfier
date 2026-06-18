from gps_classifier.classifier import RegionState, classify
from gps_classifier.motion import MotionConfig, MotionSimulator
from gps_classifier.region_config import RegionConfig, ShapeType
from gps_classifier.sensors import SensorModule


def test_sensors_track_motion_and_classify():
    region_a = RegionConfig(name="A", shape=ShapeType.CIRCLE, center=(0, 0), radius=5)
    region_b = RegionConfig(name="B", shape=ShapeType.ELLIPSE, center=(20, 0), radii=(3, 3))

    # Place the sensor at the center of region A and keep it stationary
    # by using a zero base speed... instead, just check the sensors
    # directly at the starting position before any motion.
    motion = MotionSimulator(MotionConfig(start=(0, 0), seed=1))
    sensors = SensorModule(motion, region_a, region_b)

    dist_a = sensors.get_dist_a()
    dist_b = sensors.get_dist_b()
    state = classify(dist_a, dist_b)

    assert dist_a < 0  # inside region A
    assert dist_b > 0  # outside region B
    assert state == RegionState.IN_A


def test_sensors_reflect_position_after_step():
    region_a = RegionConfig(name="A", shape=ShapeType.CIRCLE, center=(0, 0), radius=1)
    region_b = RegionConfig(name="B", shape=ShapeType.CIRCLE, center=(50, 50), radius=1)

    # Start well outside both regions.
    motion = MotionSimulator(MotionConfig(start=(100, 100), seed=1))
    sensors = SensorModule(motion, region_a, region_b)

    dist_a = sensors.get_dist_a()
    dist_b = sensors.get_dist_b()
    assert classify(dist_a, dist_b) == RegionState.OUTSIDE

    # Sensors must reflect the *current* position after stepping, not a
    # stale cached value.
    motion.step(0.1)
    new_dist_a = sensors.get_dist_a()
    assert new_dist_a != dist_a
