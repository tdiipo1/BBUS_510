import io
import math
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

# ------------------------------
# Configuration / Defaults
# ------------------------------
st.set_page_config(page_title="Littlefield Advisor (B BUS 509 | Group 3)", layout="wide")

DEFAULT_PROCESS_TIMES = {
    "S1_hours": 3.6,          # Station 1
    "S2_hours_total": 0.7 + 1.2,  # Station 2 (two steps)
    "S3_hours": 4.7           # Station 3
}
DEFAULTS = {
    "target_util_pct": 85.0,
    "sell_util_threshold_pct": 60.0,
    "min_days_for_signal": 3,
    "current_day": 50,
    "days_lockout": 218,
}

# --- File Mapping Definitions ---
FILE_LOGIC_MAP = {
    "orders": "jobs accepted",
    "queue1": "queued for station 1",
    "queue2": "queued for station 2",
    "queue3": "queued for station 3",
    "util1": "utilization of station 1",
    "util2": "utilization of station 2",
    "util3": "utilization of station 3",
}

FILE_CUE_MAP = {
    "orders": "Plot of number of jobs accepted each day.xlsx",
    "queue1": "Plot of daily average number of kits queued for station 1.xlsx",
    "queue2": "Plot of daily average number of kits queued for station 2.xlsx",
    "queue3": "Plot of daily average number of kits queued for station 3.xlsx",
    "util1": "Plot of utilization of station 1, averaged over each day.xlsx",
    "util2": "Plot of utilization of station 2, averaged over each day.xlsx",
    "util3": "Plot of utilization of station 3, averaged over each day.xlsx",
}
# --- End File Mapping Definitions ---


# ------------------------------
# Helpers
# ------------------------------

def linear_fit(x, y):
    """Calculates slope and intercept for y = b*x + a"""
    if len(x) < 2:
        return 0.0, float(np.mean(y)) if len(y) else 0.0
    b, a = np.polyfit(x, y, 1)  # y = b*x + a
    return float(b), float(a)

def moving_average(arr, window):
    s = pd.Series(arr, dtype="float")
    return s.rolling(window=window, min_periods=1).mean().to_numpy()

def machines_needed(rate_per_day, proc_hours, target_util_pct):
    target_util = max(0.05, min(1.00, target_util_pct / 100.0))
    cap_per_machine = (24.0 * target_util) / proc_hours
    return int(math.ceil(max(0.0, rate_per_day) / cap_per_machine))

def detect_phase(days, arrivals, ma_window, reg_lookback):
    """
    Analyzes the slope of the moving average to detect the current phase.
    Returns: (phase_str, slope, intercept)
    """
    s = pd.Series(arrivals, dtype="float")
    ma = s.rolling(window=ma_window, min_periods=1).mean().to_numpy()
    
    x_all = days.astype(float)
    
    K = min(reg_lookback, len(x_all))
    x_recent = x_all[-K:]
    y_recent = ma[-K:]
    
    slope_recent, intercept_recent = linear_fit(x_recent, y_recent)
    
    FLAT_THRESHOLD = 0.1 
    
    if slope_recent > FLAT_THRESHOLD:
        phase = "GROWTH"
        return phase, slope_recent, intercept_recent
        
    elif slope_recent < -FLAT_THRESHOLD:
        phase = "DECLINE"
        return phase, slope_recent, intercept_recent
        
    else:
        phase = "PLATEAU"
        slope = 0.0
        intercept = float(np.mean(y_recent))
        return phase, slope, intercept

def build_forecast_array(start_day, end_day, phase, slope, intercept):
    """Builds a forecast array based on the detected phase."""
    days = np.arange(start_day, end_day + 1)
    
    if phase == "GROWTH" or phase == "DECLINE":
        vals = [max(0.0, slope * t + intercept) for t in days]
    else: # PLATEAU
        vals = [max(0.0, intercept) for t in days]
    
    return days, np.array(vals)

