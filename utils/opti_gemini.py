import pandas as pd
import numpy as np
import numpy.typing as npt
import numpy.random as npr
from typing import List, Tuple, Dict
from datetime import datetime, timedelta

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# Presentation Imports
import plotly.express as px
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from IPython.display import clear_output

# ==========================================
# 1. DATA LOADING (Placeholders for your data)
# ==========================================
# altitudes_df = pd.read_excel("data/altitudes.xlsx", index_col=0)
# distances_df = pd.read_excel("data/distances.xlsx", index_col=0)
# hourly_weekly_demand_df = pd.read_csv("data/hourly_share_of_daily_demand.csv", index_col=0, sep=";")
# commune_info_df = pd.read_csv("data/weekly_daily_demand.csv", index_col=0)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def add_random_distance(arrival_commune: str, distances_df: pd.DataFrame) -> int:
    radius = distances_df.loc[arrival_commune, arrival_commune]
    return int(round(npr.random_integers(low=int(radius/2*1000), high=int(radius*1000))/1000))

def get_distance(departure_commune: str, arrival_commune: str, distances_df: pd.DataFrame) -> float:
    if departure_commune == arrival_commune:
        return add_random_distance(arrival_commune, distances_df)
    else:
        return distances_df.loc[departure_commune, arrival_commune] + add_random_distance(arrival_commune, distances_df)

def generate_elevation_gain(actual_altitude: float, arrival_commune: str, altitudes_df: pd.DataFrame) -> Tuple[float, float]:
    random_arrival_altitude = npr.random_integers(low=int(altitudes_df.loc[arrival_commune, "min"]), high=int(altitudes_df.loc[arrival_commune, "max"]))
    return np.abs(random_arrival_altitude - actual_altitude)/1000, random_arrival_altitude

def energy_consumption(distance: float, elevation_gain: float, load: int) -> float:
    return 52*distance + 3.6*distance*load + 0.12*elevation_gain

def cost_fct(weekly_operating_minutes: int, total_energy_consumed: float, n_drones: int) -> float:
    weekly_operating_hours = weekly_operating_minutes/60
    capex = weekly_operating_hours*11000/4000*n_drones 
    energy_cost = total_energy_consumed*0.00027 
    labor = weekly_operating_hours*(45*n_drones/5 + 25) 
    maintenance = 231*n_drones  
    return capex + energy_cost + labor + maintenance

def get_demand_mtx(hour: int, day: str, demand_threshold: float, hourly_weekly_demand_df: pd.DataFrame, commune_info_df: pd.DataFrame) -> npt.NDArray[np.int64]:
    hourly_share_of_daily_demand = hourly_weekly_demand_df.loc[day][str(hour)]
    threshold_fct = np.vectorize(lambda x: x if x >= demand_threshold else 0)
    demand_per_commune = commune_info_df.loc[:, "demand_"+day].to_numpy() * commune_info_df.loc[:, "weekly_fast_food_demand"].to_numpy() / commune_info_df.loc[:, "weekly_demand"].to_numpy()
    hourly_demand = hourly_share_of_daily_demand * demand_per_commune
    hourly_demand = threshold_fct(hourly_demand) 
    return hourly_demand / 4 

def compute_flying_time(distance: float, elevation_gain: float) -> float:
    maximum_horizontal_speed = 13 
    maximum_vertical_speed = 5 
    return int(np.ceil((distance*1000/maximum_horizontal_speed + elevation_gain/maximum_vertical_speed)*60)) 

# ==========================================
# 3. OR-TOOLS SOLVER
# ==========================================

