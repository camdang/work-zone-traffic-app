# Implementation Specification — Work-Zone Traffic What-If Planner

**Version:** 1.0  
**Status:** DRAFT — pending review  
**Generated from:** `rules/APP_DESCRIPTION.md`, `rules/APP_REQUIREMENTS.md`, `rules/BEST_PRACTICES.md`

---

## 1. Overview

A Streamlit web application that allows transportation engineers to model a single highway work zone and evaluate the traffic impact of lane closures under constant-demand scenarios. The app uses deterministic queueing theory to compute queue formation, delay, and throughput metrics.

**No AI/LLM features are included in this application.**

---

## 2. Architecture

```
work-zone-traffic-app/
├── app/
│   ├── __init__.py
│   ├── model.py            # Pure traffic math functions (no side effects)
│   └── streamlit_app.py    # UI: widgets, calls model, renders results
├── tests/
│   ├── __init__.py
│   └── test_model.py       # pytest unit tests for model.py
├── requirements.txt        # Pinned dependencies
├── plans/
│   └── spec.md             # This file
├── rules/                  # Project rules (do not modify)
│   ├── APP_DESCRIPTION.md
│   ├── APP_REQUIREMENTS.md
│   └── BEST_PRACTICES.md
└── README.md
```

### 2.1 Separation of Concerns

- **`app/model.py`** — All traffic calculations as pure functions. No imports from Streamlit. No side effects. Fully testable in isolation.
- **`app/streamlit_app.py`** — Streamlit UI layer. Reads sidebar inputs, calls model functions, renders metrics/charts/summary. No traffic math logic here.

---

## 3. Module Plan

### 3.1 `app/model.py` — Traffic Model

#### Data Structures

```python
from dataclasses import dataclass

@dataclass
class ScenarioInputs:
    normal_lanes: int           # Total lanes in direction (≥1)
    lanes_closed: int           # Lanes blocked by work zone (≥0)
    demand_vph: float           # Traffic demand (veh/hr)
    normal_capacity_per_lane: float   # veh/hr per lane, normal conditions
    wz_capacity_per_lane: float       # veh/hr per lane, through work zone
    wz_length_miles: float      # Work zone length
    posted_speed_mph: float     # Normal speed
    wz_speed_mph: float         # Reduced speed through work zone
    analysis_duration_hours: float    # Analysis period

@dataclass
class ScenarioResults:
    open_lanes: int                    # normal_lanes - lanes_closed
    wz_capacity_vph: float             # Throughput capacity of work zone
    queue_forms: bool                  # Whether demand > capacity
    max_queue_vehicles: float          # Peak queue (vehicles)
    max_queue_miles: float             # Peak queue (miles)
    avg_delay_per_vehicle_min: float   # Average delay (minutes)
    queue_over_time: list[float]       # Queue (vehicles) at each hour [0..T]
    total_delay_veh_hours: float       # Total vehicle-hours of delay
```

#### Public Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `compute_scenario` | `(inputs: ScenarioInputs) -> ScenarioResults` | Main entry point. Validates, computes capacity, dispatches to no-queue or over-capacity path. |
| `validate_inputs` | `(inputs: ScenarioInputs) -> str \| None` | Returns error message if invalid (e.g., open lanes ≤ 0), else None. |
| `compute_capacity` | `(open_lanes: int, wz_capacity_per_lane: float) -> float` | Returns work-zone throughput capacity. |
| `compute_no_queue_delay` | `(wz_length: float, posted_speed: float, wz_speed: float) -> float` | Returns delay in minutes from speed reduction only. |
| `compute_queue_dynamics` | `(demand: float, capacity: float, duration: float) -> tuple[list[float], float, float, float]` | Deterministic queueing: returns (queue_over_time, max_queue_veh, total_delay_veh_hours, avg_delay_min). |
| `queue_to_miles` | `(queue_vehicles: float) -> float` | Converts vehicles to miles using 150 veh/mile spacing. |
| `generate_summary` | `(inputs: ScenarioInputs, results: ScenarioResults) -> str` | Plain-language scenario summary (results only, no recommendations). |
| `compute_delay_vs_demand` | `(inputs: ScenarioInputs, num_points: int = 21) -> tuple[list[float], list[float]]` | Sweeps demand ±50% of current, returns (demand_values, delay_values). |

#### Key Algorithms

**Deterministic Queueing (hour-by-hour):**

```
For each hour h in [0, duration]:
    cumulative_arrivals[h] = demand × h
    cumulative_departures[h] = min(capacity × h, cumulative_arrivals[h])
    queue[h] = cumulative_arrivals[h] - cumulative_departures[h]

max_queue = max(queue)
total_delay = sum of (queue[h] for h in each interval) — area under the queue curve
             approximated as trapezoidal: sum((queue[h] + queue[h+1]) / 2 for h in 0..T-1)
avg_delay_min = (total_delay / total_arrivals) × 60
```

**No-Queue Delay:**
```
delay_minutes = (wz_length / wz_speed - wz_length / posted_speed) × 60
```

**Queue-to-Miles:**
```
queue_miles = queue_vehicles / 150.0
```

### 3.2 `app/streamlit_app.py` — Streamlit UI

#### Layout

- **Page config:** Title "Work Zone Traffic Planner", wide layout.
- **Sidebar:** All input widgets per the requirements table (Section 2.1 of APP_REQUIREMENTS).
  - Integer inputs: `st.number_input` with `step=1` for lanes.
  - Float inputs: `st.number_input` with appropriate step sizes.
  - Defaults and minimums per the requirements table.