def suggest_s2_policy(
    recent_s2_queue,
    recent_s2_util,
    recent_s3_queue,
    phase_is_growth: bool,
    phase_is_plateau: bool,
    phase_is_decline: bool,
    have_s2: int,
    need_s2_peak: int,
    target_util_pct: float,
):
    """
    Returns: (policy, reasons[])
    policy in {"FIFO", "pri2", "pri4"}
    """
    reasons = []
    policy = "FIFO"

    def rising(seq, eps=0.01):
        return len(seq) >= 2 and (seq[-1] - seq[0]) > eps

    q2_rising = rising(recent_s2_queue or [])
    q3_rising = rising(recent_s3_queue or [])

    if recent_s2_util:
        s2_busy = np.mean(recent_s2_util) >= target_util_pct
    else:
        s2_busy = (have_s2 < need_s2_peak) or q2_rising

    if phase_is_growth and (have_s2 < need_s2_peak) and q2_rising:
        policy = "pri2"
        reasons.append("Growth + S2 under capacity and queue rising — prioritize initial (short) tests to raise throughput.")
        return policy, reasons

    if (phase_is_plateau or phase_is_decline) and (q2_rising or q3_rising):
        policy = "pri4"
        reasons.append("Later phase with testing/tuning queues rising — prioritize final tests to protect due dates.")
        return policy, reasons

    if q3_rising and s2_busy:
        policy = "pri4"
        reasons.append("Tuning queue building; expect waves of finals — prioritize final tests (pri4).")
        return policy, reasons

    reasons.append("No abnormal S2 congestion detected — stick with FIFO for stability.")
    return policy, reasons

def analyze_station(recent_utils, recent_queue, needed, have, target_util_pct, sell_util_threshold_pct, min_days_for_signal, station_name):
    """
    Robust: will still BUY with rising queue + have<need even if no utilization file uploaded.
    """
    rec, bullets = "HOLD", []

    if len(recent_utils) == 0:
        avg_util = float('nan')
        high_util = False
        low_util  = False
    else:
        avg_util = float(np.mean(recent_utils))
        if len(recent_utils) >= min_days_for_signal:
            high_util = all(u >= target_util_pct for u in recent_utils[-min_days_for_signal:])
            low_util  = all(u <= sell_util_threshold_pct for u in recent_utils[-min_days_for_signal:])
        else:
            high_util = avg_util >= target_util_pct
            low_util  = avg_util <= sell_util_threshold_pct

    queue_trend = float(recent_queue[-1] - recent_queue[0]) if len(recent_queue) >= 2 else 0.0
    rising_queue = queue_trend > 0.0
    below_need  = have < needed

    if below_need and (high_util or rising_queue):
        rec = f"BUY 1 {station_name}"
        bullets.append(f"Below target: have {have}, need {needed}.")
        if not np.isnan(avg_util):
            bullets.append(f"Avg util {avg_util:.1f}% (target {target_util_pct}%).")
        else:
            bullets.append("No utilization file — using queues and capacity gap to advise.")
        bullets.append(f"Queue trend: {'rising' if rising_queue else 'flat/unknown'}.")
    elif have > needed:
        if low_util and have > 1:
            rec = f"SELL 1 {station_name}"
            bullets.append(f"Excess capacity: have {have} > need {needed}. Util looks low.")
        else:
            bullets.append(f"Have {have} > need {needed}, but not safe to sell yet.")
    else:
        if np.isnan(avg_util):
            bullets.append(f"Capacity aligned: have {have}, need {needed}. (No util data uploaded.)")
        else:
            bullets.append(f"Capacity aligned: have {have}, need {needed}. Avg util {avg_util:.1f}%.")

    return rec, bullets

def read_df(file, kind: str):
    if file is None:
        return None
    try:
        if file.name.lower().endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        st.error(f"Error reading {file.name}: {e}")
        return None

    cols = {c.lower(): c for c in df.columns}

    if "day" in cols and "data" in cols:
        if kind == "orders":
            df = df.rename(columns={cols["day"]: "Day", cols["data"]: "Arrivals"})
            return df[["Day", "Arrivals"]]
        if kind == "util":
            df = df.rename(columns={cols["day"]: "Day", cols["data"]: "UtilPct"})
            return df[["Day", "UtilPct"]]
        if kind == "queue":
            df = df.rename(columns={cols["day"]: "Day", cols["data"]: "Queue"})
            return df[["Day", "Queue"]]
            
    elif kind == "orders" and "day" in cols and "arrivals" in cols:
        df = df.rename(columns={cols["day"]: "Day", cols["arrivals"]: "Arrivals"})
        return df[["Day", "Arrivals"]]

    st.warning(f"Could not parse file: `{file.name}`. Expected 'day' and 'data' columns.")
    return None

