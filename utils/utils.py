import pandas as pd
import numpy as np
import numpy.random as npr 

from typing import Tuple
import numpy.typing as npt


def add_random_distance(arrival_commune: str, distances_df: pd.DataFrame) -> int:
    """
    Adds a random distance to the actual distance between the departure and arrival communes to account for detours.\\
    The random distance is generated uniformly between half of the radius of the arrival commune and the radius of the arrival commune.

    :param arrival_commune: The name of the arrival commune.
    :type arrival_commune: str
    :param distances_df: The DataFrame containing the distances between communes.
    :type distances_df: pd.DataFrame
    :return: A random distance in kilometers.
    :rtype: int
    """
    radius = distances_df.loc[arrival_commune, arrival_commune]
    return int(round(npr.random_integers(low=int(radius/2*1000), high=int(radius*1000))/1000))

def get_distance(departure_commune: str, arrival_commune: str, distances_df: pd.DataFrame) -> float:
    """
    Retrieves the distance between the departure and arrival communes from the distances DataFrame.\\
    If the departure and arrival communes are the same, a random distance is generated to account for detours.

    :param departure_commune: The name of the departure commune.
    :type departure_commune: str
    :param arrival_commune: The name of the arrival commune.
    :type arrival_commune: str
    :param distances_df: The DataFrame containing the distances between communes.
    :type distances_df: pd.DataFrame
    :return: The distance in kilometers.
    :rtype: float
    """
    if departure_commune == arrival_commune:
        return add_random_distance(arrival_commune, distances_df)
    else:
        return distances_df.loc[departure_commune, arrival_commune] + add_random_distance(arrival_commune, distances_df)

def generate_elevation_gain(actual_altitude: float, arrival_commune: str, altitudes_df: pd.DataFrame) -> Tuple[float, float]:
    """
    Generates a random elevation gain between the departure and arrival communes.\\
    The random elevation gain is generated uniformly between the minimum and maximum altitudes of the arrival commune.
    
    :param actual_altitude: The actual altitude of the departure commune.
    :type actual_altitude: float
    :param arrival_commune: The name of the arrival commune.
    :type arrival_commune: str
    :param altitudes_df: The DataFrame containing the minimum and maximum altitudes of the communes.
    :type altitudes_df: pd.DataFrame
    :return: A tuple containing the elevation gain in kilometers and the random arrival altitude in meters.
    :rtype: Tuple[float, float]
    """
    random_arrival_altitude = npr.random_integers(low=int(altitudes_df.loc["min", arrival_commune]), high=int(altitudes_df.loc["max", arrival_commune]))
    return np.abs(random_arrival_altitude - actual_altitude)/1000, random_arrival_altitude

def energy_consumption(distance: float, elevation_gain: float, load: int) -> float:
    """
    Computes the energy consumption of a drone for a given distance, elevation gain and load.
    
    :param distance: The distance in kilometers.
    :type distance: float
    :param elevation_gain: The elevation gain in meters.
    :type elevation_gain: float
    :param load: The load in number of meals.
    :type load: int
    :return: The energy consumption in watt-hours.
    :rtype: float
    """
    return 52*distance + 3.6*distance*load + 0.12*elevation_gain

def cost_fct(weekly_operating_minutes: int, total_energy_consumed: float, n_drones: int) -> float:
    """
    Computes the total cost of operating the drone delivery service for a week, including capital expenditure (CAPEX), energy cost, labor cost and maintenance cost.
    
    :param weekly_operating_minutes: The total operating time in minutes for a week.
    :type weekly_operating_minutes: int
    :param total_energy_consumed: The total energy consumed in watt-hours for a week.
    :type total_energy_consumed: float
    :param n_drones: The number of drones in operation.
    :type n_drones: int
    :return: The total cost in euros.
    :rtype: float
    """
    weekly_operating_hours = weekly_operating_minutes/60
    capex = weekly_operating_hours*11000/4000*n_drones 
    energy_cost = total_energy_consumed*0.00027 
    labor = weekly_operating_hours*(45*n_drones/5 + 25) 
    maintenance = 231*n_drones  
    return capex + energy_cost + labor + maintenance

def get_demand_mtx(hour: int, day: str, demand_threshold: float, hourly_weekly_demand_df: pd.DataFrame, commune_info_df: pd.DataFrame) -> npt.NDArray[np.int64]:
    """
    Computes the demand matrix for a given hour and day, applying a demand threshold to filter out low-demand communes.\\
    The demand matrix is computed by multiplying the hourly share of daily demand for the given hour and day with the demand per commune, which is calculated based
    on the weekly and daily demand for each commune and the share of fast food demand.

    :param hour: The hour of the day (0-23).
    :type hour: int
    :param day: The day of the week (e.g., "Monday", "Tuesday", etc.).
    :type day: str
    :param demand_threshold: The minimum demand threshold to consider a commune for delivery.
    :type demand_threshold: float
    :param hourly_weekly_demand_df: The DataFrame containing the hourly share of daily demand for each day of the week.
    :type hourly_weekly_demand_df: pd.DataFrame
    :param commune_info_df: The DataFrame containing the weekly and daily demand for each commune, as well as the share of fast food demand.
    :type commune_info_df: pd.DataFrame
    :return: The demand matrix for the given hour and day, with low-demand communes filtered out.
    :rtype: npt.NDArray[np.int64]
    """
    hourly_share_of_daily_demand = hourly_weekly_demand_df.loc[day][str(hour)]
    threshold_fct = np.vectorize(lambda x: x if x >= demand_threshold else 0)
    demand_per_commune = commune_info_df.loc[:, "demand_"+day].to_numpy() * commune_info_df.loc[:, "weekly_fast_food_demand"].to_numpy() / commune_info_df.loc[:, "weekly_demand"].to_numpy()
    hourly_demand = hourly_share_of_daily_demand * demand_per_commune
    hourly_demand = threshold_fct(hourly_demand) 
    return hourly_demand / 4 

def compute_flying_time(distance: float, elevation_gain: float) -> float:
    """
    Computes the flying time in minutes for a given distance and elevation gain, based on the maximum horizontal and vertical speeds of the drone.\\
    The flying time is calculated as the sum of the time taken to cover the horizontal distance and the time taken to cover the elevation gain, converted to minutes.
    
    :param distance: The distance in kilometers.
    :type distance: float
    :param elevation_gain: The elevation gain in meter.
    :type elevation_gain: float
    :return: The flying time in minutes.
    :rtype: float
    """
    maximum_horizontal_speed = 13 # m/s
    maximum_vertical_speed = 5 # m/s

    horizontal_time_seconds = distance * 1000 / maximum_horizontal_speed
    vertical_time_seconds = elevation_gain / maximum_vertical_speed
    total_time_seconds = horizontal_time_seconds + vertical_time_seconds

    total_time_minutes = total_time_seconds / 60

    return int(np.ceil(total_time_minutes)) 