- **Main panel:**
  1. Error display (if validation fails — show `st.error`, no results).
  2. Key metrics row using `st.metric` or `st.columns`.
  3. Queue-over-time chart (line chart).
  4. Delay-vs-demand sensitivity chart (line chart with current demand marker).
  5. Plain-language summary in a `st.info` or `st.markdown` block.

#### Charting

Use **matplotlib** for charts (rendered via `st.pyplot`):
- **Chart 1 — Queue over Time:** X-axis = hours (0 to duration), Y-axis = queue (vehicles). Title: "Queue Length Over Time".
- **Chart 2 — Delay vs. Demand:** X-axis = demand (veh/hr, ±50% sweep), Y-axis = avg delay (min). Vertical dashed line at current demand. Title: "Average Delay vs. Demand".

---

## 4. Dependencies (`requirements.txt`)

```
streamlit>=1.30.0,<2.0
numpy>=1.24.0,<2.0
pandas>=2.0.0,<3.0
matplotlib>=3.7.0,<4.0
pytest>=7.4.0,<9.0
```

---

## 5. Input Validation Rules

| Condition | Action |
|-----------|--------|
| `normal_lanes - lanes_closed <= 0` | Display error: "All lanes are closed. Reduce closed lanes or add normal lanes." Block calculation. |
| Any numeric input < its minimum | Prevented by widget `min_value` constraints. |
| `wz_speed >= posted_speed` | Valid input (engineer choice); model calculates zero or negative speed-reduction delay → clamp to 0. |
| `demand == 0` | No queue, zero delay. Must not crash. |
| `analysis_duration` at minimum (0.5) | Must compute correctly with 1 interval. |

---

## 6. Assumptions Displayed to User

The app must display (in an expander or footer) the following assumptions:
- Deterministic flow — no stochastic variation.
- Constant demand — uniform arrival rate within the analysis period.
- Infinite queue storage — no upstream spillback modeling.
- Queue spacing: 150 vehicles per mile (passenger-car basis).
- Single bottleneck — work zone is the only capacity constraint.
- Planning-level accuracy — suitable for "what if" estimates.

---

## 7. Test Plan

Tests in `tests/test_model.py` using pytest. All tests call model functions directly (no Streamlit).

### Task 1: Capacity Calculation Tests
- 2 open lanes × 1400 wz capacity = 2800 veh/hr
- 1 open lane × 1900 = 1900 veh/hr
- 5 open lanes × 1400 = 7000 veh/hr

### Task 2: No-Queue Delay Tests
- Demand = 2000, capacity = 2800: queue_forms = False, max_queue = 0
- Delay = (2.0/45 - 2.0/65) × 60 ≈ 0.821 minutes (for wz_length=2, posted=65, wz_speed=45)
- Zero demand: delay = 0, no crash

### Task 3: Over-Capacity Queueing Tests
- Demand = 4000, capacity = 2800, duration = 8 hours:
  - Queue grows at (4000-2800) = 1200 veh/hr
  - Max queue at hour 8 = 9600 vehicles
  - Max queue miles = 9600/150 = 64.0 miles
  - Total delay = trapezoidal area under queue curve
  - Avg delay = total_delay / (4000×8) × 60 minutes
- Demand = capacity (boundary): no queue accumulates, queue_over_time all zeros

### Task 4: Edge Case Tests
- Zero open lanes (normal=2, closed=2): validate_inputs returns error string
- Zero demand: no crash, zero queue, zero delay
- Work-zone speed ≥ posted speed: no-queue delay clamps to 0 (no negative delay)
- Minimum duration (0.5 hours): computes without error

### Task 5: Sensitivity Sweep Tests
- `compute_delay_vs_demand` returns 21 points
- Demand range is [0.5 × input_demand, 1.5 × input_demand]
- Current demand value is included in the sweep points
- All returned delays are ≥ 0

### Task 6: Summary Generation Tests
- No-queue case: summary mentions "no queue" and speed-reduction delay
- Over-capacity case: summary mentions queue formation, max queue, and average delay
- Summary contains no recommendations

### Task 7: Integration — Full Scenario Compute
- `compute_scenario` with default inputs returns valid ScenarioResults
- `compute_scenario` with zero-open-lanes inputs: validate_inputs catches it (or raises)
- `compute_scenario` round-trip: inputs → results → all fields populated with correct types

---

## 8. Implementation Order

1. **`app/model.py`** — Implement all pure functions:
   - `validate_inputs`
   - `compute_capacity`
   - `compute_no_queue_delay`
   - `compute_queue_dynamics`
   - `queue_to_miles`
   - `compute_scenario` (orchestrates the above)
   - `generate_summary`
   - `compute_delay_vs_demand`

2. **`tests/test_model.py`** — Write unit tests covering Tasks 1–7.

3. **`app/streamlit_app.py`** — Build the UI:
   - Sidebar inputs with defaults/minimums.
   - Validation check and error display.
   - Metrics rendering.
   - Chart 1: Queue over time.
   - Chart 2: Delay vs. demand sensitivity.
   - Plain-language summary.
   - Assumptions expander.

4. **`requirements.txt`** — Pin dependencies.

5. **Final verification** — `pytest -q` passes, manual check of edge cases.

---

## 9. Out of Scope

Per requirements — do NOT implement:
- AI/LLM features
- Deployment automation
- External data sources or paid APIs
- Stochastic / Monte Carlo modeling
- Multi-zone or network modeling
- Vehicle-mix differentiation
- Spillback / upstream propagation
- Time-of-day demand profiles
- Recommendations in the summary
- User authentication / session persistence
- Export to PDF/Excel