# ------------------------------
# UI
# ------------------------------
st.title("Littlefield Advisor (B BUS 509 | Group 3) — Dynamic Forecast & Capacity Recommendations")

st.sidebar.header("Inputs / Parameters")
current_day = st.sidebar.number_input("Current simulated day", min_value=1, max_value=268, value=DEFAULTS["current_day"], step=1)
target_util_pct = st.sidebar.slider("Target utilization (%)", min_value=50, max_value=100, value=int(DEFAULTS["target_util_pct"]), step=1)
sell_util_threshold_pct = st.sidebar.slider("Sell utilization threshold (%)", min_value=20, max_value=80, value=60, step=1)
min_days_for_signal = st.sidebar.slider("Consecutive days to confirm signal", min_value=2, max_value=7, value=DEFAULTS["min_days_for_signal"], step=1)
lockout_day = st.sidebar.number_input("Final decision cutoff day (no changes after)", min_value=1, max_value=268, value=DEFAULTS["days_lockout"], step=1)

st.sidebar.subheader("Data-Driven Forecast Parameters")
ma_window = st.sidebar.select_slider(
    "Moving Average Window (days)",
    options=[3, 5, 7, 14],
    value=7,
    help="How many days to smooth the arrival data? 7 is a good default."
)
reg_lookback = st.sidebar.slider(
    "Regression Lookback (days for slope)",
    min_value=7,
    max_value=40,
    value=21,
    step=1,
    help="How many recent days to use to detect the current trend (phase)? ~2-3 weeks is good."
)

st.sidebar.subheader("Process times (hours per job)")
S1_hours = st.sidebar.number_input("Station 1 (Stuffing)", min_value=0.1, max_value=24.0, value=DEFAULT_PROCESS_TIMES["S1_hours"], step=0.1)
S2_hours_total = st.sidebar.number_input("Station 2 (Testing total: 0.7+1.2)", min_value=0.1, max_value=24.0, value=DEFAULT_PROCESS_TIMES["S2_hours_total"], step=0.1)
S3_hours = st.sidebar.number_input("Station 3 (Tuning)", min_value=0.1, max_value=24.0, value=DEFAULT_PROCESS_TIMES["S3_hours"], step=0.1)

st.sidebar.subheader("Current Machines (user input)")
have_S1 = st.sidebar.number_input("Stuffers (S1) you currently own", min_value=1, max_value=10, value=1, step=1)
have_S2 = st.sidebar.number_input("Testers (S2) you currently own", min_value=1, max_value=10, value=1, step=1)
have_S3 = st.sidebar.number_input("Tuners (S3) you currently own", min_value=1, max_value=10, value=1, step=1)

st.markdown("### 1. Upload Littlefield Exports")
st.caption("Drag and drop all your exported CSV or XLSX files here at once.")

uploaded_files = st.file_uploader(
    "Upload ALL Littlefield exports (CSV or XLSX).",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
    label_visibility="collapsed"
)

st.markdown("**Expected files (7 total):**")
st.markdown(f"""
* `{FILE_CUE_MAP['orders']}` **(Required)**
* `{FILE_CUE_MAP['queue1']}` (Optional)
* `{FILE_CUE_MAP['queue2']}` (Optional)
* `{FILE_CUE_MAP['queue3']}` (Optional)
* `{FILE_CUE_MAP['util1']}` (Optional)
* `{FILE_CUE_MAP['util2']}` (Optional)
* `{FILE_CUE_MAP['util3']}` (Optional)
""")

if not uploaded_files:
    st.info("➡️ Upload your exported files to begin. The 'jobs accepted' file is required.")
    st.stop()

# --- File Mapping/Dispatcher Logic ---
data_files = {key: None for key in FILE_LOGIC_MAP}
unmapped_files = []

