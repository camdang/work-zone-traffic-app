# Design Specification — Work-Zone Traffic What-If Planner

**Version:** 1.0  
**Status:** Draft — pending human review  
**Date:** 2026-07-25

---

## 1. Overview

This specification describes the implementation plan for a **Streamlit work-zone traffic what-if planner**. The application enables transportation engineers to model a single highway work zone and visualize the traffic impact of lane closures under varying demand scenarios.

**No AI/LLM components are included.** This is traditional deterministic application software.

---

## 2. Architecture

```
work-zone-traffic-app/
├── app/
│   ├── __init__.py
│   ├── model.py            # Pure traffic math functions (no side effects)
│   └── streamlit_app.py    # UI: widgets, model calls, rendering
├── tests/
│   ├── __init__.py
│   └── test_model.py       # pytest unit tests for model.py
├── requirements.txt        # Pinned dependencies
├── plans/
│   └── spec.md             # This file
├── rules/                  # Project rules (do not modify)
└── README.md
```

### 2.1 Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `app/model.py` | All traffic calculations: capacity, delay, queueing, sensitivity sweep. Pure functions only — no Streamlit imports, no I/O. |
| `app/streamlit_app.py` | Sidebar inputs, validation display, calls model functions, renders metrics/charts/summary. No traffic math. |
| `tests/test_model.py` | Unit tests with known-input/known-output cases covering all model functions. |

---

## 3. Dependencies (`requirements.txt`)

```
streamlit>=1.30,<2.0
numpy>=1.24,<2.0
pandas>=2.0,<3.0
matplotlib>=3.7,<4.0
pytest>=7.0,<9.0
```

- **matplotlib** is chosen as the plotting library (matches "our other apps" convention).
- No additional services, databases, or external APIs.

---

## 4. Model Module (`app/model.py`)

All functions are pure, stateless, and typed. Each has a docstring.

### 4.1 Constants

```python
VEHICLES_PER_MILE: float = 150.0  # Fixed spacing assumption for queue-to-miles conversion
```

### 4.2 Functions

#### `compute_capacity(normal_lanes: int, lanes_closed: int, wz_capacity_per_lane: float) -> float`

Returns work-zone throughput capacity (veh/hr).

- Formula: `(normal_lanes - lanes_closed) * wz_capacity_per_lane`
- Raises `ValueError` if `normal_lanes - lanes_closed <= 0`.

#### `compute_delay_no_queue(wz_length: float, wz_speed: float, posted_speed: float) -> float`

Returns delay per vehicle (minutes) when demand ≤ capacity (speed-reduction delay only).

- Formula: `((wz_length / wz_speed) - (wz_length / posted_speed)) * 60`
- If `wz_speed >= posted_speed`, returns `0.0` (no delay from speed reduction).

#### `compute_queueing(demand: float, capacity: float, duration_hours: float) -> dict`

Returns a dictionary with queueing results for the over-capacity case:

```python
{
    "queue_by_hour": list[float],       # Queue length (vehicles) at end of each hour
    "max_queue_vehicles": float,        # Peak queue (vehicles)
    "max_queue_miles": float,           # Peak queue (miles) = max_queue_vehicles / VEHICLES_PER_MILE
    "total_delay_veh_hours": float,     # Area between cumulative curves (vehicle-hours)
    "avg_delay_per_vehicle_min": float, # total_delay / total_arrivals * 60
}
```

**Algorithm (deterministic, hourly resolution):**

For each hour `t` in `[1, 2, ..., ceil(duration_hours)]`:
1. Cumulative arrivals at time t: `A(t) = demand * min(t, duration_hours)`
2. Cumulative departures at time t: `D(t) = capacity * min(t, duration_hours)`  
   (Departures cannot exceed arrivals: `D(t) = min(D(t), A(t))`)
3. Queue at time t: `Q(t) = A(t) - D(t)`
4. Total delay = sum of hourly queue values (trapezoidal: area under the queue curve using the hourly trapezoids).

Note: For fractional final hours, interpolate proportionally.

If demand ≤ capacity, returns zeros for all queue/delay fields.

#### `analyze_scenario(normal_lanes: int, lanes_closed: int, demand: float, normal_capacity_per_lane: float, wz_capacity_per_lane: float, wz_length: float, posted_speed: float, wz_speed: float, duration_hours: float) -> dict`

Top-level orchestrator. Returns a dictionary with all results:

