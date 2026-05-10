import pandas as pd
from typing import Tuple
from pathlib import Path

DATA_DIR = Path.cwd().parent / "data"

def load_distances() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load distances from a CSV file.

    :return: A tuple containing the distance matrix and the min/max altitudes.
    :rtype: Tuple[pd.DataFrame, pd.DataFrame]

    """

    return pd.read_excel(DATA_DIR / "distances.xlsx", index_col=0), pd.read_excel(DATA_DIR / "altitudes.xlsx", index_col=0)
    
def communes_infos() -> pd.DataFrame:
    """
    Load communes informations from a CSV file.

    :return: A DataFrame containing the communes informations.
    :rtype: pd.DataFrame

    """
    return pd.read_excel(DATA_DIR / "communes_infos.xlsx", index_col=0)

def load_demands() -> pd.DataFrame:
    """
    Load demand data from a CSV file.

    :return: A DataFrame containing the demand data.
    :rtype: pd.DataFrame

    """
    # Implementation for loading demand
    pass