def solve_cvrp(available_vehicles: List[bool], round_demand: npt.NDArray[np.int64], remaining_flying_time_per_drones: List[float],
               max_load: int, battery_capacity: int, penalization: bool = False, penalty_per_unserved_order: float = 10.0,
               commune_names: List[str] = None, distances_df: pd.DataFrame = None, altitudes_df: pd.DataFrame = None) -> Tuple[List[List[str]], List[float], List[float], List[float], List[float]]:
    
    active_drone_indices = [i for i, available in enumerate(available_vehicles) if available]
    num_vehicles = len(active_drone_indices)
    
    if num_vehicles == 0 or np.sum(round_demand) == 0:
        return [], [], [], remaining_flying_time_per_drones, []

    node_to_commune = ["warehouse"]
    demands = [0]
    
    for idx, demand in enumerate(round_demand):
        if demand > 0:
            commune_name = commune_names[idx]
            for _ in range(int(demand)):
                node_to_commune.append(commune_name)
                demands.append(1) 
                
    num_nodes = len(node_to_commune)

    SCALE_FACTOR = 100
    distance_matrix_unscaled = np.zeros((num_nodes, num_nodes), dtype=float)
    elev_matrix_unscaled = np.zeros((num_nodes, num_nodes), dtype=float)
    energy_matrix_scaled = np.zeros((num_nodes, num_nodes), dtype=int)
    time_matrix_scaled = np.zeros((num_nodes, num_nodes), dtype=int)
    
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                dist = get_distance(node_to_commune[i], node_to_commune[j], distances_df)
                elev_gain, _ = generate_elevation_gain(0, node_to_commune[j], altitudes_df) 
                
                distance_matrix_unscaled[i][j] = dist
                elev_matrix_unscaled[i][j] = elev_gain
                
                safe_energy = energy_consumption(dist, elev_gain, load=max_load)
                energy_matrix_scaled[i][j] = int(safe_energy * SCALE_FACTOR)
                
                time_cost = compute_flying_time(dist, elev_gain)
                if j == 0:
                    time_cost += 5 
                else:
                    time_cost += 2 
                    
                time_matrix_scaled[i][j] = int(time_cost)

    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def demand_callback(from_index):
        return demands[manager.IndexToNode(from_index)]
    
    def energy_callback(from_index, to_index):
        return energy_matrix_scaled[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    energy_callback_index = routing.RegisterTransitCallback(energy_callback)

    routing.AddDimension(demand_callback_index, 0, max_load, True, 'Capacity')
    routing.AddDimension(energy_callback_index, 0, int(battery_capacity * SCALE_FACTOR), True, 'Energy')
    routing.SetArcCostEvaluatorOfAllVehicles(energy_callback_index)

    if penalization:
        scaled_penalty = int(penalty_per_unserved_order * SCALE_FACTOR)
        for node in range(1, num_nodes):
            routing.AddDisjunction([manager.NodeToIndex(node)], scaled_penalty)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.FromSeconds(5) # Reduced to 5s for smoother dashboard updates

    solution = routing.SolveWithParameters(search_parameters)

    routes = []
    distance_per_drone = []
    round_energy_consumption = []
    route_times = []
    
    if solution:
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            route_indices = []
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_indices.append(node_index)
                index = solution.Value(routing.NextVar(index))
            route_indices.append(manager.IndexToNode(index)) 
            
            if len(route_indices) <= 2: 
                continue
                
            current_load = len(route_indices) - 2 
            
            exact_route_energy = 0.0
            exact_route_distance = 0.0
            exact_route_time = 0.0
            
            for i in range(len(route_indices) - 1):
                from_node = route_indices[i]
                to_node = route_indices[i+1]
                
                dist = distance_matrix_unscaled[from_node][to_node]
                elev = elev_matrix_unscaled[from_node][to_node]
                
                exact_route_distance += dist
                exact_route_time += time_matrix_scaled[from_node][to_node]
                exact_route_energy += energy_consumption(dist, elev, current_load)
                
                if to_node != 0: 
                    current_load -= 1
                    
            routes.append([node_to_commune[n] for n in route_indices])
            distance_per_drone.append(exact_route_distance)
            round_energy_consumption.append(exact_route_energy)
            route_times.append(exact_route_time)
            
            global_drone_id = active_drone_indices[vehicle_id]
            remaining_flying_time_per_drones[global_drone_id] += exact_route_time

    return routes, distance_per_drone, round_energy_consumption, remaining_flying_time_per_drones, route_times

# ==========================================
# 4. VISUALIZATION FUNCTIONS
# ==========================================

def render_terminal_dashboard(current_time: datetime, round_energy_wh: float, total_energy_wh: float, 
                              routes: List[List[str]], active_indices: List[int], remaining_times: List[float], 
                              console: Console):
    """Renders a live-updating dashboard in a Jupyter Notebook output cell."""
    clear_output(wait=True)
    
    # Header Panel
    cost_chf = round_energy_wh * 0.00027
    total_cost_chf = total_energy_wh * 0.00027
    header = Table.grid(expand=True)
    header.add_row(f"[bold cyan]🕰️ Time:[/bold cyan] {current_time.strftime('%A %H:%M')}", 
                   f"[bold green]💸 Round Energy Cost:[/bold green] CHF {cost_chf:.4f}",
                   f"[bold yellow]💰 Total Energy Cost:[/bold yellow] CHF {total_cost_chf:.4f}")
    
    # Routes Table
    route_table = Table(title="🚁 Active Routes this 15-Min Chunk", expand=True)
    route_table.add_column("Drone ID", style="cyan", width=10)
    route_table.add_column("Flight Path", style="white")
    
    if not routes:
        route_table.add_row("None", "[dim italic]No orders to process...[/dim italic]")
    else:
        for idx, route in enumerate(routes):
            drone_id = f"Drone {active_indices[idx]:02d}"
            path_str = " ➔ ".join(route)
            route_table.add_row(drone_id, path_str)
            
    # Availability Grid
    avail_table = Table(title="⏱️ Fleet Availability (Minutes until ready)", show_header=False, expand=True)
    
    # Create an 8-column grid for 30 drones
    cols = 8
    cells = []
    for i, t in enumerate(remaining_times):
        if t <= 0:
            cells.append(f"[bold green]D{i:02d}: READY[/bold green]")
        else:
            cells.append(f"[bold red]D{i:02d}: {t:.1f}m[/bold red]")
            
    # Chunk into rows
    for i in range(0, len(cells), cols):
        avail_table.add_row(*cells[i:i+cols] + [""] * (cols - len(cells[i:i+cols])))

    # Print Dashboard
    console.print(Panel(header, style="blue"))
    console.print(route_table)
    console.print(avail_table)
    console.print("[dim]Solving next chunk...[/dim]")


def plot_gantt_chart(drone_log: List[Dict]):
    """Renders an interactive Gantt chart using Plotly."""
    if not drone_log:
        print("No drone flights logged.")
        return
        
    df = pd.DataFrame(drone_log)
    df = df.sort_values(by="Drone")
    
    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Drone", color="Status",
                      color_discrete_map={"Flying": "#EF553B", "Idle": "#00CC96"},
                      title="Drone Fleet Activity Schedule")
                      
    fig.update_yaxes(autorange="reversed") # D00 at top, D29 at bottom
    fig.update_layout(xaxis_title="Time", yaxis_title="Drone ID", height=800)
    fig.show()

