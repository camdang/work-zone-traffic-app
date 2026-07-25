# App Requirements — Work-Zone Traffic What-If Planner

**Status:** FINALIZED (pre-staged input to planning)
**Purpose of this file:** These are the finalized *requirements* — the **WHAT**, not the **HOW**. They were extracted from `plans/spec.md` so that the decisions reached during interactive Q&A live in a committed file rather than only in a chat transcript. Plan mode reads this file (plus `.claude/BEST_PRACTICES.md`) and produces an implementation plan/spec (`plans/spec.md`) deterministically, without needing a live clarifying conversation.

> This file intentionally omits implementation detail: no pseudocode, no function signatures, no step-by-step algorithm loops. Those are decided during planning. What it *does* pin down are the product behaviors and the modeling **decisions** that were previously answered conversationally.

---

## 1. Product summary & scope

A traditional Streamlit **work-zone traffic what-if planner** for transportation engineers. It models a single highway work zone on a unidirectional segment and shows the traffic impact of lane closures under different demand scenarios.

- **In scope:** one work zone, deterministic (non-stochastic) flow, constant hourly demand over a multi-hour analysis period.
- **No AI/LLM anywhere in the product.** This is ordinary application software.

---

## 2. Functional requirements

### 2.1 Inputs (sidebar)

All inputs are numeric, non-negative (enforced by minimums), and drive an automatic recompute when changed.

| Parameter | Default | Min | Unit | Meaning |
|-----------|---------|-----|------|---------|
| Normal lanes (open) | 3 | 1 | lanes | Lanes in this direction before the work zone |
| Lanes closed | 1 | 0 | lanes | Lanes blocked by the work zone |
| Traffic demand | 4000 | 0 | veh/hr | Constant hourly arrival rate |
| Normal capacity per lane | 1900 | 0 | veh/hr | Per-lane capacity outside the work zone |
| Work-zone capacity per lane | 1400 | 0 | veh/hr | Reduced per-lane capacity through the work zone |
| Work-zone length | 2.0 | 0.1 | miles | Length of the reduced-capacity segment |
| Posted speed | 65 | 1 | mph | Normal highway speed |
| Work-zone speed | 45 | 1 | mph | Reduced speed through the work zone |
| Analysis duration | 8.0 | 0.5 | hours | Time period analyzed |

### 2.2 Validation

- If **open lanes (normal − closed) ≤ 0**, the app must display an error and **block calculation** (no results shown).
- All numeric inputs must be non-negative.
- Lane counts (normal lanes, lanes closed) are **integers**; all other inputs are real-valued.

### 2.3 Outputs (main panel)

**Key metrics:**
- Work-zone throughput capacity (veh/hr)
- Whether a queue forms (Yes/No)
- Maximum queue length (vehicles)
- Maximum queue length (miles)
- Average delay per vehicle (minutes)

**Charts (two required):**
1. **Queue length over time** — queue (vehicles) across the hours of the analysis period.
2. **Delay vs. demand sensitivity** — average delay per vehicle as demand varies, with the **current demand marked**. The demand sweep is **auto-scaled to ±50% of the current input** (i.e. 0.5×–1.5×) sampled at 21 points.

**Plain-language summary:**
- A short, human-readable description of the scenario that **reports results only — no recommendations**.
- Must correctly distinguish the no-queue case (delay from speed reduction only) from the over-capacity case (queue forms; report max queue and average delay).

### 2.4 User workflow

1. Open the app in a browser.
2. Adjust sidebar inputs to define a work-zone scenario.
3. View metrics, both charts, and the summary in the main panel; results update automatically on input change.
4. Experiment with configurations to compare impacts.

---

## 3. Modeling requirements & decisions

These are the modeling **decisions** (the previously-conversational answers). They constrain correctness without prescribing code.

### 3.1 Capacity
- Work-zone throughput capacity = **open lanes × work-zone capacity per lane**, where open lanes = normal lanes − closed lanes.

### 3.2 No-queue case (demand ≤ capacity)
- No queue forms.
- The only delay is from the **speed reduction over the work-zone length** (time through the zone at work-zone speed vs. at posted speed).
- Max queue is zero (both vehicles and miles).

