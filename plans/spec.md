# Implementation Specification — Work-Zone Traffic What-If Planner

**Status:** DRAFT  
**Generated from:** `rules/APP_DESCRIPTION.md`, `rules/APP_REQUIREMENTS.md`, `rules/BEST_PRACTICES.md`

---

## 1. Overview

A Streamlit work-zone traffic what-if planner that models a single highway work zone on a unidirectional segment and shows the traffic impact of lane closures. No AI/LLM features. Pure deterministic traffic modeling with a clean separation between model logic and UI.

---

## 2. Project Structure

```
work-zone-traffic-app/
├── app/
│   ├── __init__.py
│   ├── model.py            # Pure traffic math functions
│   └── streamlit_app.py    # Streamlit UI (sidebar inputs, main panel output)
├── tests/
│   ├── __init__.py
│   └── test_model.py       # pytest unit tests for model.py
├── requirements.txt        # Pinned dependencies
├── plans/
│   └── spec.md             # This file
├── rules/                  # Do not modify
│   ├── APP_DESCRIPTION.md
│   ├── APP_REQUIREMENTS.md
│   └── BEST_PRACTICES.md
└── README.md
```

---

## 3. Dependencies (`requirements.txt`)

```
streamlit>=1.28.0,<2.0.0
numpy>=1.24.0,<2.0.0
pandas>=2.0.0,<3.0.0
matplotlib>=3.7.0,<4.0.0
pytest>=7.4.0,<9.0.0
```

- **matplotlib** is the plotting library (matches "existing apps" convention).
- No additional services or external data sources.

---

## 4. Module Plan

### 4.1 `app/model.py` — Traffic Model (Pure Functions)

All functions are pure, side-effect-free, fully typed, with docstrings.

#### 4.1.1 `compute_capacity(normal_lanes: int, lanes_closed: int, wz_capacity_per_lane: float) -> float`

Returns work-zone throughput capacity (veh/hr).

- Formula: `(normal_lanes - lanes_closed) * wz_capacity_per_lane`
- Precondition: caller validates `normal_lanes - lanes_closed > 0`

#### 4.1.2 `compute_delay_no_queue(wz_length: float, posted_speed: float, wz_speed: float) -> float`

Returns delay per vehicle (minutes) from speed reduction only (no-queue case).

- Formula: `(wz_length / wz_speed - wz_length / posted_speed) * 60`

#### 4.1.3 `compute_queue_over_time(demand: float, capacity: float, duration: float) -> list[float]`

Returns a list of queue lengths (vehicles) at each hour boundary `[0, 1, 2, ..., duration]`.

- Hourly time resolution.
- Queue at hour t = max(0, queue at t-1 + demand - capacity) — but since demand is constant and > capacity, queue grows linearly: `queue[t] = t * (demand - capacity)` for t in [0..duration].
- If demand ≤ capacity, returns all zeros.

#### 4.1.4 `compute_metrics(demand: float, capacity: float, duration: float, wz_length: float, posted_speed: float, wz_speed: float) -> dict`

Returns a dictionary with all output metrics:

```python
{
    "capacity": float,            # work-zone throughput (veh/hr)
    "queue_forms": bool,          # True if demand > capacity
    "max_queue_vehicles": float,  # max queue in vehicles
    "max_queue_miles": float,     # max queue in miles (vehicles / 150)
    "avg_delay_minutes": float,   # average delay per vehicle (minutes)
    "queue_over_time": list[float],  # queue at each hour boundary
    "total_delay_veh_hours": float   # total vehicle-hours of delay
}
```

**Logic:**

- If `demand <= capacity` (no-queue case):
  - `queue_forms = False`
  - `max_queue_vehicles = 0`
  - `max_queue_miles = 0`
  - `avg_delay_minutes = compute_delay_no_queue(wz_length, posted_speed, wz_speed)`
  - `queue_over_time = [0.0] * (int(duration) + 1)`
  - `total_delay_veh_hours = avg_delay_minutes / 60 * demand * duration`

