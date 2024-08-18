import sqlite3
import folium
from folium.plugins import MarkerCluster

# Connect to the SQLite database
conn = sqlite3.connect('messages.db')
cursor = conn.cursor()

# Query to fetch nodes, neighbors, positions, and SNR details
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
    lp2.longitude AS neighbor_longitude,
    AVG(neighbors.snr) AS average_snr,
    MIN(neighbors.snr) AS min_snr,
    MAX(neighbors.snr) AS max_snr
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
WHERE
    lp1.latitude IS NOT NULL AND lp1.longitude IS NOT NULL AND
    lp2.latitude IS NOT NULL AND lp2.longitude IS NOT NULL
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
node_positions = {}
connections = []

# Process the results
for row in results:
    node_long_name = row[0]
    neighbor_long_name = row[1]
    node_latitude = row[2]
    node_longitude = row[3]
    neighbor_latitude = row[4]
    neighbor_longitude = row[5]
    average_snr = row[6]
    min_snr = row[7]
    max_snr = row[8]

    # Ensure each node has only one marker on the map
    if node_long_name not in node_positions:
        node_positions[node_long_name] = (node_latitude, node_longitude)

    if neighbor_long_name not in node_positions:
        node_positions[neighbor_long_name] = (neighbor_latitude, neighbor_longitude)

    # Add the connection between the node and its neighbor with SNR details
    connections.append((
        (node_latitude, neighbor_latitude),
        (node_longitude, neighbor_longitude),
        average_snr,
        min_snr,
        max_snr
    ))

# Create the map centered around the first node with Folium
if node_positions:
    first_position = next(iter(node_positions.values()))
    folium_map = folium.Map(location=first_position, zoom_start=10)

    # Use MarkerCluster to handle overlapping markers
    marker_cluster = MarkerCluster().add_to(folium_map)

    # Add nodes to the map with customized popups
    for node_long_name, (latitude, longitude) in node_positions.items():
        popup_html = f"""
        <div style="font-size: 14px; font-weight: bold; text-align: center; width: 200px;">
            {node_long_name}
        </div>
        """
        popup = folium.Popup(popup_html, max_width=300)
        folium.Marker(
            location=[latitude, longitude],
            popup=popup,
            icon=folium.Icon(color="blue")
        ).add_to(marker_cluster)

    # Draw connections between nodes and their neighbors with SNR details
    for connection in connections:
        line_popup = folium.Popup(
            f"<b>Average SNR:</b> {connection[2]:.2f}<br>"
            f"<b>Min SNR:</b> {connection[3]:.2f}<br>"
            f"<b>Max SNR:</b> {connection[4]:.2f}", 
            max_width=200
        )
        folium.PolyLine(
            locations=[[connection[0][0], connection[1][0]], [connection[0][1], connection[1][1]]],
            color="blue",
            weight=2.5,
            popup=line_popup
        ).add_to(folium_map)

    # Save the map to an HTML file
    folium_map.save("mesh_network_osm_map.html")

    print("Map has been created. Open 'mesh_network_map.html' in your browser to view it.")
else:
    print("No valid coordinates available to create the map.")
