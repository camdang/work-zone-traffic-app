# Implementation Specification — Work-Zone Traffic What-If Planner

**Status:** PROPOSED  
**Date:** 2026-07-27  
**Source:** `rules/APP_REQUIREMENTS.md`, `rules/APP_DESCRIPTION.md`, `rules/BEST_PRACTICES.md`

---

## 1. Overview

A Streamlit application that models a single highway work zone and computes traffic impacts (queue formation, delay, throughput) using deterministic queueing theory. No AI/LLM components. Pure computational tool for transportation engineers.

---

## 2. Architecture

```
work-zone-traffic-app/
├── app/
│   ├── __init__.py
│   ├── model.py            # Pure traffic math functions (no side effects)
│   └── streamlit_app.py    # UI: sidebar inputs, main panel outputs
├── tests/
│   ├── __init__.py
│   └── test_model.py       # pytest unit tests for model.py
├── requirements.txt        # Pinned dependencies
└── rules/                  # (read-only, not modified)
```

### 2.1 Separation of concerns

- **`app/model.py`** — All traffic calculations as pure functions. Takes numeric inputs, returns dataclass/dict results. Zero Streamlit imports.
- **`app/streamlit_app.py`** — Streamlit widgets (sidebar), calls model functions, renders metrics/charts/summary. No math beyond formatting.

---

## 3. Module Plan

### 3.1 `app/model.py`

#### Data structures

```python
from dataclasses import dataclass

@dataclass
class ScenarioInputs:
    normal_lanes: int          # Total lanes in direction (≥1)
    lanes_closed: int          # Lanes blocked by work zone (≥0)
    demand_vph: float          # Traffic demand (veh/hr)
    normal_capacity_per_lane: float   # veh/hr (default 1900)
    wz_capacity_per_lane: float       # veh/hr (default 1400)
    wz_length_miles: float     # Work-zone length (miles)
    posted_speed_mph: float    # Normal speed (mph)
    wz_speed_mph: float        # Work-zone speed (mph)
    analysis_duration_hours: float    # Analysis period (hours)

@dataclass
class ScenarioResults:
    open_lanes: int
    wz_capacity_vph: float          # Throughput capacity
    queue_forms: bool
    max_queue_vehicles: float
    max_queue_miles: float
    avg_delay_minutes: float
    total_delay_veh_hours: float
    hourly_queue_vehicles: list[float]   # Queue at each hour boundary
```

#### Functions

| Function | Signature | Purpose |
|----------|-----------|---------|
| `validate_inputs` | `(inputs: ScenarioInputs) -> tuple[bool, str]` | Returns (valid, error_message). Invalid if open_lanes ≤ 0. |
| `compute_capacity` | `(inputs: ScenarioInputs) -> tuple[int, float]` | Returns (open_lanes, wz_throughput_capacity). |
| `compute_delay_no_queue` | `(inputs: ScenarioInputs) -> ScenarioResults` | Speed-reduction-only delay when demand ≤ capacity. |
| `compute_delay_over_capacity` | `(inputs: ScenarioInputs) -> ScenarioResults` | Deterministic queueing: hourly queue buildup, max queue, avg delay. |
| `analyze_scenario` | `(inputs: ScenarioInputs) -> ScenarioResults` | Main entry point. Validates, routes to no-queue or over-capacity. |
| `compute_delay_sweep` | `(inputs: ScenarioInputs, num_points: int = 21) -> list[tuple[float, float]]` | Returns [(demand, avg_delay_minutes), ...] for demand from 0.5× to 1.5× current. |

#### Algorithm details

**Capacity:**
```
open_lanes = normal_lanes - lanes_closed
wz_capacity = open_lanes * wz_capacity_per_lane
```

**No-queue case (demand ≤ wz_capacity):**
```
delay_minutes = (wz_length / wz_speed - wz_length / posted_speed) * 60
max_queue = 0
hourly_queue = [0.0] * (hours + 1)
```

**Over-capacity case (demand > wz_capacity):**
- Hourly time steps: t = 0, 1, ..., analysis_duration (integer hours, plus fractional final hour if needed).
- Each hour: arrivals accumulate at `demand_vph`, departures at `min(demand_vph, wz_capacity)` (departure rate is capped at capacity).
- Queue at end of hour h: `queue[h] = queue[h-1] + demand_vph - wz_capacity` (cannot go below 0).
- Since demand is constant and > capacity, queue grows linearly each hour by `(demand - capacity)`.
- `max_queue_vehicles` = queue at end of analysis period (since demand is constant and always exceeds capacity, queue only grows).
- `max_queue_miles` = max_queue_vehicles / 150.0 (fixed spacing: 150 veh/mile).
- `total_delay_veh_hours` = area between cumulative arrival and departure curves = sum of hourly queue values (trapezoidal or rectangle rule on hourly steps).
- `avg_delay_minutes` = (total_delay_veh_hours / total_arrivals) * 60.
- In over-capacity case, reported delay is **queueing delay only** (speed-reduction delay excluded).

**Delay sweep:**
- Generate 21 evenly-spaced demand values from `0.5 * demand_vph` to `1.5 * demand_vph`.
- For each, run `analyze_scenario` with that demand and collect `avg_delay_minutes`.

### 3.2 `app/streamlit_app.py`

#### Layout

**Page config:**
- Title: "Work-Zone Traffic What-If Planner"
- Layout: wide
- Icon: 🚧

**Sidebar — Inputs:**
- `st.sidebar.header("Scenario Parameters")`
- `st.sidebar.number_input(...)` for each parameter per §2.1 of requirements
- Lane counts use `step=1` (integers); others use appropriate float steps.
- Defaults and minimums match requirements table exactly.

