import pandas as pd
from typing import Tuple
from pathlib import Path

DATA_DIR = Path.cwd().parent / "data"

def load_distances() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load distances from a CSV file.

    :return: A tuple containing the distance matrix and the elevation gain matrix.
    :rtype: Tuple[pd.DataFrame, pd.DataFrame]

    """
    # Implementation for loading distances
    pass

def load_demands() -> pd.DataFrame:
    """
    Load demand data from a CSV file.

    :return: A DataFrame containing the demand data.
    :rtype: pd.DataFrame

    """
    # Implementation for loading demand
    pass