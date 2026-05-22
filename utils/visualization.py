from datetime import datetime, timedelta
import plotly.express as px
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from IPython.display import clear_output
import pandas as pd

from typing import List, Dict
from utils.utils import get_demand_mtx

def render_terminal_dashboard(current_time: datetime, round_energy_wh: float, total_energy_wh: float, 
                              routes: List[List[str]], used_drone_ids: List[int], remaining_times: List[float], 
                              dropped_orders: int, penalty_per_order: float, 
                              total_successful: int, total_missed: int, console: Console):
    """Renders a live-updating dashboard in a Jupyter Notebook output cell."""
    clear_output(wait=True)
    
    # Header Panel - Now with 2 rows!
    cost_chf = round_energy_wh * 0.00027
    total_cost_chf = total_energy_wh * 0.00027
    
    # Calculate the delivery success rate safely to avoid division by zero
    total_attempts = total_successful + total_missed
    success_rate = (total_successful / total_attempts * 100) if total_attempts > 0 else 0.0

    header = Table.grid(expand=True, padding=(0, 2))
    
    # First row: Financials and Time
    header.add_row(f"[bold cyan]🕰️ Time:[/bold cyan] {current_time.strftime('%A %H:%M')}", 
                   f"[bold green]💸 Round Cost:[/bold green] CHF {cost_chf:.4f}",
                   f"[bold yellow]💰 Total Cost:[/bold yellow] CHF {total_cost_chf:.4f}")
    
    # Second row: Delivery Metrics
    header.add_row(f"[bold blue]📦 Total Delivered:[/bold blue] {total_successful}", 
                   f"[bold red]❌ Total Missed:[/bold red] {total_missed}",
                   f"[bold magenta]📊 Success Rate:[/bold magenta] {success_rate:.1f}%")
    
    console.print(Panel(header, style="blue"))

    # --- PENALTY ALERT ---
    if dropped_orders > 0:
        penalty_chf = dropped_orders * penalty_per_order
        alert_msg = f"[bold white]⚠️ WARNING: Fleet Capacity Exceeded! ⚠️[/bold white]\n"
        alert_msg += f"{dropped_orders} orders could not be delivered this round.\n"
        alert_msg += f"Penalty Applied: [bold yellow]CHF {penalty_chf:.2f}[/bold yellow]"
        console.print(Panel(alert_msg, style="bold on red", border_style="red"))
    
    # --- ROUTES TABLE ---
    route_table = Table(title="🚁 Active Routes this 15-Min Chunk", expand=True)
    route_table.add_column("Drone ID", style="cyan", width=10)
    route_table.add_column("Flight Path", style="white")
    
    if not routes:
        route_table.add_row("None", "[dim italic]No orders to process...[/dim italic]")
    else:
        for idx, route in enumerate(routes):
            drone_id = f"Drone {used_drone_ids[idx]:02d}" 
            path_str = " ➔ ".join(route)
            route_table.add_row(drone_id, path_str)
            
    # --- AVAILABILITY GRID ---
    avail_table = Table(title="⏱️ Fleet Availability (Minutes until ready)", show_header=False, expand=True)
    cols = 8
    cells = []
    for i, t in enumerate(remaining_times):
        if t <= 0:
            cells.append(f"[bold green]D{i:02d}: READY[/bold green]")
        else:
            cells.append(f"[bold red]D{i:02d}: {t:.1f}m[/bold red]")
            
    for i in range(0, len(cells), cols):
        avail_table.add_row(*cells[i:i+cols] + [""] * (cols - len(cells[i:i+cols])))

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

def plot_demand_curves(hourly_weekly_demand_df: pd.DataFrame, commune_info_df: pd.DataFrame, demand_threshold: float = 0.0):
    """
    Renders an interactive line chart showing the demand curve for each commune over the course of the week.
    """
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    commune_names = commune_info_df.index.tolist()
    
    demand_data = []
    # Use the same anchor date as the Gantt chart for consistency
    simulation_start = datetime(2024, 1, 1, 0, 0) 
    
    for day_idx, d in enumerate(weekdays):
        for h in range(10, 25): # 10:00 to 24:00
            # get_demand_mtx returns an array of demands per 15-minute chunk for the given hour
            demand_15m = get_demand_mtx(h, d, demand_threshold, hourly_weekly_demand_df, commune_info_df)
            
            for chunk in range(4):
                # Calculate the exact timestamp for this 15-minute chunk
                current_time = simulation_start + timedelta(days=day_idx, hours=h, minutes=chunk*15)
                
                for i, commune in enumerate(commune_names):
                    demand_data.append({
                        "Time": current_time,
                        "Commune": commune,
                        "Orders (per 15 min)": demand_15m[i]
                    })
                    
    # Convert to DataFrame for Plotly
    df_demand = pd.DataFrame(demand_data)
    
    # Plot using Plotly Express
    fig = px.line(df_demand, x="Time", y="Orders (per 15 min)", color="Commune",
                  title="Weekly Demand Curve by Commune (Orders per 15-minute chunk)",
                  template="plotly_white")
    
    # Clean up the X-axis to show days clearly
    fig.update_xaxes(
        dtick="86400000", # One tick per day (in milliseconds)
        tickformat="%A\n%H:%M",
        title_text="Day & Time"
    )
    
    fig.update_layout(height=600, hovermode="x unified")
    fig.show()