# ==========================================
# 5. MAIN LOOP
# ==========================================

def full_loop(distances_df: pd.DataFrame, altitudes_df: pd.DataFrame, commune_info_df: pd.DataFrame, hourly_weekly_demand_df: pd.DataFrame,
              nb_drones: int = 30, demand_threshold: float = 0.0, maximum_operating_hours=78, 
              penalization: bool = False, penalty_per_unserved_order: float = 10.0) -> Tuple[float, List[Dict]]:
    
    remaining_flying_time_per_drones = [0.0 for _ in range(nb_drones)]
    max_load = 12 
    battery_capacity = 2131 
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    total_energy_consumed = 0.0
    commune_names = commune_info_df.index.tolist()
    
    # Initialize Presentation Tools
    console = Console()
    drone_activity_log = []
    simulation_start = datetime(2024, 1, 1, 10, 0) # Use an arbitrary Monday for clean Plotly dates

    for day_idx, d in enumerate(weekdays):
        for h in range(10, 25): 
            for chunk in range(4): 
                
                # Time calculation for Plotly and Display
                current_time = simulation_start + timedelta(days=day_idx, hours=h-10, minutes=chunk*15)
                
                # 1. Update active drones and decrement remaining times by 15 mins BEFORE the chunk
                remaining_flying_time_per_drones = [max(0.0, t - 15.0) for t in remaining_flying_time_per_drones]
                available_drones = [True if t == 0.0 else False for t in remaining_flying_time_per_drones]
                
                # 2. Fetch Demand
                round_demand = get_demand_mtx(h, d, demand_threshold, hourly_weekly_demand_df, commune_info_df) 
                
                # 3. Solve 15-minute chunk
                routes, distance_per_drone, round_energy, remaining_flying_time_per_drones, route_times = solve_cvrp(
                    available_vehicles=available_drones, 
                    round_demand=round_demand, 
                    remaining_flying_time_per_drones=remaining_flying_time_per_drones, 
                    max_load=max_load, 
                    battery_capacity=battery_capacity, 
                    penalization=penalization, 
                    penalty_per_unserved_order=penalty_per_unserved_order,
                    commune_names=commune_names,
                    distances_df=distances_df,
                    altitudes_df=altitudes_df
                )
                
                # 4. Process Data & Log Flights for Gantt Chart
                round_energy_wh = sum(round_energy)
                total_energy_consumed += round_energy_wh
                
                active_indices = [i for i, is_avail in enumerate(available_drones) if is_avail]
                
                for idx, r_time in enumerate(route_times):
                    drone_id = f"D{active_indices[idx]:02d}"
                    start_dt = current_time
                    end_dt = current_time + timedelta(minutes=r_time)
                    drone_activity_log.append({
                        "Drone": drone_id,
                        "Start": start_dt,
                        "Finish": end_dt,
                        "Status": "Flying",
                        "Path": " -> ".join(routes[idx])
                    })

                # 5. Render live dashboard
                render_terminal_dashboard(current_time, round_energy_wh, total_energy_consumed, 
                                          routes, active_indices, remaining_flying_time_per_drones, console)

    # Calculate Total System Cost
    final_cost = cost_fct(weekly_operating_minutes=maximum_operating_hours * 60, 
                          total_energy_consumed=total_energy_consumed, 
                          n_drones=nb_drones)
                    
    # The console print here persists at the end of the simulation
    clear_output(wait=True)
    console.print(f"\n[bold green]✅ Simulation Complete. Final Weekly Cost: CHF {final_cost:,.2f}[/bold green]")
    
    return final_cost, drone_activity_log

# ==========================================
# USAGE IN JUPYTER NOTEBOOK:
# ==========================================
# final_cost, drone_log = full_loop(...)
# plot_gantt_chart(drone_log)