import pandas as pd
import math
def calculate_optimized_fleet_size(demand_url, distribution_url, drone_capacity=15):
    """
    Fetches daily demand and hourly weights directly from Git repositories, 
    calculates absolute hourly order rates, and returns the optimized fleet size.
    """
    print("Initiating direct remote repository download...")
    
    try:
        # 1. Read files directly from your GitHub live links
        df_demand = pd.read_csv(demand_url)
        # Distribution file uses semicolons as standard separators
        df_share = pd.read_csv(distribution_url, sep=';')
    except Exception as e:
        print(f"Network error reading Git repository assets: {e}")
        return None

    # 2. Data Cleansing: Fix European comma formats and typos
    for col in df_share.columns:
        if col != 'Day':
            df_share[col] = df_share[col].astype(str).str.replace(',', '.').astype(float)
            
    df_share['Day'] = df_share['Day'].replace('Tuesdasy', 'Tuesday')
    
    # 3. Sum absolute unit orders across all communes for each day
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    daily_aggregates = {day: df_demand[f'demand_{day}'].sum() for day in days}

    # 4. Generate the matrix of precise hourly order rates (orders/hour)
    hours_tracked = ['10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24']
    hourly_matrix_records = []
    
    for _, row in df_share.iterrows():
        day_name = row['Day']
        if day_name in daily_aggregates:
            total_day_volume = daily_aggregates[day_name]
            for hr in hours_tracked:
                # Absolute hourly rate = Total day orders * Hourly percentage share
                hourly_order_rate = total_day_volume * row[hr]
                hourly_matrix_records.append({
                    'Day': day_name,
                    'Hour_Block': f"{hr}:00",
                    'Order_Rate': hourly_order_rate
                })
                
    df_hourly_rates = pd.DataFrame(hourly_matrix_records)

    # 5. Locate the Absolute Global Maximum Peak hour
    global_peak_index = df_hourly_rates['Order_Rate'].idxmax()
    peak_record = df_hourly_rates.loc[global_peak_index]
    
    absolute_max_rate = peak_record['Order_Rate']
    peak_day = peak_record['Day']
    peak_hour = peak_record['Hour_Block']

    # 6. Apply your mathematical formulation bounds
    # n_drones >= (peak_demand_rate / drone_capacity) rounded by excess, multiplied by 1.2
    n_drones_base = math.ceil(absolute_max_rate / drone_capacity)
    n_drones_final = math.ceil(n_drones_base * 1.2)

    # Output detailed report log for your presentation
    print("=" * 60)
    print("      VALAIS DaaS REFINED FLEET SIZING ENGINE")
    print("=" * 60)
    print(f"Global Peak Day Located     : {peak_day}")
    print(f"Global Peak Hour Interval   : {peak_hour}")
    print(f"Absolute Peak Workload Rate : {absolute_max_rate:.2f} Orders/Hour")
    print(f"Per-Unit Operational Capability: {drone_capacity} Orders/Hour")
    print("-" * 60)
    print(f"Calculated Base Fleet Size  : {n_drones_base} Drones")
    print(f"OPTIMIZED SYSTEM FLEET SIZE : {n_drones_final} Drones (with 1.2x safety buffer)")
    print("=" * 60)
    
    return n_drones_final

# Run code with live remote asset paths
if __name__ == "__main__":
    demand_repo_link = "https://github.com/Ildsjel-EPFL/Sierre-District-Food-Drone-Delivery/raw/refs/heads/main/data/weekly_daily_demand.csv"
    share_repo_link = "https://github.com/Ildsjel-EPFL/Sierre-District-Food-Drone-Delivery/raw/refs/heads/main/data/hourly_share_of_daily_demand.csv"
    
    calculate_optimized_fleet_size(demand_repo_link, share_repo_link, drone_capacity=15)
