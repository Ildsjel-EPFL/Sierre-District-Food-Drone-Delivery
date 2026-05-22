import pandas as pd
import numpy as np
import numpy.random as npr
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from utils.utils import get_distance, generate_elevation_gain, energy_consumption, compute_flying_time

from typing import Tuple, List
import numpy.typing as npt


def solve_cvrp(available_vehicles: List[bool], round_demand: npt.NDArray[np.int64], remaining_flying_time_per_drones: List[float],
               max_load: int, battery_capacity: int, penalization: bool = False, penalty_per_unserved_order: float = 10.0,
               commune_names: List[str] = None, distances_df: pd.DataFrame = None, altitudes_df: pd.DataFrame = None) -> Tuple[List[List[str]], List[float], List[float], List[float], List[float], int, List[int]]:
    """
    Solves the Capacitated Vehicle Routing Problem (CVRP) for the given round demand and available vehicles.\\
    The function uses the Google OR-Tools library to find the optimal routes for the drones while respecting the constraints of load capacity and battery life.\\
    If penalization is enabled, the function also accounts for unserved orders by adding a penalty cost for each unserved order.
    
    :param available_vehicles: A list of booleans indicating the availability of each drone.
    :type available_vehicles: List[bool]
    :param round_demand: An array containing the demand for each commune in the current round.
    :type round_demand: npt.NDArray[np.int64]
    :param remaining_flying_time_per_drones: A list containing the remaining flying time for each drone.
    :type remaining_flying_time_per_drones: List[float]
    :param max_load: The maximum load capacity of each drone.
    :type max_load: int
    :param battery_capacity: The battery capacity of each drone in terms of energy units.
    :type battery_capacity: int
    :param penalization: A boolean indicating whether to apply penalization for unserved orders.
    :type penalization: bool
    :param penalty_per_unserved_order: The penalty cost for each unserved order if penalization is enabled.
    :type penalty_per_unserved_order: float
    :param commune_names: A list of commune names corresponding to the demand array.
    :type commune_names: List[str]
    :param distances_df: A DataFrame containing the distances between communes.
    :type distances_df: pd.DataFrame
    :param altitudes_df: A DataFrame containing the minimum and maximum altitudes of the communes.
    :type altitudes_df: pd.DataFrame
    :return: A tuple containing the routes for each drone, the distance traveled by each drone, the energy consumption of each drone, the updated remaining flying time for
    each drone, the time taken for each route, the number of dropped orders due to capacity constraints, and the list of used drone IDs.
    :rtype: Tuple[List[List[str]], List[float], List[float], List[float], List[float], int, List[int]]
    """
    
    active_drone_indices = [i for i, available in enumerate(available_vehicles) if available]
    num_vehicles = len(active_drone_indices)
    
    if num_vehicles == 0 or np.sum(round_demand) == 0:
        # If there are no vehicles available, all requested demand is dropped.
        # If there is no demand, dropped_orders is naturally 0.
        dropped = int(np.sum(round_demand))
        
        # We must return exactly 6 values to match the unpacking in full_loop
        return [], [], [], remaining_flying_time_per_drones, [], dropped, []

    node_to_commune = ["Warehouse"]
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

                if j == 0:
                    # Returning to warehouse: Drone is empty
                    assumed_load = 0
                elif i == 0:
                    # Leaving warehouse: Assume worst-case max capacity
                    assumed_load = max_load
                else:
                    # Traveling commune-to-commune: Assume average load
                    assumed_load = max_load / 2
                
                safe_energy = energy_consumption(dist, elev_gain, load=assumed_load)
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
    used_drone_ids = []
    
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
            
            used_drone_ids.append(global_drone_id)

    # Calculate dropped orders
    total_requested_orders = num_nodes - 1 
    served_orders = sum(len(r) - 2 for r in routes) 
    dropped_orders = total_requested_orders - served_orders

    return routes, distance_per_drone, round_energy_consumption, remaining_flying_time_per_drones, route_times, dropped_orders, used_drone_ids