**Main panel — Outputs:**
1. **Validation check** — if invalid, display `st.error(message)` and `st.stop()`.
2. **Metrics row** — use `st.columns(5)` with `st.metric()` for: throughput capacity, queue forms (Yes/No), max queue (vehicles), max queue (miles), avg delay (min).
3. **Charts** — two charts side-by-side or stacked:
   - **Queue over time** — line chart, x = hours, y = queue (vehicles). Uses `hourly_queue_vehicles` from results.
   - **Delay vs. demand** — line chart with current demand marked (vertical line or highlighted point). Uses `compute_delay_sweep` output.
4. **Summary** — `st.markdown()` with plain-language description generated by a `format_summary()` helper function (lives in streamlit_app.py since it's presentation logic).

#### Chart library

Use **matplotlib** (standard, lightweight, no extra JS). Charts rendered via `st.pyplot()`.

#### Summary generation

A helper function `format_summary(inputs, results)` that returns a markdown string:
- No-queue case: "With {demand} veh/hr demand and {capacity} veh/hr capacity ({open_lanes} open lanes), no queue forms. Vehicles experience approximately {delay:.1f} minutes of delay due to the speed reduction from {posted} mph to {wz_speed} mph through the {length}-mile work zone."
- Over-capacity case: "With {demand} veh/hr demand exceeding the {capacity} veh/hr capacity ({open_lanes} open lanes), a queue forms. The maximum queue reaches {max_q_veh:.0f} vehicles ({max_q_mi:.1f} miles). Average delay per vehicle is {avg_delay:.1f} minutes over the {duration}-hour analysis period."

---

## 4. Dependencies (`requirements.txt`)

```
streamlit>=1.30.0,<2.0
numpy>=1.26.0,<2.0
pandas>=2.1.0,<3.0
matplotlib>=3.8.0,<4.0
pytest>=7.4.0,<9.0
```

---

## 5. Test Plan (`tests/test_model.py`)

Tests use pytest. Each test uses hand-calculated expected values.

### Task 1: Test capacity calculation
- **test_capacity_basic**: 3 normal lanes, 1 closed → 2 open lanes, capacity = 2 × 1400 = 2800 veh/hr.
- **test_capacity_no_closure**: 3 normal lanes, 0 closed → 3 open lanes, capacity = 3 × 1400 = 4200 veh/hr.
- **test_capacity_custom_rate**: 4 lanes, 2 closed, wz_capacity_per_lane=1200 → 2 × 1200 = 2400 veh/hr.

### Task 2: Test validation
- **test_validate_all_lanes_closed**: 2 normal lanes, 2 closed → invalid, error message mentions zero open lanes.
- **test_validate_more_closed_than_normal**: 2 normal, 3 closed → invalid.
- **test_validate_valid_inputs**: 3 normal, 1 closed → valid.

### Task 3: Test no-queue delay
- **test_no_queue_delay**: demand=2000, capacity=2800 (2 open × 1400). wz_length=2.0, posted_speed=65, wz_speed=45. Expected delay = (2/45 - 2/65) × 60 ≈ 0.821 minutes. Queue = 0.
- **test_demand_equals_capacity**: demand = capacity exactly → no queue, only speed-reduction delay.

### Task 4: Test over-capacity queueing
- **test_over_capacity_basic**: demand=3500, capacity=2800 (2 open × 1400), duration=4 hours.
  - Excess per hour = 700 veh/hr.
  - Queue at hour 1 = 700, hour 2 = 1400, hour 3 = 2100, hour 4 = 2800.
  - Max queue = 2800 vehicles = 2800/150 ≈ 18.67 miles.
  - Total arrivals = 3500 × 4 = 14000.
  - Total delay (area) = 700×1/2 + 700×3/2 + 700×5/2 + 700×7/2 = 700 × (0.5+1.5+2.5+3.5) = 700 × 8 = 5600 veh-hours. (Using trapezoidal: sum of trapezoids between hourly queue values [0, 700, 1400, 2100, 2800] = (0+700)/2 + (700+1400)/2 + (1400+2100)/2 + (2100+2800)/2 = 350 + 1050 + 1750 + 2450 = 5600 veh-hours.)
  - Avg delay = (5600 / 14000) × 60 = 24.0 minutes.

### Task 5: Test edge cases
- **test_zero_demand**: demand=0 → no queue, zero delay, no crash.
- **test_wz_speed_equals_posted_speed**: wz_speed=65, posted=65 → no-queue delay = 0 minutes.
- **test_minimum_duration**: duration=0.5 hours, demand > capacity → queue builds for half hour.
- **test_large_demand**: demand=10000, verify no overflow/NaN.

### Task 6: Test delay sweep
- **test_delay_sweep_length**: verify returns 21 points.
- **test_delay_sweep_range**: verify demand range is 0.5× to 1.5× input demand.
- **test_delay_sweep_monotonic**: delay should be non-decreasing as demand increases.

---

## 6. Implementation Order

1. Create project structure (`app/__init__.py`, `tests/__init__.py`).
2. Implement `app/model.py` — data structures and all functions.
3. Write `tests/test_model.py` — all test tasks.
4. Run `pytest -q` to verify model correctness.
5. Implement `app/streamlit_app.py` — sidebar inputs, metrics, charts, summary.
6. Write `requirements.txt`.
7. Manual smoke test (run Streamlit locally if possible).
8. Final `pytest -q` pass.
9. Code review.
10. Commit and push.

---

## 7. Assumptions & Constraints

- **150 vehicles per mile** for queue-to-distance conversion.
- **Hourly time resolution** for queue dynamics.
- **No extrapolation** beyond analysis period — report queue as-is at end.
- **Deterministic, constant demand** — no time-varying profiles.
- **Single bottleneck** — work zone is the only capacity constraint.
- App must run in the existing Streamlit Docker deployment without config changes.