for file in uploaded_files:
    found = False
    file_name_lower = file.name.lower()
    for key, pattern in FILE_LOGIC_MAP.items():
        if pattern in file_name_lower:
            data_files[key] = file
            found = True
            break
    if not found:
        unmapped_files.append(file.name)

# Read the data
orders = read_df(data_files["orders"], kind="orders")
util1 = read_df(data_files["util1"], kind="util")
util2 = read_df(data_files["util2"], kind="util")
util3 = read_df(data_files["util3"], kind="util")
queue1 = read_df(data_files["queue1"], kind="queue")
queue2 = read_df(data_files["queue2"], kind="queue")
queue3 = read_df(data_files["queue3"], kind="queue")

# --- Updated File Status Cues ---
st.markdown("### 2. File Status")
if orders is not None:
    st.success(f"✅ **Orders** file loaded: `{data_files['orders'].name}`")
else:
    st.error(f"❌ **Orders file is missing!** Please upload: `{FILE_CUE_MAP['orders']}`.")
    st.stop() 

with st.expander("Show status for optional files (queues/utilization)"):
    for key, file_obj in data_files.items():
        if key == "orders": continue
        if file_obj:
            st.success(f"✅ **{key}** file loaded: `{file_obj.name}`")
        else:
            st.warning(f"⚠️ **{key}** file not found. Expected: `{FILE_CUE_MAP[key]}` (Optional)")
    if unmapped_files:
        st.warning(f"Unmapped files (ignored): {unmapped_files}")
# --- End of File Status ---

# ✅ THEN TRIM
orders = orders.dropna(subset=["Day", "Arrivals"]).copy()
orders = orders.sort_values("Day")
orders = orders[orders["Day"] <= current_day]

if len(orders) < 5:
    st.error("Need at least 5 data points to fit a trend.")
    st.stop()

last_day_in_file = int(orders["Day"].max())
if current_day > last_day_in_file:
    st.warning(
        f"You set current day to {current_day}, but latest data only goes up to day {last_day_in_file}. "
        f"Forecast will be based on data up to day {last_day_in_file}."
    )
    orders = orders[orders["Day"] <= last_day_in_file]

# ------------------------------
# Forecast
# ------------------------------
st.markdown(f"### 3. Forecast (Data-Driven)")

days_arr = orders["Day"].to_numpy()
arrivals_arr = orders["Arrivals"].to_numpy()

phase, slope, intercept = detect_phase(
    days=days_arr,
    arrivals=arrivals_arr,
    ma_window=ma_window,
    reg_lookback=reg_lookback
)

future_days, forecast_vals = build_forecast_array(
    start_day=current_day,
    end_day=min(268, current_day + 30),
    phase=phase,
    slope=slope,
    intercept=intercept
)

today_rate = float(forecast_vals[0]) if len(forecast_vals) > 0 else 0.0
peak_horizon = float(np.max(forecast_vals)) if len(forecast_vals) > 0 else today_rate

# Capacity needs
need_S1_today = machines_needed(today_rate, S1_hours, target_util_pct)
need_S2_today = machines_needed(today_rate, S2_hours_total, target_util_pct)
need_S3_today = machines_needed(today_rate, S3_hours, target_util_pct)

need_S1_peak = machines_needed(peak_horizon, S1_hours, target_util_pct)
need_S2_peak = machines_needed(peak_horizon, S2_hours_total, target_util_pct)
need_S3_peak = machines_needed(peak_horizon, S3_hours, target_util_pct)

# Phase flags
phase_is_growth  = (phase == "GROWTH")
phase_is_plateau = (phase == "PLATEAU")
phase_is_decline = (phase == "DECLINE")

# Header metrics
st.markdown(f"#### Detected Phase: **{phase}** — Current day: **{current_day}**")
colA, colB, colC, colD = st.columns(4)
colA.metric("Slope (orders/day²)", f"{slope:.4f}")
colB.metric("Intercept (orders/day)", f"{intercept:.2f}")
colC.metric("Today's forecast (orders/day)", f"{today_rate:.2f}")
colD.metric("30-day peak in view", f"{peak_horizon:.2f}")

