import pandas as pd
import numpy as np
import numpy.random as npr
import numpy.typing as npt
from typing import List, Tuple

def get_distance(departure_commune : str, arrival_commune : str, df : pd.DataFrame) -> float:
    """
    Determine the distance between two communes based on a distance matrix.

    :param departure_commune: The name of the departure commune.
    :type departure_commune: str
    :param arrival_commune: The name of the arrival commune.
    :type arrival_commune: str
    :param df: The DataFrame containing the distance matrix.
    :type df: pd.DataFrame
    :return: The distance between the two communes.
    :rtype: float
    """
    if departure_commune == arrival_commune:
        radius = df.loc[departure_commune, departure_commune]
        return npr.random_integers(low = int(radius/2*1000), high = int(radius*1000))/1000
    else:
        return df.loc[departure_commune, arrival_commune]

def generate_elevation_gain(actual_altitude : float, departure_commune : str, arrival_commune : str, df : pd.DataFrame) -> float:
    """
    Generate a random elevation gain for a route between two communes.

    :param actual_altitude: The current altitude of the drone.
    :type actual_altitude: float
    :param departure_commune: The name of the departure commune.
    :type departure_commune: str
    :param arrival_commune: The name of the arrival commune.
    :type arrival_commune: str
    :param df: The DataFrame containing the altitude information.
    :type df: pd.DataFrame
    :return: A random elevation gain for the route.
    :rtype: float
    """
    random_arrival_altitude = npr.random_integers(low = int(df.loc[arrival_commune, "min"]), high = int(df.loc[arrival_commune, "max"]))
    return np.abs(random_arrival_altitude - actual_altitude)/1000

def generate_weights(mu : float, sigma : float, size : int) -> npt.NDArray[np.float32]:
    """
    Generate random weights for the demand model based on a normal distribution.

    :param mu: The mean of the normal distribution.
    :type mu: float
    :param sigma: The standard deviation of the normal distribution.
    :type sigma: float
    :param size: The number of weights to generate.
    :type size: int
    :return: An array of generated weights.
    :rtype: np.ndarray
    """
    return npr.normal(loc=mu, scale=sigma, size=size)

def generate_people_counts(num_locations : int, min_people : int, max_people : int) -> npt.NDArray[np.int32]:
    """
    Generate random people counts for each location.

    :param num_locations: The number of locations to generate counts for.
    :type num_locations: int
    :param min_people: The minimum number of people at a location.
    :type min_people: int
    :param max_people: The maximum number of people at a location.
    :type max_people: int
    :return: An array of generated people counts.
    :rtype: np.ndarray
    """
    return npr.normal(low=min_people, high=max_people + 1, size=num_locations).round().astype(np.int32)

def generate_demands(days : List[str], open_hours : List[Tuple[int]]) -> npt.NDArray[np.float32]:
    """
    Generate a demand matrix for a given list of days and their corresponding open hours.
    
    :param days: A list of days for which to generate the demand matrix.
    :type days: List[str]
    :param open_hours: A list of tuples representing the open hours for each day.
    :type open_hours: List[Tuple[int]]
    :return: A demand matrix where each entry represents the demand for a specific time slot on a specific day.
    :rtype: np.ndarray
    """
    demand_mtx : List[List[float]] = []
    for i in range(len(days)):

        demand_mtx.append([[] for _ in range((open_hours[i][1]-open_hours[i][0])*4)])