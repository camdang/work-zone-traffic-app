"""Streamlit UI for the Work-Zone Traffic What-If Planner."""

import matplotlib.pyplot as plt
import streamlit as st

from app.model import compute_capacity, compute_delay, compute_sensitivity

st.set_page_config(page_title="Work-Zone Traffic Planner", layout="wide")

# --- Sidebar Inputs ---
st.sidebar.header("Scenario Parameters")

normal_lanes = st.sidebar.number_input(
    "Normal lanes (open)", min_value=1, value=3, step=1
)
lanes_closed = st.sidebar.number_input(
    "Lanes closed", min_value=0, value=1, step=1
)
demand = st.sidebar.number_input(
    "Traffic demand (veh/hr)", min_value=0.0, value=4000.0, step=100.0
)
normal_capacity_per_lane = st.sidebar.number_input(
    "Normal capacity per lane (veh/hr)", min_value=0.0, value=1900.0, step=50.0
)
wz_capacity_per_lane = st.sidebar.number_input(
    "Work-zone capacity per lane (veh/hr)", min_value=0.0, value=1400.0, step=50.0
)
wz_length = st.sidebar.number_input(
    "Work-zone length (miles)", min_value=0.1, value=2.0, step=0.1
)
posted_speed = st.sidebar.number_input(
    "Posted speed (mph)", min_value=1.0, value=65.0, step=5.0
)
wz_speed = st.sidebar.number_input(
    "Work-zone speed (mph)", min_value=1.0, value=45.0, step=5.0
)
analysis_duration = st.sidebar.number_input(
    "Analysis duration (hours)", min_value=0.5, value=8.0, step=0.5
)

# --- Validation ---
open_lanes = normal_lanes - lanes_closed
if open_lanes <= 0:
    st.error(
        "All lanes are closed. Adjust the number of normal lanes or lanes closed "
        "to have at least one open lane."
    )
    st.stop()

# --- Compute Results ---
results = compute_delay(
    normal_lanes=int(normal_lanes),
    lanes_closed=int(lanes_closed),
    demand=demand,
    normal_capacity_per_lane=normal_capacity_per_lane,
    wz_capacity_per_lane=wz_capacity_per_lane,
    wz_length=wz_length,
    posted_speed=posted_speed,
    wz_speed=wz_speed,
    analysis_duration=analysis_duration,
)

# --- Title ---
st.title("Work-Zone Traffic What-If Planner")

# --- Key Metrics ---
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("WZ Capacity", f"{results['wz_capacity']:.0f} veh/hr")
col2.metric("Queue Forms", "Yes" if results["queue_forms"] else "No")
col3.metric("Max Queue (veh)", f"{results['max_queue_vehicles']:.0f} veh")
col4.metric("Max Queue (mi)", f"{results['max_queue_miles']:.1f} mi")
col5.metric("Avg Delay", f"{results['avg_delay_per_vehicle']:.1f} min")

# --- Chart 1: Queue Length Over Time ---
st.subheader("Queue Length Over Time")

queue_data = results["queue_over_time"]
num_hours = int(analysis_duration)
fractional = analysis_duration - num_hours
time_points = list(range(num_hours + 1))
if fractional > 0:
    time_points_float = [float(t) for t in time_points] + [analysis_duration]
else:
    time_points_float = [float(t) for t in time_points]

fig1, ax1 = plt.subplots(figsize=(8, 4))
ax1.plot(time_points_float, queue_data, marker="o", linewidth=2, color="#1f77b4")
ax1.set_xlabel("Hour")
ax1.set_ylabel("Queue (vehicles)")
ax1.set_title("Queue Length Over Time")
ax1.set_xlim(0, analysis_duration)
ax1.set_ylim(bottom=0)
ax1.grid(True, alpha=0.3)
plt.tight_layout()
st.pyplot(fig1)
plt.close(fig1)

# --- Chart 2: Delay vs. Demand Sensitivity ---
st.subheader("Delay vs. Demand Sensitivity")

if demand > 0:
    demands_sweep, delays_sweep = compute_sensitivity(
        normal_lanes=int(normal_lanes),
        lanes_closed=int(lanes_closed),
        normal_capacity_per_lane=normal_capacity_per_lane,
        wz_capacity_per_lane=wz_capacity_per_lane,
        wz_length=wz_length,
        posted_speed=posted_speed,
        wz_speed=wz_speed,
        analysis_duration=analysis_duration,
        current_demand=demand,
    )

    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.plot(demands_sweep, delays_sweep, linewidth=2, color="#2ca02c")
    ax2.axvline(x=demand, linestyle="--", color="#d62728", linewidth=1.5, label="Current demand")
    ax2.annotate(
        f"Current: {demand:.0f}",
        xy=(demand, 0),
        xytext=(demand + (0.05 * demand), max(delays_sweep) * 0.8 if max(delays_sweep) > 0 else 1),
        fontsize=9,
        color="#d62728",
        arrowprops=dict(arrowstyle="->", color="#d62728"),
    )
    ax2.set_xlabel("Demand (veh/hr)")
    ax2.set_ylabel("Avg Delay per Vehicle (min)")
    ax2.set_title("Delay vs. Demand")
    ax2.set_ylim(bottom=0)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    st.pyplot(fig2)
    plt.close(fig2)
else:
    st.info("Set demand > 0 to see the sensitivity chart.")

# --- Summary ---
st.subheader("Scenario Summary")

wz_cap = results["wz_capacity"]
if not results["queue_forms"]:
    summary = (
        f"With {demand:.0f} veh/hr demand and a work-zone capacity of {wz_cap:.0f} veh/hr "
        f"({open_lanes} open lanes × {wz_capacity_per_lane:.0f} veh/hr/lane), "
        f"demand is within capacity. No queue forms. "
        f"The only delay is {results['avg_delay_per_vehicle']:.1f} minutes per vehicle "
        f"due to the speed reduction from {posted_speed:.0f} mph to {wz_speed:.0f} mph "
        f"over the {wz_length:.1f}-mile work zone."
    )
else:
    summary = (
        f"With {demand:.0f} veh/hr demand exceeding the work-zone capacity of {wz_cap:.0f} veh/hr "
        f"({open_lanes} open lanes × {wz_capacity_per_lane:.0f} veh/hr/lane), "
        f"a queue forms. The maximum queue reaches {results['max_queue_vehicles']:.0f} vehicles "
        f"({results['max_queue_miles']:.1f} miles). "
        f"The average delay per vehicle is {results['avg_delay_per_vehicle']:.1f} minutes "
        f"over the {analysis_duration:.1f}-hour analysis period."
    )

st.info(summary)

# --- Assumptions footer ---
st.sidebar.markdown("---")
st.sidebar.caption(
    "Assumptions: deterministic flow, constant demand, infinite queue storage, "
    "150 veh/mile spacing, single bottleneck, planning-level accuracy."
)