- If `demand > capacity` (over-capacity case):
  - Queue grows hourly: `queue[t] = t * (demand - capacity)`
  - `max_queue_vehicles = duration * (demand - capacity)`
  - `max_queue_miles = max_queue_vehicles / 150.0`
  - Total delay (vehicle-hours) = area between cumulative arrival and departure curves = `(demand - capacity) * duration^2 / 2`
  - Total arrivals = `demand * duration`
  - `avg_delay_minutes = (total_delay_veh_hours / total_arrivals) * 60`
  - Reported delay is **queueing delay only** (speed-reduction delay excluded in over-capacity case).

#### 4.1.5 `compute_delay_vs_demand(capacity: float, duration: float, wz_length: float, posted_speed: float, wz_speed: float, current_demand: float) -> tuple[list[float], list[float]]`

Returns `(demand_values, delay_values)` for the sensitivity chart.

- Sweeps demand from `0.5 * current_demand` to `1.5 * current_demand` in 21 evenly spaced points.
- For each demand point, computes `avg_delay_minutes` using the same logic as `compute_metrics`.

#### 4.1.6 Constants

```python
VEHICLES_PER_MILE: float = 150.0  # Fixed spacing assumption for queue-to-miles conversion
```

### 4.2 `app/streamlit_app.py` — Streamlit UI

#### 4.2.1 Page Configuration

- `st.set_page_config(page_title="Work-Zone Traffic Planner", layout="wide")`
- Title: "Work-Zone Traffic What-If Planner"

#### 4.2.2 Sidebar Inputs

All inputs use `st.sidebar` widgets with the defaults, mins, and types from the requirements table:

| Parameter | Widget | Default | Min | Step |
|-----------|--------|---------|-----|------|
| Normal lanes | `number_input` (int) | 3 | 1 | 1 |
| Lanes closed | `number_input` (int) | 1 | 0 | 1 |
| Traffic demand | `number_input` (float) | 4000 | 0 | 100 |
| Normal capacity/lane | `number_input` (float) | 1900 | 0 | 100 |
| WZ capacity/lane | `number_input` (float) | 1400 | 0 | 100 |
| WZ length | `number_input` (float) | 2.0 | 0.1 | 0.1 |
| Posted speed | `number_input` (float) | 65 | 1 | 5 |
| WZ speed | `number_input` (float) | 45 | 1 | 5 |
| Analysis duration | `number_input` (float) | 8.0 | 0.5 | 0.5 |

#### 4.2.3 Validation

- Compute `open_lanes = normal_lanes - lanes_closed`.
- If `open_lanes <= 0`: display `st.error("All lanes are closed...")` and `st.stop()`.

#### 4.2.4 Main Panel — Metrics

Display using `st.metric` or columns:

- Work-zone throughput capacity (veh/hr)
- Queue forms? (Yes / No)
- Max queue length (vehicles)
- Max queue length (miles)
- Average delay per vehicle (minutes)

#### 4.2.5 Main Panel — Charts

**Chart 1: Queue Length Over Time**
- X-axis: Hour (0 to duration)
- Y-axis: Queue (vehicles)
- Line chart using matplotlib
- Title: "Queue Length Over Time"

**Chart 2: Delay vs. Demand Sensitivity**
- X-axis: Traffic Demand (veh/hr)
- Y-axis: Average Delay (minutes)
- Line chart with a vertical marker at the current demand value
- Title: "Delay vs. Demand (±50% sweep)"
- Sweep: 0.5× to 1.5× current demand, 21 points

Both charts rendered via `st.pyplot()`.

#### 4.2.6 Main Panel — Summary

A plain-language summary using `st.info()` or `st.markdown()`:

- **No-queue case:** "At {demand} veh/hr with {open_lanes} open lanes (capacity {capacity} veh/hr), demand is within capacity. No queue forms. The only delay is from the speed reduction through the {wz_length}-mile work zone: approximately {delay:.1f} minutes per vehicle."
- **Over-capacity case:** "At {demand} veh/hr with {open_lanes} open lanes (capacity {capacity} veh/hr), demand exceeds capacity. A queue forms, reaching a maximum of {max_q_veh:.0f} vehicles ({max_q_mi:.1f} miles). Average delay per vehicle is {avg_delay:.1f} minutes over the {duration}-hour analysis period."

