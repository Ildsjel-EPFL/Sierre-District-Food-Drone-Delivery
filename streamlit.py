import streamlit as st
import json
import pandas as pd

# Load the pre-computed simulation data
@st.cache_data
def load_data():
    with open("simulation_results.json", "r") as f:
        return json.load(f)

history = load_data()

st.title("🚁 Drone Fleet Simulation Replay")

# Create a slider to scrub through time (0 to total rounds)
step = st.slider("Timeline (15-min chunks)", min_value=0, max_value=len(history)-1, value=0)

# Get the snapshot for the current slider position
current_frame = history[step]

st.subheader(f"Time: {current_frame['day']} - {current_frame['hour_chunk']}")

# Display Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Round Cost", f"CHF {current_frame['financials']['round_energy_cost_chf']:.2f}")
col2.metric("Successful Deliveries", current_frame['metrics']['cumulative_successful'])
col3.metric("Missed Deliveries", current_frame['metrics']['cumulative_missed'])

# Display Active Routes
st.markdown("### Active Routes")
routes = current_frame["active_routes"]
if not routes:
    st.info("No active flights this round.")
else:
    # Convert routes to a dataframe for a clean Streamlit table
    df_routes = pd.DataFrame(routes)
    # Convert list path to a string arrow format
    df_routes['path'] = df_routes['path'].apply(lambda p: " ➔ ".join(p)) 
    st.table(df_routes[['drone_id', 'path', 'distance_km']])