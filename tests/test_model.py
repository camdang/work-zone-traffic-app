"""Unit tests for app.model — work-zone traffic calculations."""

import pytest
from app.model import compute_capacity, compute_delay, compute_sensitivity


# --- Task 1: Capacity calculation ---


def test_capacity_basic():
    """3 normal lanes, 1 closed, 1400 wz cap → 2 × 1400 = 2800."""
    assert compute_capacity(3, 1, 1400.0) == 2800.0


def test_capacity_no_closure():
    """3 normal lanes, 0 closed, 1400 wz cap → 3 × 1400 = 4200."""
    assert compute_capacity(3, 0, 1400.0) == 4200.0


def test_capacity_all_closed():
    """3 normal lanes, 3 closed → raises ValueError."""
    with pytest.raises(ValueError):
        compute_capacity(3, 3, 1400.0)


# --- Task 2: No-queue case ---


def test_no_queue_delay():
    """Demand below capacity: delay from speed reduction only."""
    result = compute_delay(
        normal_lanes=3,
        lanes_closed=1,
        demand=2000.0,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
    )
    assert result["queue_forms"] is False
    assert result["max_queue_vehicles"] == 0.0
    assert result["max_queue_miles"] == 0.0
    expected_delay = (2.0 / 45.0 - 2.0 / 65.0) * 60.0
    assert abs(result["avg_delay_per_vehicle"] - expected_delay) < 0.01


def test_demand_equals_capacity():
    """Demand exactly equals capacity: no queue forms (boundary)."""
    result = compute_delay(
        normal_lanes=3,
        lanes_closed=1,
        demand=2800.0,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
    )
    assert result["queue_forms"] is False
    assert result["max_queue_vehicles"] == 0.0


# --- Task 3: Over-capacity queueing ---


def test_over_capacity_basic():
    """Demand=4000, capacity=2800, duration=8h — queue grows linearly."""
    result = compute_delay(
        normal_lanes=3,
        lanes_closed=1,
        demand=4000.0,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
    )
    assert result["queue_forms"] is True
    assert result["max_queue_vehicles"] == pytest.approx(9600.0)
    assert result["max_queue_miles"] == pytest.approx(64.0)
    total_arrivals = 4000.0 * 8.0
    expected_total_delay = sum(
        (1200.0 * t + 1200.0 * (t + 1)) / 2.0 for t in range(8)
    )
    expected_avg_delay = (expected_total_delay / total_arrivals) * 60.0
    assert result["avg_delay_per_vehicle"] == pytest.approx(expected_avg_delay, rel=1e-6)


def test_queue_over_time_shape():
    """Queue values at each hour: [0, 1200, 2400, ..., 9600]."""
    result = compute_delay(
        normal_lanes=3,
        lanes_closed=1,
        demand=4000.0,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
    )
    expected = [1200.0 * t for t in range(9)]
    assert len(result["queue_over_time"]) == 9
    for actual, exp in zip(result["queue_over_time"], expected):
        assert actual == pytest.approx(exp)


# --- Task 4: Edge cases ---


def test_zero_demand():
    """Zero demand: no queue, zero delay, no crash."""
    result = compute_delay(
        normal_lanes=3,
        lanes_closed=1,
        demand=0.0,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
    )
    assert result["queue_forms"] is False
    assert result["max_queue_vehicles"] == 0.0
    expected_delay = (2.0 / 45.0 - 2.0 / 65.0) * 60.0
    assert result["avg_delay_per_vehicle"] == pytest.approx(expected_delay)
    assert result["total_delay_veh_hours"] == 0.0


def test_minimum_duration():
    """Duration=0.5h with over-capacity gives proportional results."""
    result = compute_delay(
        normal_lanes=3,
        lanes_closed=1,
        demand=4000.0,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=0.5,
    )
    assert result["queue_forms"] is True
    assert result["max_queue_vehicles"] == pytest.approx(600.0)
    assert result["max_queue_miles"] == pytest.approx(600.0 / 150.0)


def test_wz_speed_equals_posted():
    """Work-zone speed = posted speed, demand < capacity → zero delay."""
    result = compute_delay(
        normal_lanes=3,
        lanes_closed=1,
        demand=2000.0,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=65.0,
        analysis_duration=8.0,
    )
    assert result["queue_forms"] is False
    assert result["avg_delay_per_vehicle"] == 0.0


def test_wz_speed_exceeds_posted():
    """Work-zone speed > posted speed, demand < capacity → delay clipped to 0."""
    result = compute_delay(
        normal_lanes=3,
        lanes_closed=1,
        demand=2000.0,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=70.0,
        analysis_duration=8.0,
    )
    assert result["queue_forms"] is False
    assert result["avg_delay_per_vehicle"] == 0.0


# --- Task 5: Sensitivity function ---


def test_sensitivity_returns_21_points():
    """Sensitivity returns 21 demand/delay points by default."""
    demands, delays = compute_sensitivity(
        normal_lanes=3,
        lanes_closed=1,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
        current_demand=4000.0,
    )
    assert len(demands) == 21
    assert len(delays) == 21


def test_sensitivity_range():
    """Demand range spans 0.5× to 1.5× current demand."""
    demands, _ = compute_sensitivity(
        normal_lanes=3,
        lanes_closed=1,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
        current_demand=4000.0,
    )
    assert demands[0] == pytest.approx(2000.0)
    assert demands[-1] == pytest.approx(6000.0)


def test_sensitivity_includes_current():
    """Current demand value is in the demand list (midpoint of 21 points)."""
    demands, _ = compute_sensitivity(
        normal_lanes=3,
        lanes_closed=1,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
        current_demand=4000.0,
    )
    assert any(abs(d - 4000.0) < 1.0 for d in demands)
