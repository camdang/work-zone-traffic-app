"""Traffic model for work-zone what-if planner.

Pure, side-effect-free functions for deterministic queueing analysis
of highway work zones.
"""

VEHICLES_PER_MILE: float = 150.0


def compute_capacity(
    normal_lanes: int, lanes_closed: int, wz_capacity_per_lane: float
) -> float:
    """Return work-zone throughput capacity (veh/hr).

    capacity = open_lanes * wz_capacity_per_lane
    where open_lanes = normal_lanes - lanes_closed

    Raises ValueError if open_lanes <= 0.
    """
    open_lanes = normal_lanes - lanes_closed
    if open_lanes <= 0:
        raise ValueError(
            f"No open lanes: normal_lanes={normal_lanes}, lanes_closed={lanes_closed}"
        )
    return open_lanes * wz_capacity_per_lane


def compute_delay(
    normal_lanes: int,
    lanes_closed: int,
    demand: float,
    normal_capacity_per_lane: float,
    wz_capacity_per_lane: float,
    wz_length: float,
    posted_speed: float,
    wz_speed: float,
    analysis_duration: float,
) -> dict:
    """Compute all traffic metrics for the scenario.

    Returns a dict with keys:
        wz_capacity, queue_forms, max_queue_vehicles, max_queue_miles,
        avg_delay_per_vehicle, queue_over_time, total_delay_veh_hours

    Raises ValueError if open_lanes <= 0.
    """
    wz_capacity = compute_capacity(normal_lanes, lanes_closed, wz_capacity_per_lane)

    num_hours = int(analysis_duration)
    fractional = analysis_duration - num_hours
    time_points = [float(t) for t in range(num_hours + 1)]
    if fractional > 0:
        time_points.append(analysis_duration)

    if demand <= wz_capacity:
        speed_reduction_delay = max(
            0.0, (wz_length / wz_speed - wz_length / posted_speed) * 60.0
        )
        avg_delay = speed_reduction_delay
        total_arrivals = demand * analysis_duration
        total_delay_veh_hours = (speed_reduction_delay / 60.0) * total_arrivals if total_arrivals > 0 else 0.0
        queue_over_time = [0.0] * len(time_points)

        return {
            "wz_capacity": wz_capacity,
            "queue_forms": False,
            "max_queue_vehicles": 0.0,
            "max_queue_miles": 0.0,
            "avg_delay_per_vehicle": avg_delay,
            "queue_over_time": queue_over_time,
            "total_delay_veh_hours": total_delay_veh_hours,
        }

    queue_over_time = []
    for t in time_points:
        cumulative_arrivals = demand * t
        cumulative_departures = wz_capacity * t
        queue = max(0.0, cumulative_arrivals - cumulative_departures)
        queue_over_time.append(queue)

    max_queue_vehicles = max(queue_over_time)
    max_queue_miles = max_queue_vehicles / VEHICLES_PER_MILE

    total_delay_veh_hours = 0.0
    for i in range(len(time_points) - 1):
        dt = time_points[i + 1] - time_points[i]
        avg_queue_in_interval = (queue_over_time[i] + queue_over_time[i + 1]) / 2.0
        total_delay_veh_hours += avg_queue_in_interval * dt

    total_arrivals = demand * analysis_duration
    avg_delay = (total_delay_veh_hours / total_arrivals) * 60.0 if total_arrivals > 0 else 0.0

    return {
        "wz_capacity": wz_capacity,
        "queue_forms": True,
        "max_queue_vehicles": max_queue_vehicles,
        "max_queue_miles": max_queue_miles,
        "avg_delay_per_vehicle": avg_delay,
        "queue_over_time": queue_over_time,
        "total_delay_veh_hours": total_delay_veh_hours,
    }


def compute_sensitivity(
    normal_lanes: int,
    lanes_closed: int,
    normal_capacity_per_lane: float,
    wz_capacity_per_lane: float,
    wz_length: float,
    posted_speed: float,
    wz_speed: float,
    analysis_duration: float,
    current_demand: float,
    num_points: int = 21,
) -> tuple[list[float], list[float]]:
    """Compute delay-vs-demand sensitivity curve.

    Sweeps demand from 0.5x to 1.5x current_demand at num_points.
    Returns (demands_list, delays_list) for plotting.
    """
    low = 0.5 * current_demand
    high = 1.5 * current_demand
    if num_points < 2:
        num_points = 2
    step = (high - low) / (num_points - 1)
    demands = [low + i * step for i in range(num_points)]

    delays = []
    for d in demands:
        result = compute_delay(
            normal_lanes=normal_lanes,
            lanes_closed=lanes_closed,
            demand=d,
            normal_capacity_per_lane=normal_capacity_per_lane,
            wz_capacity_per_lane=wz_capacity_per_lane,
            wz_length=wz_length,
            posted_speed=posted_speed,
            wz_speed=wz_speed,
            analysis_duration=analysis_duration,
        )
        delays.append(result["avg_delay_per_vehicle"])

    return demands, delays
