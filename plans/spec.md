# Implementation Spec — Work-Zone Traffic What-If Planner

**Status:** PROPOSED  
**Date:** 2026-07-27  

---

## 1. Overview

A Streamlit application that lets transportation engineers model a highway work zone and visualize traffic impacts of lane closures. Pure deterministic queueing model with no AI/LLM components.

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
│   ├── APP_DESCRIPTION.md
│   ├── APP_REQUIREMENTS.md
│   └── BEST_PRACTICES.md
└── README.md
```

### 2.1 Module responsibilities

| Module | Responsibility |
|--------|---------------|
| `app/model.py` | All traffic calculations as pure, side-effect-free functions. No Streamlit imports. |
| `app/streamlit_app.py` | Sidebar widgets, input validation display, calls model functions, renders metrics/charts/summary. |
| `tests/test_model.py` | Unit tests covering capacity, no-queue, over-capacity, boundary, and edge cases. |

---

## 3. Data model

### 3.1 Input parameters (dataclass or dict)

| Field | Type | Default | Min | Unit |
|-------|------|---------|-----|------|
| `normal_lanes` | int | 3 | 1 | lanes |
| `lanes_closed` | int | 1 | 0 | lanes |
| `demand` | float | 4000 | 0 | veh/hr |
| `normal_capacity_per_lane` | float | 1900 | 0 | veh/hr |
| `wz_capacity_per_lane` | float | 1400 | 0 | veh/hr |
| `wz_length` | float | 2.0 | 0.1 | miles |
| `posted_speed` | float | 65 | 1 | mph |
| `wz_speed` | float | 45 | 1 | mph |
| `analysis_duration` | float | 8.0 | 0.5 | hours |

### 3.2 Output results (dataclass or dict)

| Field | Type | Unit |
|-------|------|------|
| `wz_capacity` | float | veh/hr |
| `queue_forms` | bool | — |
| `max_queue_vehicles` | float | vehicles |
| `max_queue_miles` | float | miles |
| `avg_delay_per_vehicle` | float | minutes |
| `queue_over_time` | list[float] | vehicles at each hour |
| `total_delay_veh_hours` | float | vehicle-hours |

---

## 4. Model logic (`app/model.py`)

### 4.1 Public functions

```python
def compute_capacity(normal_lanes: int, lanes_closed: int, wz_capacity_per_lane: float) -> float:
    """Return work-zone throughput capacity (veh/hr).
    
    capacity = open_lanes * wz_capacity_per_lane
    where open_lanes = normal_lanes - lanes_closed
    """

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
    
    Returns a dict with keys matching the Output results table.
    Raises ValueError if open_lanes <= 0.
    """

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
```

### 4.2 Algorithm detail

**Capacity calculation:**
```
open_lanes = normal_lanes - lanes_closed
wz_capacity = open_lanes * wz_capacity_per_lane
```

**No-queue case (demand <= wz_capacity):**
```
speed_reduction_delay = (wz_length / wz_speed - wz_length / posted_speed) * 60  # minutes
avg_delay_per_vehicle = speed_reduction_delay
max_queue_vehicles = 0
max_queue_miles = 0
queue_over_time = [0.0] * (number_of_hours + 1)
total_delay_veh_hours = (speed_reduction_delay / 60) * demand * analysis_duration
```

**Over-capacity case (demand > wz_capacity):**
- Use deterministic (fluid) queueing with hourly time steps.
- For each hour `t` in `[0, analysis_duration]`:
  - Cumulative arrivals at `t` = `demand * t`
  - Cumulative departures at `t` = `wz_capacity * t`
  - Queue at `t` = max(0, cumulative_arrivals - cumulative_departures)
- `max_queue_vehicles` = max of queue array
- `max_queue_miles` = max_queue_vehicles / 150 (fixed 150 veh/mile spacing)
- Total delay (vehicle-hours) = area between cumulative arrival and departure curves, computed by trapezoidal rule on the hourly queue values.
- `avg_delay_per_vehicle` = (total_delay_veh_hours / total_arrivals) * 60 (minutes)
- Note: In over-capacity case, only queueing delay is reported (speed-reduction delay excluded as it is dominated by queue delay).

**End-of-period:** If queue has not cleared by end of analysis period, report state as-is with no extrapolation.

### 4.3 Constants

| Constant | Value | Meaning |
|----------|-------|---------|
| `VEHICLES_PER_MILE` | 150 | Queue-length-to-miles conversion factor |

---

## 5. UI Layout (`app/streamlit_app.py`)

### 5.1 Page config
- `st.set_page_config(page_title="Work-Zone Traffic Planner", layout="wide")`

### 5.2 Sidebar inputs
- All inputs rendered via `st.sidebar.number_input(...)` with defaults, mins, and steps as per the input table.
- `normal_lanes` and `lanes_closed` use `step=1` (integer).
- All others use appropriate float steps.

### 5.3 Validation
- Compute `open_lanes = normal_lanes - lanes_closed`
- If `open_lanes <= 0`: display `st.error("All lanes are closed...")` and `st.stop()` — no further output rendered.

### 5.4 Main panel layout

1. **Title:** `st.title("Work-Zone Traffic What-If Planner")`
2. **Key metrics:** displayed using `st.metric()` in columns:
   - Work-zone capacity (veh/hr)
   - Queue forms (Yes/No)
   - Max queue (vehicles)
   - Max queue (miles)
   - Avg delay/vehicle (min)
3. **Chart 1 — Queue Length Over Time:**
   - X-axis: Hour (0 to analysis_duration)
   - Y-axis: Queue (vehicles)
   - Plotted using matplotlib via `st.pyplot()`
4. **Chart 2 — Delay vs. Demand Sensitivity:**
   - X-axis: Demand (veh/hr), range 0.5× to 1.5× current demand
   - Y-axis: Average delay per vehicle (minutes)
   - Current demand marked with a vertical dashed line and annotation
   - Plotted using matplotlib via `st.pyplot()`
5. **Summary:** `st.info(...)` with a plain-language description of the scenario results.

### 5.5 Summary generation logic

No-queue case:
> "With {demand} veh/hr demand and a work-zone capacity of {capacity} veh/hr ({open_lanes} open lanes × {wz_cap_per_lane} veh/hr/lane), demand is within capacity. No queue forms. The only delay is {delay:.1f} minutes per vehicle due to the speed reduction from {posted_speed} mph to {wz_speed} mph over the {wz_length}-mile work zone."

Over-capacity case:
> "With {demand} veh/hr demand exceeding the work-zone capacity of {capacity} veh/hr ({open_lanes} open lanes × {wz_cap_per_lane} veh/hr/lane), a queue forms. The maximum queue reaches {max_q_veh:.0f} vehicles ({max_q_mi:.1f} miles). The average delay per vehicle is {avg_delay:.1f} minutes over the {duration}-hour analysis period."

---

## 6. Dependencies (`requirements.txt`)

```
streamlit==1.36.0
numpy==1.26.4
pandas==2.2.2
matplotlib==3.9.1
pytest==8.2.2
```

---

## 7. Test plan (`tests/test_model.py`)

Tests use pytest. Each test calls model functions directly with known inputs and asserts expected outputs.

### Task 1: Test capacity calculation
- **test_capacity_basic:** 3 normal lanes, 1 closed, 1400 wz cap → 2 × 1400 = 2800 veh/hr
- **test_capacity_no_closure:** 3 normal lanes, 0 closed, 1400 wz cap → 3 × 1400 = 4200 veh/hr
- **test_capacity_all_closed:** 3 normal lanes, 3 closed → raises ValueError (0 open lanes)

### Task 2: Test no-queue case
- **test_no_queue_delay:** demand=2000, capacity=2800 → queue_forms=False, max_queue=0, delay = (2.0/45 - 2.0/65)*60 ≈ 0.82 min
- **test_demand_equals_capacity:** demand=2800, capacity=2800 → no queue forms (boundary)

### Task 3: Test over-capacity queueing
- **test_over_capacity_basic:** demand=4000, capacity=2800, duration=8h
  - Queue grows at 1200 veh/hr excess
  - Max queue at end of period = 1200 × 8 = 9600 vehicles
  - Max queue miles = 9600 / 150 = 64.0 miles
  - Total delay = area under queue curve (triangle if it doesn't clear, or trapezoid sum)
  - Avg delay = total_delay / total_arrivals * 60 minutes
- **test_queue_over_time_shape:** verify queue_over_time has correct hourly values [0, 1200, 2400, ...]

### Task 4: Test edge cases
- **test_zero_demand:** demand=0 → no queue, zero delay, no crash
- **test_minimum_duration:** duration=0.5h with over-capacity → correct proportional results
- **test_wz_speed_equals_posted:** wz_speed=65, posted_speed=65, demand<capacity → zero delay
- **test_wz_speed_exceeds_posted:** wz_speed=70, posted_speed=65, demand<capacity → negative speed-reduction handled gracefully (delay clipped to 0 or reported as 0)

### Task 5: Test sensitivity function
- **test_sensitivity_returns_21_points:** verify length of returned lists is 21
- **test_sensitivity_range:** verify demand range spans 0.5× to 1.5× current demand
- **test_sensitivity_includes_current:** verify current demand value is in the demand list

---

## 8. Implementation order

1. Create `app/__init__.py`, `tests/__init__.py`
2. Implement `app/model.py` (capacity, delay, sensitivity functions)
3. Write `tests/test_model.py` and verify all pass
4. Implement `app/streamlit_app.py` (sidebar, validation, metrics, charts, summary)
5. Create `requirements.txt`
6. Run `pytest -q` — confirm green
7. Manual smoke test with `streamlit run app/streamlit_app.py`

---

## 9. Assumptions & fixed parameters

- Deterministic flow (no stochastic variation)
- Constant demand (uniform arrival rate)
- Infinite queue storage (no spillback)
- 150 vehicles/mile spacing for queue-to-miles conversion
- Single bottleneck (work zone is sole capacity constraint)
- No vehicle-mix differentiation
- Planning-level accuracy only

---

## 10. Out of scope

- AI/LLM features
- Deployment automation
- External data sources or paid APIs
- Stochastic/Monte Carlo modeling
- Multi-zone or network modeling
- Vehicle-mix differentiation
- Spillback/upstream propagation
- Time-of-day demand profiles
- Recommendations engine
- User authentication
- Export to PDF/Excel
