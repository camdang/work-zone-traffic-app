"""Unit tests for app.model — work-zone traffic calculations."""

import pytest

from app.model import compute_capacity, compute_delay, compute_sensitivity


# --- Task 1: Capacity calculation ---

class TestCapacity:
    def test_capacity_basic(self):
        result = compute_capacity(normal_lanes=3, lanes_closed=1, wz_capacity_per_lane=1400)
        assert result == 2800.0

    def test_capacity_no_closure(self):
        result = compute_capacity(normal_lanes=3, lanes_closed=0, wz_capacity_per_lane=1400)
        assert result == 4200.0

    def test_capacity_all_closed(self):
        with pytest.raises(ValueError):
            compute_capacity(normal_lanes=3, lanes_closed=3, wz_capacity_per_lane=1400)


# --- Task 2: No-queue case ---

class TestNoQueue:
    def test_no_queue_delay(self):
        result = compute_delay(
            normal_lanes=3,
            lanes_closed=1,
            demand=2000,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=8.0,
        )
        assert result["queue_forms"] is False
        assert result["max_queue_vehicles"] == 0.0
        assert result["max_queue_miles"] == 0.0
        expected_delay = (2.0 / 45 - 2.0 / 65) * 60
        assert abs(result["avg_delay_per_vehicle"] - expected_delay) < 0.01

    def test_demand_equals_capacity(self):
        result = compute_delay(
            normal_lanes=3,
            lanes_closed=1,
            demand=2800,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=8.0,
        )
        assert result["queue_forms"] is False
        assert result["max_queue_vehicles"] == 0.0


# --- Task 3: Over-capacity queueing ---

class TestOverCapacity:
    def test_over_capacity_basic(self):
        result = compute_delay(
            normal_lanes=3,
            lanes_closed=1,
            demand=4000,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=8.0,
        )
        assert result["queue_forms"] is True
        assert result["wz_capacity"] == 2800.0
        assert result["max_queue_vehicles"] == pytest.approx(9600.0)
        assert result["max_queue_miles"] == pytest.approx(64.0)
        total_arrivals = 4000 * 8
        assert result["avg_delay_per_vehicle"] == pytest.approx(
            (result["total_delay_veh_hours"] / total_arrivals) * 60
        )

    def test_queue_over_time_shape(self):
        result = compute_delay(
            normal_lanes=3,
            lanes_closed=1,
            demand=4000,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=8.0,
        )
        expected = [0.0, 1200.0, 2400.0, 3600.0, 4800.0, 6000.0, 7200.0, 8400.0, 9600.0]
        assert len(result["queue_over_time"]) == 9
        for actual, exp in zip(result["queue_over_time"], expected):
            assert actual == pytest.approx(exp)


# --- Task 4: Edge cases ---

class TestEdgeCases:
    def test_zero_demand(self):
        result = compute_delay(
            normal_lanes=3,
            lanes_closed=1,
            demand=0,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=8.0,
        )
        assert result["queue_forms"] is False
        assert result["max_queue_vehicles"] == 0.0

    def test_minimum_duration(self):
        result = compute_delay(
            normal_lanes=3,
            lanes_closed=1,
            demand=4000,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=0.5,
        )
        assert result["queue_forms"] is True
        assert result["max_queue_vehicles"] == pytest.approx(600.0)

    def test_wz_speed_equals_posted(self):
        result = compute_delay(
            normal_lanes=3,
            lanes_closed=1,
            demand=2000,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=65,
            analysis_duration=8.0,
        )
        assert result["queue_forms"] is False
        assert result["avg_delay_per_vehicle"] == 0.0

    def test_wz_speed_exceeds_posted(self):
        result = compute_delay(
            normal_lanes=3,
            lanes_closed=1,
            demand=2000,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=70,
            analysis_duration=8.0,
        )
        assert result["queue_forms"] is False
        assert result["avg_delay_per_vehicle"] == 0.0


# --- Task 5: Sensitivity function ---

class TestSensitivity:
    def test_sensitivity_returns_21_points(self):
        demands, delays = compute_sensitivity(
            normal_lanes=3,
            lanes_closed=1,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=8.0,
            current_demand=4000,
        )
        assert len(demands) == 21
        assert len(delays) == 21

    def test_sensitivity_range(self):
        current = 4000
        demands, _ = compute_sensitivity(
            normal_lanes=3,
            lanes_closed=1,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=8.0,
            current_demand=current,
        )
        assert demands[0] == pytest.approx(0.5 * current)
        assert demands[-1] == pytest.approx(1.5 * current)

    def test_sensitivity_includes_current(self):
        current = 4000
        demands, _ = compute_sensitivity(
            normal_lanes=3,
            lanes_closed=1,
            normal_capacity_per_lane=1900,
            wz_capacity_per_lane=1400,
            wz_length=2.0,
            posted_speed=65,
            wz_speed=45,
            analysis_duration=8.0,
            current_demand=current,
        )
        assert any(abs(d - current) < 1.0 for d in demands)
