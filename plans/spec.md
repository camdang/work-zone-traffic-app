# Design Specification — Work-Zone Traffic What-If Planner

**Version:** 1.0
**Status:** Draft — awaiting review

---

## 1. Overview

This specification describes the implementation plan for a Streamlit work-zone traffic what-if planner. The application models a single highway work zone on a unidirectional segment and shows the traffic impact of lane closures using deterministic queueing theory.

**No AI/LLM features are included.** This is traditional application software.

---

## 2. Architecture

```
work-zone-traffic-app/
├── app/
│   ├── __init__.py
│   ├── model.py            # Pure traffic math functions
│   └── streamlit_app.py    # UI: sidebar inputs, metrics, charts, summary
├── tests/
│   ├── __init__.py
│   └── test_model.py       # pytest unit tests for model.py
├── requirements.txt        # Pinned dependencies
├── plans/
│   └── spec.md             # This file
├── rules/                  # Project rules (do not modify)
└── README.md
```

### 2.1 Module responsibilities

| Module | Responsibility |
|--------|---------------|
| `app/model.py` | All traffic math — capacity calculation, delay computation, queueing analysis, sensitivity sweep. Pure functions, no side effects, no Streamlit imports. |
| `app/streamlit_app.py` | Sidebar widget rendering, input validation display, calling model functions, rendering metrics/charts/summary. No traffic math logic. |
| `tests/test_model.py` | Unit tests with known-input/known-output cases covering all model functions. |

---

## 3. Model Module (`app/model.py`)

### 3.1 Data structures

```python
from dataclasses import dataclass

@dataclass
class ScenarioInputs:
    """All user-provided inputs for a work-zone scenario."""
    normal_lanes: int          # Total lanes in this direction
    lanes_closed: int          # Lanes blocked by work zone
    demand_vph: float          # Traffic demand (vehicles/hour)
    normal_capacity_per_lane: float   # veh/hr per lane (normal)
    wz_capacity_per_lane: float       # veh/hr per lane (work zone)
    wz_length_miles: float     # Work-zone length
    posted_speed_mph: float    # Normal highway speed
    wz_speed_mph: float        # Reduced speed through work zone
    analysis_duration_hours: float    # Analysis period

@dataclass
class ScenarioResults:
    """Computed results for a work-zone scenario."""
    open_lanes: int
    wz_capacity_vph: float           # Total work-zone throughput capacity
    queue_forms: bool                 # Whether demand exceeds capacity
    max_queue_vehicles: float         # Peak queue length (vehicles)
    max_queue_miles: float            # Peak queue length (miles)
    avg_delay_minutes: float          # Average delay per vehicle
    queue_over_time: list[float]      # Queue (vehicles) at each hour boundary
    total_delay_veh_hours: float      # Total vehicle-hours of delay
```

### 3.2 Functions

#### `compute_capacity(normal_lanes: int, lanes_closed: int, wz_capacity_per_lane: float) -> float`
Returns work-zone throughput capacity = (normal_lanes − lanes_closed) × wz_capacity_per_lane.

#### `compute_speed_reduction_delay(wz_length_miles: float, posted_speed_mph: float, wz_speed_mph: float) -> float`
Returns delay in minutes from traversing the work zone at reduced speed vs. posted speed.
Formula: `(wz_length / wz_speed - wz_length / posted_speed) * 60`

#### `compute_queueing(demand_vph: float, capacity_vph: float, duration_hours: float) -> tuple[list[float], float, float]`
Deterministic queueing analysis (hourly resolution).
- Tracks cumulative arrivals and departures hour by hour.
- Returns: (queue_over_time, total_delay_veh_hours, max_queue_vehicles)
- Queue at hour t = cumulative_arrivals[t] − cumulative_departures[t]
- Total delay = sum of hourly queue values (area under the queue curve, each hour-step = 1 hour wide, so area = sum of queue lengths in vehicle-hours)
- If queue has not cleared by end of period, report as-is.

#### `analyze_scenario(inputs: ScenarioInputs) -> ScenarioResults`
Main entry point. Validates open_lanes > 0 (raises ValueError if not). Computes capacity, determines queue/no-queue case, dispatches to appropriate delay calculation, and assembles full results.

#### `compute_delay_vs_demand(inputs: ScenarioInputs, num_points: int = 21) -> tuple[list[float], list[float]]`
Sweeps demand from 0.5× to 1.5× the current input value at `num_points` evenly spaced points. Returns (demand_values, delay_values) for the sensitivity chart.

#### `generate_summary(inputs: ScenarioInputs, results: ScenarioResults) -> str`
Returns a plain-language summary string. Reports results only — no recommendations. Distinguishes no-queue case (speed-reduction delay only) from over-capacity case (queue forms, reports max queue and average delay).

### 3.3 Constants

```python
VEHICLES_PER_MILE: float = 150.0  # Queue-length-to-miles conversion factor
```

### 3.4 Modeling rules

- **No-queue case (demand ≤ capacity):** delay = speed-reduction delay only; queue = 0.
- **Over-capacity case (demand > capacity):** delay = queueing delay only (speed-reduction delay excluded per requirements — queueing dominates).
- **Hourly resolution:** queue tracked at integer hour boundaries [0, 1, 2, ..., duration].
- **End-of-period:** no extrapolation; report queue state as-is if not cleared.
- **Queue to miles:** max_queue_miles = max_queue_vehicles / 150.

---

## 4. UI Module (`app/streamlit_app.py`)

### 4.1 Page layout

- **Page title:** "Work-Zone Traffic What-If Planner"
- **Sidebar:** All 9 inputs with specified defaults, mins, and units.
- **Main panel:** Validation error (if applicable), then metrics, charts, summary.

