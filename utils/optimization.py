from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import numpy as np
import numpy.typing as npt
import numpy.random as npr
import pandas as pd

from typing import List, Tuple

altitudes_df = pd.read_excel("data/altitudes.xlsx", index_col=0)
# One column per commune, two rows (min and max altitudes) and the last column is the depot's column

distances_df = pd.read_excel("data/distances.xlsx", index_col=0)
# One column per commune and the last column is the depot's column, one row per commune and the last row is the depot's row, with the same order as the altitudes_df
# The distances are in kilometers and must be randomized using the get_distance function to add some variability to the model
# The diagonal of the distance matrix (distance from a commune to itself) is not zero but the average radius of the commune in kilometers, to add some variability to the model

hourly_weekly_demand_df = pd.read_csv("data/hourly_share_of_daily_demand.csv", index_col=0, sep=";")
# One column per open hour of the day (from 10 to 24) and one row per day of the week (the indexs is the name of the day, from Monday to Sunday), with the share
# of the daily demand for each hour and each day. This will be used to generate the demand matrix for each hour and each day, based on a total daily demand for each commune.

commune_info_df = pd.read_csv("data/weekly_daily_demand.csv", index_col=0)
# Columns : Radius,Citizens,Density,weekly_demand,weekly_fast_food_demand,demand_Monday,demand_Tuesday,demand_Wednesday,demand_Thursday,demand_Friday,demand_Saturday,demand_Sunday
# One row per commune, with the radius of the commune in meters, the number of citizens, the population density of the commune, the total weekly demand for food delivery in the commune,
# the total weekly demand for fast food delivery in the commune and the total daily demand for each day of the week. 
# This will be used to generate the demand matrix for each hour and each day, based on a total daily demand for each commune.

def add_random_distance(arrival_commune : str, distances_df : pd.DataFrame) -> int:
    """
    Add a random distance to the distance from a commune to itself, based on the average radius of the commune.
    
    :param arrival_commune: The name of the arrival commune.
    :type arrival_commune: str
    :param distances_df: The DataFrame containing the distance matrix.
    :type distances_df: pd.DataFrame
    :return: A random distance to add to the distance from a commune to itself.
    :rtype: int
    """
    radius = distances_df.loc[arrival_commune, arrival_commune]
    return int(round(npr.random_integers(low = int(radius/2*1000), high = int(radius*1000))/1000))

def get_distance(departure_commune : str, arrival_commune : str, distances_df : pd.DataFrame) -> int:
    """
    Determine the distance between two communes based on a distance matrix.

    :param departure_commune: The name of the departure commune.
    :type departure_commune: str
    :param arrival_commune: The name of the arrival commune.
    :type arrival_commune: str
    :param distances_df: The DataFrame containing the distance matrix.
    :type distances_df: pd.DataFrame
    :return: The distance between the two communes in kilometers.
    :rtype: float
    """
    if departure_commune == arrival_commune:
        return add_random_distance(arrival_commune, distances_df)
    else:
        return distances_df.loc[departure_commune, arrival_commune]+add_random_distance(arrival_commune, distances_df)

def generate_elevation_gain(actual_altitude : float, arrival_commune : str, altitudes_df : pd.DataFrame) -> Tuple[float, float]:
    """
    Generate a random elevation gain for a route between two communes.

    :param actual_altitude: The current altitude of the drone.
    :type actual_altitude: float
    :param arrival_commune: The name of the arrival commune.
    :type arrival_commune: str
    :param altitudes_df: The DataFrame containing the altitude information.
    :type altitudes_df: pd.DataFrame
    :return: A random elevation gain in meter for the route and the random arrival altitude.
    :rtype: Tuple[float, float]
    """
    random_arrival_altitude = npr.random_integers(low = int(altitudes_df.loc[arrival_commune, "min"]), high = int(altitudes_df.loc[arrival_commune, "max"]))
    return np.abs(random_arrival_altitude - actual_altitude)/1000, random_arrival_altitude

def energy_consumption(distance : int, elevation_gain : float, load : int) -> float:
    """
    Calculate the energy consumption of a drone for a given route based on the distance, elevation gain and load.
    
    :param distance: The distance of the route in kilometers.
    :type distance: int
    :param elevation_gain: The elevation gain of the route in kilometers.
    :type elevation_gain: float
    :param load: The load of the drone in kilograms.
    :type load: int
    :return: The energy consumption of the drone for the route in watt-hours.
    :rtype: float
    """
    return 52*distance + 3.6*distance*load + 0.12*elevation_gain # 

