import sqlite3
from datetime import datetime
import pandas as pd
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

# Convert timestamps to European datetime format
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.strftime("%d.%m.%Y %H:%M")

# Create the figure
fig = go.Figure()

# Add temperature chart
fig.add_trace(
    go.Scatter(
        x=df["timestamp"], 
        y=df["temperature"], 
        mode='lines+markers', 
        name="Temperature (°C)", 
        line=dict(color='blue')
    )
)

# Add humidity chart
fig.add_trace(
    go.Scatter(
        x=df["timestamp"], 
        y=df["humidity"], 
        mode='lines+markers', 
        name="Humidity (%)", 
        line=dict(color='orange')
    )
)

# Add pressure chart
fig.add_trace(
    go.Scatter(
        x=df["timestamp"], 
        y=df["bar"], 
        mode='lines+markers', 
        name="Pressure (hPa)", 
        line=dict(color='green')
    )
)

# Update chart layout
fig.update_layout(
    title="Environmental Data Flowchart",
    xaxis_title="Timestamp",
    yaxis_title="Measurements",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(tickangle=-45),  # Rotate x-axis labels
    height=700,
    margin=dict(t=50, b=300)  # Leave space for the table
)

# Add the table as an annotation
table = go.Figure(
    data=[
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
        )
    ]
)

# Combine the chart and table into a single dashboard
fig.write_html("environment_chart_with_table.html", full_html=True)

print("Dashboard generated: environment_chart_with_table.html")