### 4.2 Sidebar inputs

| Widget | Type | Key | Default | Min | Step |
|--------|------|-----|---------|-----|------|
| Normal lanes | number_input (int) | `normal_lanes` | 3 | 1 | 1 |
| Lanes closed | number_input (int) | `lanes_closed` | 1 | 0 | 1 |
| Traffic demand | number_input (float) | `demand_vph` | 4000 | 0 | 100 |
| Normal capacity/lane | number_input (float) | `normal_cap` | 1900 | 0 | 100 |
| Work-zone capacity/lane | number_input (float) | `wz_cap` | 1400 | 0 | 100 |
| Work-zone length | number_input (float) | `wz_length` | 2.0 | 0.1 | 0.1 |
| Posted speed | number_input (float) | `posted_speed` | 65 | 1 | 5 |
| Work-zone speed | number_input (float) | `wz_speed` | 45 | 1 | 5 |
| Analysis duration | number_input (float) | `duration` | 8.0 | 0.5 | 0.5 |

### 4.3 Validation display

If `normal_lanes - lanes_closed <= 0`:
- Display `st.error("All lanes are closed. Reduce lanes closed or increase normal lanes.")` in the main panel.
- Do not render metrics, charts, or summary.

### 4.4 Metrics display

Use `st.metric` or columns with `st.metric` for:
- Work-zone capacity (veh/hr)
- Queue forms (Yes / No)
- Max queue (vehicles)
- Max queue (miles)
- Avg delay/vehicle (minutes)

### 4.5 Charts

Use **matplotlib** (via `st.pyplot`) for both charts.

**Chart 1 — Queue length over time:**
- X-axis: Hour (0 to analysis_duration)
- Y-axis: Queue (vehicles)
- Line plot with filled area under curve
- Title: "Queue Length Over Time"

**Chart 2 — Delay vs. demand sensitivity:**
- X-axis: Demand (veh/hr), range = [0.5× current, 1.5× current]
- Y-axis: Average delay per vehicle (minutes)
- Line plot
- Vertical marker (dashed line or dot) at current demand value
- Title: "Average Delay vs. Demand"

### 4.6 Summary

Display `generate_summary()` output in an `st.info` block.

### 4.7 Assumptions footer

Display a collapsed expander (`st.expander("Assumptions")`) listing:
- Deterministic flow — no stochastic variation
- Constant demand over the analysis period
- Infinite queue storage — no spillback
- 150 vehicles/mile queue spacing
- Single bottleneck (work zone only)
- Planning-level accuracy

---

## 5. Dependencies (`requirements.txt`)

```
streamlit>=1.28,<2.0
numpy>=1.24,<2.0
pandas>=2.0,<3.0
matplotlib>=3.7,<4.0
pytest>=7.0,<9.0
```

---

## 6. Test Plan (`tests/test_model.py`)

Tests use pytest. Each test uses hand-calculable inputs.

### Task 1: Test capacity computation
- 2 open lanes × 1400 = 2800 veh/hr
- 3 open lanes × 1900 = 5700 veh/hr
- 1 open lane × 1400 = 1400 veh/hr

### Task 2: Test no-queue delay (speed reduction only)
- Scenario: demand=2000, capacity=2800 (below capacity)
- WZ length=2 miles, posted=65 mph, wz_speed=45 mph
- Expected delay = (2/45 − 2/65) × 60 minutes ≈ 0.821 minutes
- Expected queue = 0

### Task 3: Test over-capacity queueing
- Scenario: demand=5000 veh/hr, capacity=2800 veh/hr, duration=4 hours
- Hour-by-hour queue: [2200, 4400, 6600, 8800]
- Max queue = 8800 vehicles = 8800/150 ≈ 58.67 miles
- Total delay = 2200 + 4400 + 6600 + 8800 = 22000 vehicle-hours
- Total arrivals = 5000 × 4 = 20000
- Avg delay = 22000/20000 × 60 = 66.0 minutes

### Task 4: Test boundary — demand equals capacity
- demand = capacity = 2800 veh/hr
- Expected: no queue forms, queue_over_time all zeros
- Delay = 0 (no queueing) and speed-reduction delay applies (no-queue case)

### Task 5: Test edge cases
- Zero open lanes → raises ValueError
- Zero demand → zero delay, no crash, no queue
- Minimum duration (0.5 hours) → no crash
- Work-zone speed ≥ posted speed → delay ≤ 0, reported as 0 (no negative delay)

### Task 6: Test sensitivity sweep
- Verify returns 21 points
- Verify demand range is [0.5×, 1.5×] of input
- Verify delay at current demand matches single-scenario result

### Task 7: Test summary generation
- No-queue case → summary mentions speed-reduction delay, no queue
- Over-capacity case → summary mentions queue forms, max queue, avg delay
- Summary contains no recommendations

---

## 7. Implementation Order

1. Create `app/__init__.py`, `tests/__init__.py` (empty)
2. Implement `app/model.py` — all functions per §3
3. Implement `tests/test_model.py` — all test tasks per §6
4. Run `pytest -q` — fix until green
5. Implement `app/streamlit_app.py` — UI per §4
6. Create `requirements.txt` per §5
7. Manual verification — run Streamlit, test inputs, verify charts render
8. Final `pytest -q` — confirm still green

---

## 8. Out of Scope

Per rules: no AI features, no deployment automation, no external data sources, no stochastic modeling, no multi-zone, no vehicle mix, no spillback, no time-of-day profiles, no recommendations, no auth, no export.