def cost_fct(weekly_operating_minutes : int, total_energy_consumed : float, n_drones : int) -> float:
    """
    Calculate the total cost of the drone delivery system based on the weekly operating minutes, total energy consumed and total drones used.
    
    :param weekly_operating_minutes: The total operating minutes of the drone delivery system per week.
    :type weekly_operating_minutes: int
    :param total_energy_consumed: The total energy consumed by the drone delivery system per week in watt-hours.
    :type total_energy_consumed: float 
    :param n_drones: The total number of drones used in the drone delivery system.
    :type n_drones: int
    :return: The total cost of the drone delivery system per week in Swiss francs.
    :rtype: float
    """
    weekly_operating_hours = weekly_operating_minutes/60
    capex = weekly_operating_hours*11000/4000*n_drones # a drone cost 11000 chf, 4000 hours of mechanical lifetime per drone
    energy_cost = total_energy_consumed*0.00027 # 0.00027 chf per Wh
    labor = weekly_operating_hours*(45*n_drones/5+25) # 45 chf per hour for a drone operator, 25 chf per hour for a logistics manager
    maintenance = 231*n_drones  # 231 chf per drone per week for maintenance
    return capex + energy_cost + labor + maintenance

def get_demand_mtx(hour : int, day : str, demand_threshold : float = 0.0) -> npt.NDArray[np.int64]:
    """
    Generate the demand matrix for a given hour and day based on the hourly share of daily demand and the total daily demand for each commune, with an optional demand threshold.
    
    :param hour: The hour of the day for which to generate the demand matrix (from 10 to 24).
    :type hour: int
    :param day: The day of the week for which to generate the demand matrix (from "Monday" to "Sunday").
    :type day: str
    :param demand_threshold: The minimum demand threshold for a commune to be included in the demand matrix, in number of orders per hour. Communes with a demand below this threshold will be set to 0 in the demand matrix.
    :type demand_threshold: float
    :return: The demand matrix for the given quarter of hour and day, as a 2D numpy array of size (1, nb_communes).
    :rtype: npt.NDArray[np.int64]
    """
    hourly_share_of_daily_demand = hourly_weekly_demand_df.loc[day][str(hour)]
    threshold_fct = np.vectorize(lambda x: x if x >= demand_threshold else 0)
    demand_per_commune = commune_info_df.loc[:, "demand_"+day].to_numpy()*commune_info_df.loc[:, "weekly_fast_food_demand"].to_numpy()/commune_info_df.loc[:, "weekly_demand"].to_numpy()
    hourly_demand = hourly_share_of_daily_demand * demand_per_commune
    hourly_demand = threshold_fct(hourly_demand) # apply demand threshold
    return hourly_demand/4 # we divide by 4 because we want the demand per 15 minutes

def compute_flying_time(distance : int, elevation_gain : float) -> int:
    """
    Compute the flying time of a drone for a given route based on the distance and elevation gain.
    
    :param distance: The distance of the route in kilometers.
    :type distance: int
    :param elevation_gain: The elevation gain of the route in kilometers.
    :type elevation_gain: float
    :return: The flying time of the drone for the route in minutes.
    :rtype: float
    """
    maximum_horizontal_speed = 13 # m/s, which is the maximum horizontal speed of the drone, we assume that the drone flies at this speed for the entire route
    maximum_vertical_speed = 5 # m/s, which is the maximum vertical speed of the drone, we assume that the drone flies at this speed for the entire route
    return int(np.ceil((distance*1000/(maximum_horizontal_speed) + elevation_gain/maximum_vertical_speed)*60)) # we convert the flying time from seconds to minutes, and we round it up to the nearest minute to be more realistic

