import numpy as np
import numpy.random as npr
import numpy.typing as npt


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