# ------------------------------
# Plot
# ------------------------------
hist_df = orders[["Day", "Arrivals"]].copy()
hist_df["MA"] = pd.Series(arrivals_arr, dtype="float").rolling(window=ma_window, min_periods=1).mean()

forecast_df = pd.DataFrame({"Day": future_days, "Forecast": forecast_vals})

base = alt.Chart(hist_df).encode(x="Day:Q")
chart_raw = base.mark_circle(size=50, opacity=0.3, color="#AAA").encode(
    y="Arrivals:Q", 
    tooltip=["Day", "Arrivals"]
)
chart_ma = base.mark_line(color="orange", opacity=0.8).encode(
    y="MA:Q",
    tooltip=["Day", alt.Tooltip("MA", format=".2f")]
)
chart_forecast = (
    alt.Chart(forecast_df)
    .mark_line(color="red", strokeDash=[3,3])
    .encode(x="Day:Q", y="Forecast:Q", tooltip=["Day", alt.Tooltip("Forecast", format=".2f")])
)
st.altair_chart(
    (chart_raw + chart_ma + chart_forecast).properties(height=300), 
    use_container_width=True
)

st.caption(f"""
**How this forecast was built:**
- We smoothed your raw arrivals using a **{ma_window}-day** moving average (orange line).
- We analyzed the last **{reg_lookback} days** of that average to find the trend.
- The trend was detected as **{phase}**.
- The red dashed line is the 30-day forecast based on this trend.
- Recommendations use the highest point in this 30-day view ('peak in view').
""")

# ------------------------------
# Util/queue helper
# ------------------------------
def get_recent_series(df, colname):
    if df is None or colname not in df.columns:
        return []
    d = df.sort_values("Day")
    d = d[d["Day"] <= current_day]
    N = min(7, len(d)) # Look at last 7 days of data
    return d[colname].tail(N).to_list()

recent_u1 = get_recent_series(util1, "UtilPct")
recent_u2 = get_recent_series(util2, "UtilPct")
recent_u3 = get_recent_series(util3, "UtilPct")
recent_q1 = get_recent_series(queue1, "Queue")
recent_q2 = get_recent_series(queue2, "Queue")
recent_q3 = get_recent_series(queue3, "Queue")

# ------------------------------
# S2 Queue Policy Suggestion
# ------------------------------
s2_policy, s2_policy_reasons = suggest_s2_policy(
    recent_s2_queue=recent_q2 or [],
    recent_s2_util=recent_u2 or [],
    recent_s3_queue=recent_q3 or [],
    phase_is_growth=phase_is_growth,
    phase_is_plateau=phase_is_plateau,
    phase_is_decline=phase_is_decline,
    have_s2=have_S2,
    need_s2_peak=need_S2_peak,
    target_util_pct=target_util_pct,
)

# ------------------------------
# Recommendations
# ------------------------------
rec_S1, bullets_S1 = analyze_station(recent_u1, recent_q1, need_S1_peak, have_S1, target_util_pct, sell_util_threshold_pct, min_days_for_signal, "S1 (Stuffer)")
rec_S2, bullets_S2 = analyze_station(recent_u2, recent_q2, need_S2_peak, have_S2, target_util_pct, sell_util_threshold_pct, min_days_for_signal, "S2 (Tester)")
rec_S3, bullets_S3 = analyze_station(recent_u3, recent_q3, need_S3_peak, have_S3, target_util_pct, sell_util_threshold_pct, min_days_for_signal, "S3 (Tuner)")

st.markdown("### 4. Recommendations")
cols = st.columns(3)
for i, (title, rec, bullets) in enumerate([
    ("Station 1 — Stuffing", rec_S1, bullets_S1),
    ("Station 2 — Testing", rec_S2, bullets_S2),
    ("Station 3 — Tuning", rec_S3, bullets_S3),
]):
    with cols[i]:
        st.subheader(title)
        st.markdown(f"**Action:** {rec}")
        for b in bullets:
            st.write("• " + b)