### 3.3 Over-capacity case (demand > capacity)
- A queue forms and is modeled with **deterministic queueing** based on cumulative arrival/departure curves:
  - Queue at any time = cumulative arrivals − cumulative departures.
  - Total delay = the area between the two curves (vehicle-hours).
  - Average delay per vehicle (minutes) = total delay ÷ total arrivals, converted to minutes.
- **Time resolution is hourly** (queue dynamics tracked hour by hour, not continuous).
- **End-of-period reporting:** if the queue has not cleared by the end of the analysis period, report the state as-is (no extrapolation beyond the period).
- In the over-capacity case, reported delay is **queueing delay only**; the speed-reduction delay component is intentionally excluded because queueing delay dominates. (Speed-reduction delay applies only to the no-queue case above.)

### 3.4 Fixed assumptions & limits (must be honored, and stated to the user where relevant)
- **Deterministic flow** — no stochastic variation.
- **Constant demand** — uniform arrival rate within the analysis period.
- **Infinite queue storage** — no upstream spillback modeling.
- **Queue-length-to-miles conversion** uses a fixed spacing assumption of **150 vehicles per mile** (passenger-car basis).
- **Single bottleneck** — the work zone is the only capacity constraint; no vehicle-mix differentiation.
- **Planning-level accuracy** — suitable for "what if" estimates, not detailed operational design.

---

## 4. Architecture requirements

(Per `.claude/BEST_PRACTICES.md`; restated here as hard requirements.)

- **Model / UI separation.** All traffic math lives in `app/model.py` as pure, side-effect-free functions. `app/streamlit_app.py` handles widgets, calls the model, and renders results only.
- Python 3.11+, Streamlit UI, pandas/numpy, and the project's existing plotting library.
- Type hints throughout; docstrings on every public function.
- Dependencies minimal and pinned in `requirements.txt`; no new services or external data sources.
- Must run unchanged in the existing Streamlit docker deploy shape.

---

## 5. Test requirements

Tests live in `tests/` and use **pytest**; `pytest -q` must pass before the build is considered done. The **model module must have unit tests with known-input/known-output cases.** Required coverage:

- **Capacity:** open lanes × work-zone per-lane capacity produces the expected total (e.g., 2 open lanes × 1400 = 2800 veh/hr).
- **No-queue delay:** demand below capacity yields zero queue and a delay driven solely by the speed differential over the zone length.
- **Over-capacity queueing:** demand above capacity produces the expected growing queue, max queue (vehicles and miles), total vehicle-hours of delay, and average delay per vehicle for a hand-checkable scenario.
- **Boundary — demand equals capacity:** no queue accumulates.
- **Edge cases:** zero open lanes (blocked/validation), zero demand (zero delay, no crash), minimum duration, and unrealistic inputs (e.g. work-zone speed ≥ posted speed) handled without NaN/crash.

---

## 6. Out of scope

- AI/LLM features inside the app.
- Deployment automation (manual deploy to the existing Streamlit docker).
- External data sources, databases, or paid APIs.
- Stochastic / Monte Carlo modeling.
- Multi-lane network or multi-zone modeling.
- Vehicle-mix differentiation (cars vs. trucks).
- Spillback / upstream congestion propagation.
- Time-of-day demand profiles (demand is constant per analysis period).
- Recommendations engine (the summary reports results only).
- User authentication / session persistence.
- Export to PDF/Excel.

---

## 7. Acceptance criteria

The build is complete when:

1. The app runs in the existing Streamlit docker without deployment-config changes.
2. All inputs render in the sidebar with the specified defaults.
3. Validation blocks calculation and shows an error when all lanes are closed.
4. Metrics display correctly for both no-queue and over-capacity scenarios.
5. The queue-length-over-time chart renders correctly.
6. The delay-vs-demand chart renders with the current demand marked and a ±50% sweep.
7. The summary accurately describes the scenario in plain language, without recommendations.
8. `pytest -q` passes with unit tests covering the model.
9. Code review reports no Blocker-level issues.
10. Manual testing confirms edge cases (zero demand, extreme demand, minimal duration) do not crash.
