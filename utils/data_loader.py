import pandas as pd
from typing import Tuple
from pathlib import Path

DATA_DIR = Path.cwd() / "data"

def data_loader() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads all necessary data files for the optimization process.
        The function loads the following files:
        - altitudes.xlsx: Contains the minimum and maximum altitudes of the communes.
        - distances.xlsx: Contains the distances between the communes.
        - hourly_share_of_daily_demand.csv: Contains the hourly share of daily demand for each day of the week.
        - weekly_daily_demand.csv: Contains the weekly and daily demand for each commune.
        - commune_info.csv: Contains additional information about the communes, such as population and area.
    
    :return: A tuple containing the altitudes DataFrame, distances DataFrame, hourly weekly demand DataFrame, and commune info DataFrame.
    :rtype: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
    """
    altitudes_df = pd.read_excel(DATA_DIR / "altitudes.xlsx", index_col=0)
    distances_df = pd.read_excel(DATA_DIR / "distances.xlsx", index_col=0)
    hourly_weekly_demand_df = pd.read_csv(DATA_DIR / "hourly_share_of_daily_demand.csv", index_col=0)
    commune_info_df = pd.read_csv(DATA_DIR / "weekly_daily_demand.csv", index_col=0)
    return altitudes_df, distances_df, hourly_weekly_demand_df, commune_info_df