import sqlite3
from datetime import datetime
import pandas as pd
import pytz  # For timezone conversion
import plotly.subplots as sp
import plotly.graph_objects as go

# Define the timeframe in UTC
start_time_str = "2025-01-24 17:45:00"
start_time = int(datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S").timestamp())

# Connect to the SQLite database
db_path = "messages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Query the data for the specified node_id and timeframe
node_id = "!067e0508"
query = f"""
SELECT id, node_id, temperature, humidity, bar, iaq, timestamp
FROM environment
WHERE node_id = ? AND timestamp >= ?
ORDER BY timestamp ASC;
"""
cursor.execute(query, (node_id, start_time))
rows = cursor.fetchall()

# Close the database connection
conn.close()

# Create a DataFrame for better data handling
columns = ["id", "node_id", "temperature", "humidity", "bar", "iaq", "timestamp"]
df = pd.DataFrame(rows, columns=columns)

# Convert timestamps to CET timezone (Prague time)
utc_tz = pytz.utc
cet_tz = pytz.timezone("Europe/Prague")
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.tz_localize(utc_tz).dt.tz_convert(cet_tz)
df["timestamp"] = df["timestamp"].dt.strftime("%d.%m.%Y %H:%M")  # Format for European datetime

# Create a subplot layout with additional spacing
fig = sp.make_subplots(
    rows=2, cols=1,
    row_heights=[0.6, 0.4],  # Chart takes 60%, table takes 40% of height
    specs=[[{"type": "xy"}], [{"type": "domain"}]],  # Specify table subplot type as "domain"
    shared_xaxes=False,
    vertical_spacing=0.15,  # Increase spacing between chart and table
    subplot_titles=("Environmental Data Chart", "Data Table")
)

# Add temperature chart
fig.add_trace(
    go.Scatter(
        x=df["timestamp"], 
        y=df["temperature"], 
        mode='lines+markers', 
        name="Temperature (°C)", 
        line=dict(color='blue')
    ),
    row=1, col=1
)

# Add humidity chart
fig.add_trace(
    go.Scatter(
        x=df["timestamp"], 
        y=df["humidity"], 
        mode='lines+markers', 
        name="Humidity (%)", 
        line=dict(color='orange')
    ),
    row=1, col=1
)

# Add pressure chart
fig.add_trace(
    go.Scatter(
        x=df["timestamp"], 
        y=df["bar"], 
        mode='lines+markers', 
        name="Pressure (hPa)", 
        line=dict(color='green')
    ),
    row=1, col=1
)

# Add the table
fig.add_trace(
    go.Table(
        header=dict(
            values=["ID", "Node ID", "Temperature (°C)", "Humidity (%)", "Pressure (hPa)", "Timestamp"],
            font=dict(size=12, color="white"),
            fill_color="gray",
            align="center"
        ),
        cells=dict(
            values=[df[col] for col in df.columns],
            align="center",
            font=dict(size=11),
            fill_color="lightgray"
        )
    ),
    row=2, col=1
)

# Update layout
fig.update_layout(
    title_text="Environmental Data Flowchart with Table (CET Timezone)",
    height=1000,  # Increase the overall height for better spacing
    xaxis=dict(tickangle=-45),  # Rotate x-axis labels for better readability
    showlegend=True
)

# Show the plot
fig.show()
