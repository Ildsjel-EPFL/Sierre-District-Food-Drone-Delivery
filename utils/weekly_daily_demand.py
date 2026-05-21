import pandas as pd

DAY_SHARES = {
    "Monday": 0.128,
    "Tuesday": 0.159,
    "Wednesday": 0.169,
    "Thursday": 0.160,
    "Friday": 0.180,
    "Saturday": 0.125,
    "Sunday": 0.079,
}

ORDER_FREQUENCY_DATA = pd.DataFrame({
    "category": ["Several times a week", "Around once a week", "2 to 3 times a month", "Around once a month", "Every 2 to 3 months", "1 to 2 times a year", "Less than 1 to 2 times a year", "Never / no longer ordering",],
    "share": [0.029, 0.095, 0.161, 0.168, 0.145, 0.088, 0.113, 0.201],
    "orders_per_week": [3,1,2.5 / 4.3,1 / 4.3,1 / (4.3 * 2.5),1.5 / 52.1,0.5 / 52.1,0,],
})

def compute_orders_per_user_per_week():
    ORDER_FREQUENCY_DATA["weighted_orders"] = (ORDER_FREQUENCY_DATA["share"] * ORDER_FREQUENCY_DATA["orders_per_week"])
    return ORDER_FREQUENCY_DATA["weighted_orders"].sum()

def load_population_data(path="data/communes_infos.xlsx"):
    raw_df = pd.read_excel(path, index_col=0)
    df = raw_df.T
    df = df.reset_index()
    df = df.rename(columns={"index": "Commune"})
    return df

def compute_weekly_demand(df, population_column="Citizens"):
    orders_per_user_per_week = compute_orders_per_user_per_week()
    df["weekly_demand"] = df[population_column] * orders_per_user_per_week
    return df, orders_per_user_per_week

def distribute_by_day(df):
    for day, share in DAY_SHARES.items():
        df[f"demand_{day}"] = df["weekly_demand"] * share
    return df

def main():
    print(ORDER_FREQUENCY_DATA)
    
    orders_per_user_per_week = compute_orders_per_user_per_week()
    print(f"\nOrders per user per week = {orders_per_user_per_week:.3f}")

    df = load_population_data()
    df, orders_per_user_per_week = compute_weekly_demand(df)
    df = distribute_by_day(df)

    print(df)
    df.to_csv("data/weekly_daily_demand.csv", index=False)

    print("\nSaved: data/weekly_daily_demand.csv")

if __name__ == "__main__":
    main()
