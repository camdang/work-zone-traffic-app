# Application Description

Build a Streamlit **work-zone traffic what-if planner** for transportation engineers. This is a traditional app — **no AI inside it.**

The tool should let a user model a highway work zone and see the traffic impact of lane closures:

**Inputs (sidebar):**
- Number of normal (open) lanes in this direction
- Number of lanes closed by the work zone
- Hourly traffic demand (vehicles/hour)
- Per-lane capacity, normal (default ~1,900 vph) and reduced through the work zone (default lower, e.g. ~1,400 vph)
- Work-zone length (miles) and posted/work-zone speed
- Analysis duration (hours)

**Model (in `app/model.py`, pure functions):**
- Compute work-zone throughput capacity from open lanes × reduced per-lane capacity.
- If demand ≤ capacity: no queue; delay comes from the speed reduction over the zone length.
- If demand > capacity: a queue forms — use deterministic queueing to compute max queue (vehicles and miles), total vehicle-hours of delay, and average delay per vehicle (minutes).

**Outputs (main panel):**
- Key metrics: throughput, whether a queue forms, max queue length, avg delay/vehicle.
- At least one chart (e.g., delay or queue vs. demand, or a queue-over-time profile).
- A short plain-language summary of the scenario.
