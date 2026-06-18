import math

import pytest

from gps_classifier.motion import MotionConfig, MotionSimulator


def test_step_advances_position():
    sim = MotionSimulator(MotionConfig(start=(0.0, 0.0), seed=1))
    p0 = sim.pos
    p1 = sim.step(0.1)

    assert p1 != p0
    assert sim.t == pytest.approx(0.1)


def test_speed_varies_over_time():
    """Speed should not be identical across many ticks (non-constant motion)."""
    sim = MotionSimulator(MotionConfig(seed=2, speed_variation_period_s=5.0))

    speeds = []
    for _ in range(50):
        sim.step(0.1)
        speeds.append(sim.current_speed)

    assert len(set(round(s, 6) for s in speeds)) > 1


def test_speed_never_below_minimum():
    cfg = MotionConfig(seed=3, min_speed=0.2, speed_jitter_std=5.0)
    sim = MotionSimulator(cfg)

    for _ in range(100):
        sim.step(0.05)
        assert sim.current_speed >= cfg.min_speed


def test_reproducible_with_same_seed():
    sim1 = MotionSimulator(MotionConfig(seed=99))
    sim2 = MotionSimulator(MotionConfig(seed=99))

    for _ in range(20):
        p1 = sim1.step(0.1)
        p2 = sim2.step(0.1)
        assert p1 == pytest.approx(p2)


def test_invalid_dt_rejected():
    sim = MotionSimulator()
    with pytest.raises(ValueError):
        sim.step(0)
    with pytest.raises(ValueError):
        sim.step(-1)


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        MotionConfig(base_speed=0)
    with pytest.raises(ValueError):
        MotionConfig(min_speed=-1)
    with pytest.raises(ValueError):
        MotionConfig(speed_variation_period_s=0)