No recommendations — results only.

#### 4.2.7 Assumptions Footer

Display a collapsed expander with key assumptions:
- Deterministic flow (no stochastic variation)
- Constant demand within the analysis period
- Infinite queue storage (no spillback)
- Queue-to-miles uses 150 vehicles/mile
- Single bottleneck (work zone only)
- Planning-level accuracy

---

## 5. Test Plan (`tests/test_model.py`)

All tests use pytest. Tests are numbered for sequential execution tracking.

### Task 1: Test capacity calculation
- `test_capacity_basic`: 3 normal lanes, 1 closed, 1400 wz cap → 2800 veh/hr
- `test_capacity_all_open`: 4 normal, 0 closed, 1400 → 5600 veh/hr
- `test_capacity_one_lane`: 2 normal, 1 closed, 1400 → 1400 veh/hr

### Task 2: Test no-queue delay
- `test_no_queue_delay`: wz_length=2.0, posted=65, wz_speed=45 → delay = (2/45 - 2/65)*60 ≈ 0.8205 minutes
- `test_no_queue_delay_same_speed`: posted=wz_speed=65 → delay = 0

### Task 3: Test over-capacity queueing
- `test_over_capacity_basic`: demand=4000, capacity=2800, duration=8
  - max_queue_vehicles = 8*(4000-2800) = 9600
  - max_queue_miles = 9600/150 = 64.0
  - total_delay = (4000-2800)*8²/2 = 38400 veh-hours
  - total_arrivals = 4000*8 = 32000
  - avg_delay = (38400/32000)*60 = 72.0 minutes

### Task 4: Test boundary — demand equals capacity
- `test_demand_equals_capacity`: demand=2800, capacity=2800, duration=8
  - queue_forms = False
  - max_queue = 0
  - avg_delay = speed-reduction delay only

### Task 5: Test edge cases
- `test_zero_demand`: demand=0, capacity=2800 → no queue, zero delay
- `test_minimum_duration`: duration=0.5, demand=4000, capacity=2800 → queue = 0.5*1200 = 600
- `test_wz_speed_exceeds_posted`: wz_speed=70, posted=65 → delay should be 0 (or negative clipped to 0) — no crash, no NaN

### Task 6: Test queue_over_time
- `test_queue_over_time_no_queue`: demand ≤ capacity → all zeros
- `test_queue_over_time_growing`: demand=4000, capacity=2800, duration=4 → [0, 1200, 2400, 3600, 4800]

### Task 7: Test delay_vs_demand sensitivity
- `test_delay_vs_demand_length`: returns 21 points
- `test_delay_vs_demand_at_current`: the value at the midpoint matches compute_metrics result

---

## 6. Implementation Order

1. Create project structure (`app/__init__.py`, `tests/__init__.py`)
2. Implement `app/model.py` (all pure functions)
3. Write `tests/test_model.py` (all unit tests)
4. Run tests — ensure all pass
5. Implement `app/streamlit_app.py` (UI layer)
6. Create `requirements.txt`
7. Final integration test (manual run confirmation)

---

## 7. Assumptions & Constraints Stated to User

The app must display (in a collapsed expander or similar) these modeling assumptions:
- Deterministic flow — no stochastic variation
- Constant demand — uniform arrival rate within the analysis period
- Infinite queue storage — no upstream spillback modeling
- Queue-length-to-miles uses 150 vehicles per mile (passenger-car basis)
- Single bottleneck — work zone is the only capacity constraint
- No vehicle-mix differentiation
- Planning-level accuracy — suitable for "what if" estimates, not detailed operational design

---

## 8. Out of Scope

Per requirements: No AI/LLM features, no deployment automation, no external data, no stochastic modeling, no multi-zone, no vehicle mix, no spillback, no time-of-day profiles, no recommendations, no auth, no export.
