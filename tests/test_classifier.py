import logging

import pytest

from gps_classifier.classifier import RegionState, classify


@pytest.mark.parametrize(
    "dist_a, dist_b, expected",
    [
        (-1.0, 5.0, RegionState.IN_A),
        (5.0, -1.0, RegionState.IN_B),
        (3.0, 4.0, RegionState.OUTSIDE),
        (0.0, 4.0, RegionState.IN_A),   # on boundary of A counts as inside
        (4.0, 0.0, RegionState.IN_B),   # on boundary of B counts as inside
        (0.0, 0.0, RegionState.IN_A),   # both boundaries -> A wins (overlap warning)
    ],
)
def test_classify(dist_a, dist_b, expected):
    assert classify(dist_a, dist_b) == expected


def test_overlap_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="gps_classifier.classifier"):
        result = classify(-1.0, -1.0)

    assert result == RegionState.IN_A
    assert any("Overlap detected" in record.message for record in caplog.records)


def test_no_warning_for_normal_case(caplog):
    with caplog.at_level(logging.WARNING, logger="gps_classifier.classifier"):
        classify(1.0, -1.0)

    assert not any("Overlap detected" in record.message for record in caplog.records)
