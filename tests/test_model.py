"""Unit tests for app.model — work-zone traffic calculations."""

import pytest

from app.model import compute_capacity, compute_delay, compute_sensitivity


# ---------- Task 1: Capacity calculation ----------


def test_capacity_basic():
    """3 normal lanes, 1 closed, 1400 wz cap -> 2 * 1400 = 2800."""
    assert compute_capacity(3, 1, 1400.0) == 2800.0


def test_capacity_no_closure():
    """3 normal lanes, 0 closed, 1400 wz cap -> 3 * 1400 = 4200."""
    assert compute_capacity(3, 0, 1400.0) == 4200.0


def test_capacity_all_closed():
    """3 normal lanes, 3 closed -> raises ValueError."""
    with pytest.raises(ValueError):
        compute_capacity(3, 3, 1400.0)


# ---------- Task 2: No-queue case ----------


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
    # Delay = (2.0/45 - 2.0/65) * 60 ≈ 0.8205 min
    expected_delay = (2.0 / 45.0 - 2.0 / 65.0) * 60.0
    assert abs(result["avg_delay_per_vehicle"] - expected_delay) < 0.001


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


# ---------- Task 3: Over-capacity queueing ----------


def test_over_capacity_basic():
    """Demand=4000, capacity=2800, duration=8h."""
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
    # Excess = 4000 - 2800 = 1200 veh/hr
    # Max queue at hour 8 = 1200 * 8 = 9600 vehicles
    assert result["max_queue_vehicles"] == 9600.0
    # Miles = 9600 / 150 = 64.0
    assert result["max_queue_miles"] == 64.0
    # Total delay = area under linear queue curve from 0 to 9600 over 8 hours
    # = 0.5 * 8 * 9600 = 38400 veh-hours
    assert abs(result["total_delay_veh_hours"] - 38400.0) < 0.01
    # Avg delay = 38400 / (4000*8) * 60 = 38400/32000 * 60 = 72 minutes
    assert abs(result["avg_delay_per_vehicle"] - 72.0) < 0.01


def test_queue_over_time_shape():
    """Verify queue_over_time has correct hourly values."""
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
    # Queue grows at 1200 veh/hr: [0, 1200, 2400, ..., 9600]
    expected = [1200.0 * h for h in range(9)]
    assert result["queue_over_time"] == expected


# ---------- Task 4: Edge cases ----------


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
    assert result["avg_delay_per_vehicle"] >= 0.0


def test_minimum_duration():
    """Duration=0.5h with over-capacity: correct proportional results."""
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
    # Excess rate = 1200, at 0.5h queue = 600 vehicles
    assert abs(result["max_queue_vehicles"] - 600.0) < 0.01


def test_wz_speed_equals_posted():
    """Work-zone speed equals posted speed: zero delay in no-queue case."""
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
    assert result["avg_delay_per_vehicle"] == 0.0


def test_wz_speed_exceeds_posted():
    """Work-zone speed > posted speed: delay clipped to 0."""
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
    assert result["avg_delay_per_vehicle"] == 0.0


# ---------- Task 5: Sensitivity function ----------


def test_sensitivity_returns_21_points():
    """Verify length of returned lists is 21."""
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
    """Verify demand range spans 0.5x to 1.5x current demand."""
    current = 4000.0
    demands, _ = compute_sensitivity(
        normal_lanes=3,
        lanes_closed=1,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
        current_demand=current,
    )
    assert abs(demands[0] - 0.5 * current) < 0.01
    assert abs(demands[-1] - 1.5 * current) < 0.01


def test_sensitivity_includes_current():
    """Verify current demand value is in the demand list."""
    current = 4000.0
    demands, _ = compute_sensitivity(
        normal_lanes=3,
        lanes_closed=1,
        normal_capacity_per_lane=1900.0,
        wz_capacity_per_lane=1400.0,
        wz_length=2.0,
        posted_speed=65.0,
        wz_speed=45.0,
        analysis_duration=8.0,
        current_demand=current,
    )
    # With 21 points from 2000 to 6000, step=200, midpoint index 10 = 4000
    assert any(abs(d - current) < 0.01 for d in demands)
