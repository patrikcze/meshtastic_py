import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt

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

# Extract data for plotting
timestamps = [datetime.utcfromtimestamp(row[6]) for row in rows]
temperatures = [row[2] for row in rows]
humidities = [row[3] for row in rows]
pressures = [row[4] for row in rows]

# Create the flowchart with subplots
plt.figure(figsize=(10, 8))

# Temperature subplot
plt.subplot(3, 1, 1)
plt.plot(timestamps, temperatures, marker='o', label="Temperature (°C)")
plt.title("Environmental Data Flowchart")
plt.ylabel("Temperature (°C)")
plt.grid()
plt.legend()

# Humidity subplot
plt.subplot(3, 1, 2)
plt.plot(timestamps, humidities, marker='o', label="Humidity (%)", color='orange')
plt.ylabel("Humidity (%)")
plt.grid()
plt.legend()

# Air Pressure subplot
plt.subplot(3, 1, 3)
plt.plot(timestamps, pressures, marker='o', label="Air Pressure (hPa)", color='green')
plt.ylabel("Air Pressure (hPa)")
plt.xlabel("Timestamp")
plt.grid()
plt.legend()

# Adjust layout
plt.tight_layout()

# Save or display the plot
plt.savefig("environment_data_flowchart.png")  # Save as an image file
plt.show()  # Display the plot

