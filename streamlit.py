import streamlit as st
import json
import pandas as pd
import time
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Drone Fleet Replay", page_icon="🚁", layout="wide")

REPLAYS_DIR = "Replays"

# Ensure the Replays directory exists
if not os.path.exists(REPLAYS_DIR):
    os.makedirs(REPLAYS_DIR)

# --- SESSION STATE INITIALIZATION ---
# Session state keeps track of variables even when the page reloads every 3 seconds
if "current_step" not in st.session_state:
    st.session_state.current_step = 0
if "is_playing" not in st.session_state:
    st.session_state.is_playing = False
if "loaded_file" not in st.session_state:
    st.session_state.loaded_file = None

# --- DATA LOADING ---
@st.cache_data
def load_data(filepath):
    with open(filepath, "r") as f:
        return json.load(f)

def reset_simulation():
    """Resets the playback to the beginning."""
    st.session_state.current_step = 0
    st.session_state.is_playing = False

# --- SIDEBAR: FILE SELECTION & CONTROLS ---
st.sidebar.title("🎮 Replay Controls")

# 1. Find all JSON files in the Replays folder
available_files = [f for f in os.listdir(REPLAYS_DIR) if f.endswith('.json')]

if not available_files:
    st.error(f"No JSON files found in the '{REPLAYS_DIR}' folder. Please run your simulation first.")
    st.stop()

# 2. File Selector
selected_filename = st.sidebar.selectbox("Select a Scenario:", available_files, on_change=reset_simulation)
filepath = os.path.join(REPLAYS_DIR, selected_filename)

history = load_data(filepath)
total_steps = len(history)

# 3. Playback Controls
col1, col2, col3 = st.sidebar.columns(3)
if col1.button("▶️ Play"):
    # If we are at the end, restart automatically
    if st.session_state.current_step >= total_steps - 1:
        st.session_state.current_step = 0
    st.session_state.is_playing = True
    st.rerun()
    
if col2.button("⏸️ Pause"):
    st.session_state.is_playing = False
    st.rerun()
    
if col3.button("⏹️ Reset"):
    reset_simulation()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Total 15-min rounds:** {total_steps}")
st.sidebar.progress((st.session_state.current_step + 1) / total_steps)

# --- MAIN DASHBOARD AREA ---
current_frame = history[st.session_state.current_step]

st.title(f"🚁 Scenario Replay: {selected_filename}")
st.subheader(f"🕰️ Time: {current_frame['day']} - {current_frame['hour_chunk']}")

# 4. Metrics Row
m1, m2, m3, m4 = st.columns(4)
m1.metric("💸 Round Cost", f"CHF {current_frame['financials']['round_energy_cost_chf']:.4f}")
m2.metric("💰 Total Cost", f"CHF {current_frame['financials']['cumulative_energy_cost_chf']:.2f}")
m3.metric("📦 Successful Deliveries", current_frame['metrics']['cumulative_successful'])
m4.metric("❌ Missed Deliveries", current_frame['metrics']['cumulative_missed'])

# Show penalty alert if orders were dropped
if current_frame['metrics']['missed_deliveries'] > 0:
    dropped = current_frame['metrics']['missed_deliveries']
    penalty = current_frame['financials']['penalties_incurred_chf']
    st.error(f"⚠️ **CAPACITY EXCEEDED:** {dropped} orders missed this round. Penalty applied: CHF {penalty:.2f}")

st.markdown("---")

# Layout: Left column for Routes, Right column for Availability Grid
col_routes, col_grid = st.columns([2, 1])

# --- MAIN DASHBOARD AREA ---
# (Keep your metrics row exactly as it is)

st.markdown("---")

# 5. Active Routes Table (Now taking full width)
st.markdown("### 🗺 New Routes")
routes = current_frame["active_routes"]
if not routes:
    st.info("No active flights this round.")
else:
    df_routes = pd.DataFrame(routes)
    # Format the path list into a readable string
    df_routes['path'] = df_routes['path'].apply(lambda p: " ➔ ".join(p))
    df_routes['drone_id'] = df_routes['drone_id'].apply(lambda d: f"D{d:02d}")
    # Clean up column names for display
    df_routes.rename(columns={"drone_id": "Drone", "path": "Flight Path", "distance_km": "Dist (km)", "energy_used_wh": "Energy (Wh)"}, inplace=True)
    st.dataframe(df_routes, use_container_width=True, hide_index=True)

st.markdown("---")

# 6. Availability Grid (Now directly underneath, taking full width)
st.markdown("### ⏱️ Fleet Availability")
drones = current_frame["fleet_status"]["drones"]

# Increased to 6 columns since we now have the full width of the page
num_cols = 6 

# Create the rows of the grid dynamically
for i in range(0, len(drones), num_cols):
    chunk = drones[i:i + num_cols]
    cols = st.columns(num_cols)
    
    for j, drone in enumerate(chunk):
        d_id = f"D{drone['id']:02d}"
        time_left = drone['minutes_until_ready']
        
        with cols[j]:
            if time_left <= 0:
                # Available (Green)
                st.success(f"**{d_id}**\n\nREADY")
            else:
                # Flying (Red)
                st.error(f"**{d_id}**\n\n{time_left:.1f}m")

# --- ANIMATION LOOP LOGIC ---
# If playing, wait 3 seconds, increment frame, and force Streamlit to reload
if st.session_state.is_playing:
    if st.session_state.current_step < total_steps - 1:
        time.sleep(3)
        st.session_state.current_step += 1
        st.rerun()
    else:
        # Stop playing when the file is finished
        st.session_state.is_playing = False
        st.toast("Simulation playback finished!", icon="✅")
        st.rerun()


# import streamlit as st
# import json
# import pandas as pd

# # Load the pre-computed simulation data
# @st.cache_data
# def load_data():
#     with open("simulation_results_scenario_1.json", "r") as f:
#         return json.load(f)

# history = load_data()

# st.title("🚁 Drone Fleet Simulation Replay")

# # Create a slider to scrub through time (0 to total rounds)
# step = st.slider("Timeline (15-min chunks)", min_value=0, max_value=len(history)-1, value=0)

# # Get the snapshot for the current slider position
# current_frame = history[step]

# st.subheader(f"Time: {current_frame['day']} - {current_frame['hour_chunk']}")

# # Display Metrics
# col1, col2, col3 = st.columns(3)
# col1.metric("Round Cost", f"CHF {current_frame['financials']['round_energy_cost_chf']:.2f}")
# col2.metric("Successful Deliveries", current_frame['metrics']['cumulative_successful'])
# col3.metric("Missed Deliveries", current_frame['metrics']['cumulative_missed'])

# # Display Active Routes
# st.markdown("### Active Routes")
# routes = current_frame["active_routes"]
# if not routes:
#     st.info("No active flights this round.")
# else:
#     # Convert routes to a dataframe for a clean Streamlit table
#     df_routes = pd.DataFrame(routes)
#     # Convert list path to a string arrow format
#     df_routes['path'] = df_routes['path'].apply(lambda p: " ➔ ".join(p)) 
#     st.table(df_routes[['drone_id', 'path', 'distance_km']])