def solve_cvrp(available_vehicles: List[bool], round_demand: npt.NDArray[np.int64], remaining_flying_time_per_drones: List[float],
               max_load: int, battery_capacity: int, penalization: bool = False, penalty_per_unserved_order: float = 10.0,
               commune_names: List[str] = None, distances_df: pd.DataFrame = None, altitudes_df: pd.DataFrame = None) -> Tuple[List[List[int]], List[float], List[float], List[float]]:
    
    active_drone_indices = [i for i, available in enumerate(available_vehicles) if available]
    num_vehicles = len(active_drone_indices)
    
    if num_vehicles == 0 or np.sum(round_demand) == 0:
        return [], [], [], remaining_flying_time_per_drones

    # --- Node Expansion ---
    node_to_commune = ["Warehouse"]
    demands = [0]
    
    for idx, demand in enumerate(round_demand):
        if demand > 0:
            commune_name = commune_names[idx]
            for _ in range(int(demand)):
                node_to_commune.append(commune_name)
                demands.append(1) # Every order is exactly 1 kg
                
    num_nodes = len(node_to_commune)

    # --- Matrix Generation (Randomized per 15-min chunk) ---
    SCALE_FACTOR = 100
    distance_matrix_unscaled = np.zeros((num_nodes, num_nodes), dtype=float)
    elev_matrix_unscaled = np.zeros((num_nodes, num_nodes), dtype=float)
    
    energy_matrix_scaled = np.zeros((num_nodes, num_nodes), dtype=int)
    time_matrix_scaled = np.zeros((num_nodes, num_nodes), dtype=int)
    
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                # Randomization happens here via your get_distance function
                dist = get_distance(node_to_commune[i], node_to_commune[j], distances_df)
                elev_gain, _ = generate_elevation_gain(0, node_to_commune[j], altitudes_df) 
                
                distance_matrix_unscaled[i][j] = dist
                elev_matrix_unscaled[i][j] = elev_gain
                
                # WORST-CASE ENERGY for solver safety (Assuming max_load = 12kg)
                safe_energy = energy_consumption(dist, elev_gain, load=max_load)
                energy_matrix_scaled[i][j] = int(safe_energy * SCALE_FACTOR)
                
                # TIME CALCULATION
                time_cost = compute_flying_time(dist, elev_gain)
                if j == 0:
                    time_cost += 5 # 5 minute service time upon returning to the depot
                else:
                    time_cost += 2 # 2 minute delivery time per order
                    
                time_matrix_scaled[i][j] = int(time_cost)

    # --- OR-Tools Initialization ---
    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Callbacks
    def demand_callback(from_index):
        return demands[manager.IndexToNode(from_index)]
    
    def energy_callback(from_index, to_index):
        return energy_matrix_scaled[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    def time_callback(from_index, to_index):
        return time_matrix_scaled[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    energy_callback_index = routing.RegisterTransitCallback(energy_callback)

    # Dimensions
    routing.AddDimension(demand_callback_index, 0, max_load, True, 'Capacity')
    routing.AddDimension(energy_callback_index, 0, int(battery_capacity * SCALE_FACTOR), True, 'Energy')

    # Objective
    routing.SetArcCostEvaluatorOfAllVehicles(energy_callback_index)

    # Penalization
    if penalization:
        scaled_penalty = int(penalty_per_unserved_order * SCALE_FACTOR)
        for node in range(1, num_nodes):
            routing.AddDisjunction([manager.NodeToIndex(node)], scaled_penalty)

    # Solve
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.FromSeconds(10)

    solution = routing.SolveWithParameters(search_parameters)

    # --- Exact Extraction (Dynamic Weight Processing) ---
    routes = []
    distance_per_drone = []
    round_energy_consumption = []
    
    if solution:
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            route = []
            
            # First pass: Get the route sequence to know the initial load
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route.append(node_index)
                index = solution.Value(routing.NextVar(index))
            route.append(manager.IndexToNode(index)) # Append Depot end
            
            if len(route) <= 2: # Only depot to depot, no deliveries
                continue
                
            routes.append(route)
            
            # Second pass: Compute exact dynamic energy and time
            # Initial load is the number of drops (1kg per drop). len(route) includes start/end depot.
            current_load = len(route) - 2 
            
            exact_route_energy = 0.0
            exact_route_distance = 0.0
            exact_route_time = 0.0
            
            for i in range(len(route) - 1):
                from_node = route[i]
                to_node = route[i+1]
                
                dist = distance_matrix_unscaled[from_node][to_node]
                elev = elev_matrix_unscaled[from_node][to_node]
                
                exact_route_distance += dist
                exact_route_time += time_matrix_scaled[from_node][to_node]
                
                # EXACT Energy calculation based on CURRENT load
                exact_route_energy += energy_consumption(dist, elev, current_load)
                
                # Decrease weight by 1 kg after arriving at a delivery node
                if to_node != 0: 
                    current_load -= 1
                    
            distance_per_drone.append(exact_route_distance)
            round_energy_consumption.append(exact_route_energy)
            
            global_drone_id = active_drone_indices[vehicle_id]
            remaining_flying_time_per_drones[global_drone_id] += exact_route_time

    return routes, distance_per_drone, round_energy_consumption, remaining_flying_time_per_drones

def full_loop(distances_df: pd.DataFrame, altitudes_df: pd.DataFrame, commune_info_df: pd.DataFrame, 
              nb_drones: int = 30, demand_threshold: float = 0.0, maximum_operating_hours=78, 
              penalization: bool = False, penalty_per_unserved_order: float = 10.0) -> float:
    
    remaining_flying_time_per_drones = [0.0 for _ in range(nb_drones)]
    max_load = 12 
    battery_capacity = 2131 
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    total_energy_consumed = 0.0
    commune_names = commune_info_df.index.tolist()

    for d in weekdays:
        for h in range(10, 25): # 10 to 24 inclusive
            for _ in range(4): # 4 chunks of 15 minutes per hour
                
                # 1. Update active drones and decrement remaining times by 15 mins BEFORE the chunk
                remaining_flying_time_per_drones = [max(0.0, t - 15.0) for t in remaining_flying_time_per_drones]
                available_drones = [True if t == 0.0 else False for t in remaining_flying_time_per_drones]
                
                # 2. Fetch Demand
                round_demand = get_demand_mtx(h, d, demand_threshold) 
                
                # 3. Solve 15-minute chunk
                routes, distance_per_drone, round_energy, remaining_flying_time_per_drones = solve_cvrp(
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
                
                # 4. Accumulate cost metrics
                total_energy_consumed += sum(round_energy)

    # Calculate Total System Cost
    cost = cost_fct(weekly_operating_minutes=maximum_operating_hours * 60, 
                    total_energy_consumed=total_energy_consumed, 
                    n_drones=nb_drones)
                    
    return cost