st.markdown("### Station 2 — Queue Policy Suggestion")
st.markdown(f"**Suggested rule:** `{s2_policy}`")
for r in s2_policy_reasons:
    st.write("• " + r)
st.caption("Remember: change this in the Littlefield UI (Scheduling → Station 2). This app is only advising.")


# ------------------------------
# --- NEW: Capacity Calculations ---
# ------------------------------
target_util_float = target_util_pct / 100.0
cap_per_machine_S1 = (24.0 * target_util_float) / S1_hours
cap_per_machine_S2 = (24.0 * target_util_float) / S2_hours_total
cap_per_machine_S3 = (24.0 * target_util_float) / S3_hours

cap_station_S1 = cap_per_machine_S1 * have_S1
cap_station_S2 = cap_per_machine_S2 * have_S2
cap_station_S3 = cap_per_machine_S3 * have_S3

cap_system = min(cap_station_S1, cap_station_S2, cap_station_S3)

# ------------------------------
# --- UPDATED: Capacity Analysis Table ---
# ------------------------------
st.markdown("### 5. Capacity Analysis")

# --- NEW: System Bottleneck Metric ---
st.metric(
    label=f"System Bottleneck Capacity (at {target_util_pct}% Util)",
    value=f"{cap_system:.2f} jobs/day"
)
st.caption("This is the maximum sustainable output of your factory with its current machines. Compare this to the '30-Day Peak Need'.")


# --- UPDATED: Capacity Table ---
cap_tab_data = {
    "": [
        "**Station Capacity (jobs/day)**", 
        "**Cap per Machine (jobs/day)**", 
        "---", 
        "30-Day Peak Need (machines)", 
        "Have Now (machines)", 
        "Today Need (machines)"
    ],
    "S1 Stuffers": [
        f"{cap_station_S1:.2f}", 
        f"{cap_per_machine_S1:.2f}", 
        "---", 
        need_S1_peak, 
        have_S1, 
        need_S1_today
    ],
    "S2 Testers": [
        f"{cap_station_S2:.2f}", 
        f"{cap_per_machine_S2:.2f}", 
        "---", 
        need_S2_peak, 
        have_S2, 
        need_S2_today
    ],
    "S3 Tuners": [
        f"{cap_station_S3:.2f}", 
        f"{cap_per_machine_S3:.2f}", 
        "---", 
        need_S3_peak, 
        have_S3, 
        need_S3_today
    ],
}
cap_tab = pd.DataFrame(cap_tab_data)
st.dataframe(cap_tab, use_container_width=True, hide_index=True)


# ------------------------------
# Lockout
# ------------------------------
if current_day >= lockout_day:
    st.warning(f"⚠️ You are at/after the lockout day ({lockout_day}). Ensure your final configuration is already set.")

# ------------------------------
# Export snapshot
# ------------------------------
snapshot = {
    "CurrentDay": current_day,
    "Phase": phase,
    "Slope": slope,
    "Intercept": intercept,
    "ForecastToday": today_rate,
    "Peak30Day": peak_horizon,
    # Add new capacity data to snapshot
    "SystemCapacity": cap_system,
    "StationCap_S1": cap_station_S1,
    "StationCap_S2": cap_station_S2,
    "StationCap_S3": cap_station_S3,
    # Original data
    "Need_S1_30dPeak": need_S1_peak,
    "Need_S2_30dPeak": need_S2_peak,
    "Need_S3_30dPeak": need_S3_peak,
    "Have_S1": have_S1,
    "Have_S2": have_S2,
    "Have_S3": have_S3,
    "Rec_S1": rec_S1,
    "Rec_S2": rec_S2,
    "Rec_S3": rec_S3,
    "S2_Policy": s2_policy
}
snap_df = pd.DataFrame([snapshot])
st.download_button(
    "Download recommendation snapshot (CSV)",
    data=snap_df.to_csv(index=False).encode("utf-8"),
    file_name=f"littlefield_snapshot_day{current_day}.csv",
    mime="text/csv",
)

st.markdown("---")
st.caption("Tip: re-upload the latest daily exports any time you want to refresh forecasts and recommendations.")
st.caption("Contact: Diipo Owotumi(tdiipo@outlook.com)")