```python
{
    "open_lanes": int,
    "capacity": float,                  # veh/hr
    "queue_forms": bool,
    "max_queue_vehicles": float,
    "max_queue_miles": float,
    "avg_delay_per_vehicle_min": float,
    "queue_by_hour": list[float],       # For the time-series chart
    "total_delay_veh_hours": float,
}
```

Logic:
1. Validate open lanes > 0; raise `ValueError` if not.
2. Compute capacity via `compute_capacity`.
3. If `demand <= capacity`: no queue, delay from `compute_delay_no_queue`.
4. If `demand > capacity`: compute queueing via `compute_queueing`.

#### `sensitivity_sweep(normal_lanes: int, lanes_closed: int, demand: float, normal_capacity_per_lane: float, wz_capacity_per_lane: float, wz_length: float, posted_speed: float, wz_speed: float, duration_hours: float) -> dict`

Generates data for the delay-vs-demand sensitivity chart.

- Sweeps demand from `0.5 * demand` to `1.5 * demand` in 21 evenly-spaced points.
- For each demand value, calls `analyze_scenario` and collects `avg_delay_per_vehicle_min`.
- Returns:

```python
{
    "demand_values": list[float],       # 21 demand points
    "delay_values": list[float],        # Corresponding avg delay (minutes)
    "current_demand": float,            # The user's input demand (for marking on chart)
}
```

---

## 5. UI Module (`app/streamlit_app.py`)

### 5.1 Page Configuration

- `st.set_page_config(page_title="Work-Zone Traffic Planner", layout="wide")`
- Title: "Work-Zone Traffic What-If Planner"

### 5.2 Sidebar Inputs

All inputs in `st.sidebar` using `st.number_input` (integers for lane counts, floats for the rest):

| Parameter | Widget key | Default | Min | Step |
|-----------|-----------|---------|-----|------|
| Normal lanes | `normal_lanes` | 3 | 1 | 1 |
| Lanes closed | `lanes_closed` | 1 | 0 | 1 |
| Traffic demand (veh/hr) | `demand` | 4000 | 0 | 100 |
| Normal capacity/lane (veh/hr) | `normal_cap` | 1900 | 0 | 100 |
| Work-zone capacity/lane (veh/hr) | `wz_cap` | 1400 | 0 | 100 |
| Work-zone length (miles) | `wz_length` | 2.0 | 0.1 | 0.1 |
| Posted speed (mph) | `posted_speed` | 65 | 1 | 5 |
| Work-zone speed (mph) | `wz_speed` | 45 | 1 | 5 |
| Analysis duration (hours) | `duration` | 8.0 | 0.5 | 0.5 |

### 5.3 Validation

After reading inputs, check: `normal_lanes - lanes_closed > 0`.

If invalid:
- Display `st.error("All lanes are closed. Reduce lanes closed or increase normal lanes.")`
- `st.stop()` — no further output rendered.

### 5.4 Main Panel — Metrics

Call `model.analyze_scenario(...)` with sidebar values.

Display metrics using `st.metric` or `st.columns`:
- **Throughput Capacity:** `{capacity:,.0f} veh/hr`
- **Queue Forms:** Yes / No
- **Max Queue Length:** `{max_queue_vehicles:,.0f} vehicles ({max_queue_miles:.1f} miles)`
- **Avg Delay / Vehicle:** `{avg_delay_per_vehicle_min:.1f} minutes`

### 5.5 Main Panel — Charts

#### Chart 1: Queue Length Over Time

- matplotlib figure with hours on x-axis, queue (vehicles) on y-axis.
- Step or line plot of `queue_by_hour` values.
- X-axis label: "Time (hours)", Y-axis label: "Queue Length (vehicles)"
- Title: "Queue Length Over Time"
- Rendered via `st.pyplot(fig)`.

#### Chart 2: Delay vs. Demand Sensitivity

- Call `model.sensitivity_sweep(...)`.
- Line plot: demand (x-axis) vs. average delay (y-axis).
- Vertical line or marker at `current_demand`.
- X-axis label: "Demand (veh/hr)", Y-axis label: "Avg Delay (min/vehicle)"
- Title: "Delay vs. Demand"
- Rendered via `st.pyplot(fig)`.

### 5.6 Main Panel — Plain-Language Summary

Generate a summary string based on results:

**No-queue case:**
> "With {demand:,} veh/hr demand and {open_lanes} open lanes providing {capacity:,} veh/hr capacity, no queue forms. The only delay is {avg_delay:.1f} minutes per vehicle due to the speed reduction from {posted_speed} mph to {wz_speed} mph over the {wz_length}-mile work zone."

