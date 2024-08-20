import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# Connect to the SQLite database
conn = sqlite3.connect('messages.db')

# Query to fetch telemetry data for a specific node
node_id = ''  # Replace with the desired node ID
query = f"SELECT * FROM telemetry WHERE node_id = '{node_id}'"

# Load the data into a DataFrame
df = pd.read_sql_query(query, conn)

# Close the database connection
conn.close()

# Convert timestamp to datetime and adjust to CEST timezone
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
df['timestamp'] = df['timestamp'].dt.tz_convert('Europe/Berlin')

# Display basic statistics
stats = df.describe()

print("Basic Statistics for Node:", node_id)
print(stats)

# Plotting battery level over time
plt.figure(figsize=(10, 6))
plt.plot(df['timestamp'], df['battery_level'], marker='o', linestyle='-', color='b')
plt.title('Battery Level Over Time (CEST)')
plt.xlabel('Timestamp (CEST)')
plt.ylabel('Battery Level (%)')
plt.grid(True)
plt.xticks(rotation=45)  # Rotate timestamps for better readability
plt.show()

# Plotting voltage over time
plt.figure(figsize=(10, 6))
plt.plot(df['timestamp'], df['voltage'], marker='o', linestyle='-', color='g')
plt.title('Voltage Over Time (CEST)')
plt.xlabel('Timestamp (CEST)')
plt.ylabel('Voltage (V)')
plt.grid(True)
plt.xticks(rotation=45)
plt.show()

# Plotting channel utilization over time
plt.figure(figsize=(10, 6))
plt.plot(df['timestamp'], df['channel_utilization'], marker='o', linestyle='-', color='orange')
plt.title('Channel Utilization Over Time (CEST)')
plt.xlabel('Timestamp (CEST)')
plt.ylabel('Channel Utilization')
plt.grid(True)
plt.xticks(rotation=45)
plt.show()

# Plotting air utilization (TX) over time
plt.figure(figsize=(10, 6))
plt.plot(df['timestamp'], df['air_util_tx'], marker='o', linestyle='-', color='r')
plt.title('Air Utilization (TX) Over Time (CEST)')
plt.xlabel('Timestamp (CEST)')
plt.ylabel('Air Utilization (TX)')
plt.grid(True)
plt.xticks(rotation=45)
plt.show()

# You can add more plots for other metrics as needed.

