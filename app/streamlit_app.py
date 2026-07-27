"""Work-Zone Traffic What-If Planner — Streamlit UI."""

import streamlit as st
import matplotlib.pyplot as plt

from app.model import compute_capacity, compute_delay, compute_sensitivity

st.set_page_config(page_title="Work-Zone Traffic Planner", layout="wide")

# --- Sidebar inputs ---
st.sidebar.header("Scenario Inputs")

normal_lanes = st.sidebar.number_input(
    "Normal lanes (open)", value=3, min_value=1, step=1
)
lanes_closed = st.sidebar.number_input(
    "Lanes closed", value=1, min_value=0, step=1
)
demand = st.sidebar.number_input(
    "Traffic demand (veh/hr)", value=4000.0, min_value=0.0, step=100.0
)
normal_capacity_per_lane = st.sidebar.number_input(
    "Normal capacity per lane (veh/hr)", value=1900.0, min_value=0.0, step=100.0
)
wz_capacity_per_lane = st.sidebar.number_input(
    "Work-zone capacity per lane (veh/hr)", value=1400.0, min_value=0.0, step=100.0
)
wz_length = st.sidebar.number_input(
    "Work-zone length (miles)", value=2.0, min_value=0.1, step=0.1
)
posted_speed = st.sidebar.number_input(
    "Posted speed (mph)", value=65.0, min_value=1.0, step=5.0
)
wz_speed = st.sidebar.number_input(
    "Work-zone speed (mph)", value=45.0, min_value=1.0, step=5.0
)
analysis_duration = st.sidebar.number_input(
    "Analysis duration (hours)", value=8.0, min_value=0.5, step=0.5
)

# --- Validation ---
open_lanes = int(normal_lanes) - int(lanes_closed)
if open_lanes <= 0:
    st.error(
        "All lanes are closed — no throughput is possible. "
        "Reduce the number of closed lanes or increase normal lanes."
    )
    st.stop()

# --- Compute results ---
results = compute_delay(
    normal_lanes=int(normal_lanes),
    lanes_closed=int(lanes_closed),
    demand=float(demand),
    normal_capacity_per_lane=float(normal_capacity_per_lane),
    wz_capacity_per_lane=float(wz_capacity_per_lane),
    wz_length=float(wz_length),
    posted_speed=float(posted_speed),
    wz_speed=float(wz_speed),
    analysis_duration=float(analysis_duration),
)

# --- Title ---
st.title("Work-Zone Traffic What-If Planner")

# --- Key metrics ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("WZ Capacity (veh/hr)", f"{results['wz_capacity']:.0f}")
col2.metric("Queue Forms", "Yes" if results["queue_forms"] else "No")
col3.metric("Max Queue (vehicles)", f"{results['max_queue_vehicles']:.0f}")
col4.metric("Max Queue (miles)", f"{results['max_queue_miles']:.1f}")
col5.metric("Avg Delay/Vehicle (min)", f"{results['avg_delay_per_vehicle']:.1f}")

# --- Chart 1: Queue Length Over Time ---
st.subheader("Queue Length Over Time")

num_hours = int(analysis_duration)
time_points = list(range(num_hours + 1))
if analysis_duration != int(analysis_duration):
    time_points.append(analysis_duration)

fig1, ax1 = plt.subplots(figsize=(8, 4))
ax1.plot(time_points, results["queue_over_time"], marker="o", linewidth=2)
ax1.set_xlabel("Hour")
ax1.set_ylabel("Queue (vehicles)")
ax1.set_title("Queue Length Over Time")
ax1.set_xlim(0, analysis_duration)
ax1.set_ylim(bottom=0)
ax1.grid(True, alpha=0.3)
st.pyplot(fig1)

# --- Chart 2: Delay vs. Demand Sensitivity ---
st.subheader("Delay vs. Demand Sensitivity")

demands_sweep, delays_sweep = compute_sensitivity(
    normal_lanes=int(normal_lanes),
    lanes_closed=int(lanes_closed),
    normal_capacity_per_lane=float(normal_capacity_per_lane),
    wz_capacity_per_lane=float(wz_capacity_per_lane),
    wz_length=float(wz_length),
    posted_speed=float(posted_speed),
    wz_speed=float(wz_speed),
    analysis_duration=float(analysis_duration),
    current_demand=float(demand),
)

fig2, ax2 = plt.subplots(figsize=(8, 4))
ax2.plot(demands_sweep, delays_sweep, linewidth=2)
ax2.axvline(x=demand, color="red", linestyle="--", linewidth=1.5, label="Current demand")
ax2.annotate(
    f"Current: {demand:.0f} veh/hr",
    xy=(demand, results["avg_delay_per_vehicle"]),
    xytext=(demand + 100, results["avg_delay_per_vehicle"] + 1),
    fontsize=9,
    color="red",
    arrowprops=dict(arrowstyle="->", color="red"),
)
ax2.set_xlabel("Demand (veh/hr)")
ax2.set_ylabel("Avg Delay per Vehicle (min)")
ax2.set_title("Delay vs. Demand")
ax2.set_ylim(bottom=0)
ax2.legend()
ax2.grid(True, alpha=0.3)
st.pyplot(fig2)

# --- Plain-language summary ---
st.subheader("Scenario Summary")

if not results["queue_forms"]:
    summary = (
        f"With {demand:.0f} veh/hr demand and a work-zone capacity of "
        f"{results['wz_capacity']:.0f} veh/hr ({open_lanes} open lanes × "
        f"{wz_capacity_per_lane:.0f} veh/hr/lane), demand is within capacity. "
        f"No queue forms. The only delay is {results['avg_delay_per_vehicle']:.1f} "
        f"minutes per vehicle due to the speed reduction from {posted_speed:.0f} mph "
        f"to {wz_speed:.0f} mph over the {wz_length:.1f}-mile work zone."
    )
else:
    summary = (
        f"With {demand:.0f} veh/hr demand exceeding the work-zone capacity of "
        f"{results['wz_capacity']:.0f} veh/hr ({open_lanes} open lanes × "
        f"{wz_capacity_per_lane:.0f} veh/hr/lane), a queue forms. "
        f"The maximum queue reaches {results['max_queue_vehicles']:.0f} vehicles "
        f"({results['max_queue_miles']:.1f} miles). The average delay per vehicle is "
        f"{results['avg_delay_per_vehicle']:.1f} minutes over the "
        f"{analysis_duration:.1f}-hour analysis period."
    )

st.info(summary)