**Over-capacity case:**
> "With {demand:,} veh/hr demand exceeding the {capacity:,} veh/hr capacity ({open_lanes} open lanes), a queue forms reaching a maximum of {max_queue_vehicles:,.0f} vehicles ({max_queue_miles:.1f} miles). Average delay per vehicle is {avg_delay:.1f} minutes over the {duration}-hour analysis period."

Display via `st.info(summary)`.

### 5.7 Assumptions Footer

Display a collapsed expander with the fixed assumptions:
- Deterministic flow (no stochastic variation)
- Constant demand over the analysis period
- Infinite queue storage (no spillback)
- Queue spacing: 150 vehicles per mile
- Single bottleneck (work zone only)
- Planning-level accuracy

---

## 6. Test Plan (`tests/test_model.py`)

Tests use **pytest**. Each test uses hand-calculated expected values.

### Task 1: Test capacity computation

- `compute_capacity(3, 1, 1400)` → `2800.0`
- `compute_capacity(4, 2, 1400)` → `2800.0`
- `compute_capacity(2, 2, 1400)` → raises `ValueError`

### Task 2: Test no-queue delay

- `compute_delay_no_queue(2.0, 45, 65)` → `(2/45 - 2/65) * 60 ≈ 0.8205 min`
- `compute_delay_no_queue(2.0, 65, 45)` → `0.0` (wz_speed ≥ posted_speed)
- `compute_delay_no_queue(0.1, 45, 65)` → small positive value, no crash

### Task 3: Test over-capacity queueing

Hand-calculated scenario:
- demand=3000, capacity=2000, duration=4 hours
- Hour 1: arrivals=3000, departures=2000, queue=1000
- Hour 2: arrivals=6000, departures=4000, queue=2000
- Hour 3: arrivals=9000, departures=6000, queue=3000
- Hour 4: arrivals=12000, departures=8000, queue=4000
- Max queue = 4000 vehicles = 4000/150 ≈ 26.67 miles
- Total delay (trapezoidal): (0+1000)/2 + (1000+2000)/2 + (2000+3000)/2 + (3000+4000)/2 = 500+1500+2500+3500 = 8000 veh-hours
- Avg delay = 8000/12000 * 60 = 40.0 min/vehicle

### Task 4: Test demand-equals-capacity boundary

- demand=2800, capacity=2800, duration=4 → queue_forms=False, max_queue=0

### Task 5: Test edge cases

- Zero demand: `demand=0` → no queue, zero delay, no crash
- Zero open lanes: raises `ValueError`
- Minimum duration (0.5 hours): runs without crash
- Very high demand: large values compute without overflow

### Task 6: Test sensitivity sweep

- Returns exactly 21 data points
- `demand_values[0]` ≈ `0.5 * demand`, `demand_values[-1]` ≈ `1.5 * demand`
- `current_demand` matches input demand

### Task 7: Test analyze_scenario integration

- No-queue scenario returns `queue_forms=False`, correct delay
- Over-capacity scenario returns `queue_forms=True`, correct queue metrics
- Invalid lanes raises `ValueError`

---

## 7. Implementation Order

1. Create `requirements.txt` with pinned dependencies.
2. Create `app/__init__.py` (empty).
3. Implement `app/model.py` — all functions per §4.
4. Create `tests/__init__.py` (empty).
5. Implement `tests/test_model.py` — all test tasks per §6.
6. Run `pytest -q` — verify all tests pass.
7. Implement `app/streamlit_app.py` — UI per §5.
8. Run the app manually to verify sidebar, metrics, charts, and summary render correctly.
9. Final `pytest -q` run to confirm nothing broke.

---

## 8. Acceptance Criteria

The build is complete when:

1. The app runs via `streamlit run app/streamlit_app.py` without errors.
2. All 9 sidebar inputs render with correct defaults.
3. Validation blocks calculation and shows error when all lanes are closed.
4. Metrics display correctly for both no-queue and over-capacity scenarios.
5. Queue-length-over-time chart renders correctly.
6. Delay-vs-demand chart renders with current demand marked and ±50% sweep.
7. Summary accurately describes the scenario without recommendations.
8. `pytest -q` passes with all model unit tests.
9. Code review reports no Blocker-level issues.
10. Edge cases (zero demand, extreme demand, minimal duration) do not crash.
