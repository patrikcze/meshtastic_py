import sqlite3
import gmplot

# Connect to the SQLite database
conn = sqlite3.connect('messages.db')
cursor = conn.cursor()

# Execute the SQL query to fetch nodes and their neighbors along with their latest positions
query = """
WITH LatestPositions AS (
    SELECT 
        p.node_id,
        p.latitude,
        p.longitude,
        p.altitude,
        datetime(p.timestamp, 'unixepoch', 'localtime') AS last_position_time,
        ROW_NUMBER() OVER (PARTITION BY p.node_id ORDER BY p.timestamp DESC) AS rn
    FROM 
        positions p
)
SELECT 
    n1.long_name AS node_long_name,
    n2.long_name AS neighbor_long_name,
    lp1.latitude AS node_latitude,
    lp1.longitude AS node_longitude,
    lp2.latitude AS neighbor_latitude,
    lp2.longitude AS neighbor_longitude
FROM 
    neighbors
JOIN 
    nodes n1 ON neighbors.node_id = n1.node_number
LEFT JOIN 
    nodes n2 ON neighbors.neighbor_node_id = n2.node_number
LEFT JOIN 
    LatestPositions lp1 ON n1.user_id = lp1.node_id AND lp1.rn = 1
LEFT JOIN 
    LatestPositions lp2 ON n2.user_id = lp2.node_id AND lp2.rn = 1
GROUP BY 
    n1.long_name, n2.long_name
ORDER BY 
    n1.long_name;
"""

cursor.execute(query)
results = cursor.fetchall()

# Close the database connection
conn.close()

# Prepare lists for the map
latitudes = []
longitudes = []
labels = []
connections = []

# Process the results
for row in results:
    node_long_name = row[0]
    neighbor_long_name = row[1]
    node_latitude = row[2]
    node_longitude = row[3]
    neighbor_latitude = row[4]
    neighbor_longitude = row[5]

    # Add node positions to the list if they are not None
    if node_latitude is not None and node_longitude is not None:
        latitudes.append(node_latitude)
        longitudes.append(node_longitude)
        labels.append(node_long_name)

    # Add neighbor positions and connections if they are not None
    if neighbor_latitude is not None and neighbor_longitude is not None:
        latitudes.append(neighbor_latitude)
        longitudes.append(neighbor_longitude)
        labels.append(neighbor_long_name)
        connections.append(((node_latitude, neighbor_latitude), (node_longitude, neighbor_longitude)))

# Create the Google Map plotter
if latitudes and longitudes:  # Ensure there are valid lat/long values
    gmap = gmplot.GoogleMapPlotter(latitudes[0], longitudes[0], 10)  # Center map at the first node

    # Plot nodes on the map
    gmap.scatter(latitudes, longitudes, color='red', size=100, marker=True)

    # Draw connections between nodes and their neighbors
    for connection in connections:
        if connection[0][0] is not None and connection[0][1] is not None:
            gmap.plot(connection[0], connection[1], color='blue', edge_width=2.5)

    # Add labels for nodes
    for i in range(len(labels)):
        gmap.text(latitudes[i], longitudes[i], labels[i], color='black', size='medium')

    # Generate the map
    gmap.draw("mesh_network_map.html")

    print("Map has been created. Open 'mesh_network_map.html' in your browser to view it.")
else:
    print("No valid coordinates available to create the map.")
