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
),
AggregatedNeighbors AS (
    SELECT
        node_id,
        neighbor_node_id,
        AVG(snr) AS average_snr,
        MIN(snr) AS min_snr,
        MAX(snr) AS max_snr,
        COUNT(*) AS record_count,
        MAX(timestamp) AS last_seen
    FROM
        neighbors
    GROUP BY
        node_id, neighbor_node_id
)
SELECT 
    n1.user_id AS node_user_id,
    n1.long_name AS node_long_name,
    n1.hw_model AS node_hw_model,
    n1.short_name AS node_short_name,
    datetime(n1.last_heard, 'unixepoch', 'localtime') AS node_last_heard,
    n2.user_id AS neighbor_user_id,
    n2.long_name AS neighbor_long_name,
    n2.hw_model AS neighbor_hw_model,
    n2.short_name AS neighbor_short_name,
    datetime(ag.last_seen, 'unixepoch', 'localtime') AS neighbor_last_heard,
    lp1.latitude AS node_latitude,
    lp1.longitude AS node_longitude,
    lp2.latitude AS neighbor_latitude,
    lp2.longitude AS neighbor_longitude,
    ag.average_snr,
    ag.min_snr,
    ag.max_snr,
    ag.record_count
FROM 
    AggregatedNeighbors ag
JOIN 
    nodes n1 ON ag.node_id = n1.node_number
LEFT JOIN 
    nodes n2 ON ag.neighbor_node_id = n2.node_number
LEFT JOIN 
    LatestPositions lp1 ON n1.user_id = lp1.node_id AND lp1.rn = 1
LEFT JOIN 
    LatestPositions lp2 ON n2.user_id = lp2.node_id AND lp2.rn = 1
WHERE
    lp1.latitude IS NOT NULL AND lp1.longitude IS NOT NULL AND
    lp2.latitude IS NOT NULL AND lp2.longitude IS NOT NULL
ORDER BY 
    n1.long_name, neighbor_last_heard DESC;
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
    node_user_id = row[0]
    node_long_name = row[1]
    node_hw_model = row[2]
    node_short_name = row[3]
    node_last_heard = row[4]
    neighbor_user_id = row[5]
    neighbor_long_name = row[6]
    neighbor_hw_model = row[7]
    neighbor_short_name = row[8]
    neighbor_last_heard = row[9]
    node_latitude = row[10]
    node_longitude = row[11]
    neighbor_latitude = row[12]
    neighbor_longitude = row[13]
    average_snr = row[14]
    min_snr = row[15]
    max_snr = row[16]
    record_count = row[17]

    # Ensure each node has only one marker on the map
    if node_long_name not in node_positions:
        node_positions[node_long_name] = {
            'latitude': node_latitude,
            'longitude': node_longitude,
            'user_id': node_user_id,
            'hw_model': node_hw_model,
            'short_name': node_short_name,
            'last_heard': node_last_heard
        }

    if neighbor_long_name not in node_positions:
        node_positions[neighbor_long_name] = {
            'latitude': neighbor_latitude,
            'longitude': neighbor_longitude,
            'user_id': neighbor_user_id,
            'hw_model': neighbor_hw_model,
            'short_name': neighbor_short_name,
            'last_heard': neighbor_last_heard
        }

    # Add the connection between the node and its neighbor with SNR details
    connections.append({
        'node_latitude': node_latitude,
        'node_longitude': node_longitude,
        'neighbor_latitude': neighbor_latitude,
        'neighbor_longitude': neighbor_longitude,
        'average_snr': average_snr,
        'min_snr': min_snr,
        'max_snr': max_snr,
        'record_count': record_count,
        'node_long_name': node_long_name,
        'neighbor_long_name': neighbor_long_name
    })

# Create the map centered around the first node with Folium
if node_positions:
    first_position = next(iter(node_positions.values()))['latitude'], next(iter(node_positions.values()))['longitude']
    folium_map = folium.Map(location=first_position, zoom_start=10)

    # Create feature groups for markers and lines
    node_group = folium.FeatureGroup(name="Nodes")
    connection_group = folium.FeatureGroup(name="Connections")

    # Use MarkerCluster to handle overlapping markers
    marker_cluster = MarkerCluster().add_to(node_group)

    # Add nodes to the map with customized popups
    for node_long_name, details in node_positions.items():
        popup_html = f"""
        <div style="font-size: 14px; text-align: left; width: 250px;">
            <b>{node_long_name}</b><br>
            <b>User ID:</b> {details.get('user_id', 'N/A')}<br>
            <b>Hardware Model:</b> {details.get('hw_model', 'N/A')}<br>
            <b>Short Name:</b> {details.get('short_name', 'N/A')}<br>
            <b>Last Heard:</b> {details.get('last_heard', 'N/A')}
        </div>
        """
        popup = folium.Popup(popup_html, max_width=300)
        folium.Marker(
            location=[details['latitude'], details['longitude']],
            popup=popup,
            icon=folium.Icon(color="blue")
        ).add_to(marker_cluster)

    # Draw connections between nodes and their neighbors with SNR details
    for connection in connections:
        line_popup = folium.Popup(
            f"<b>Connection between:</b> {connection['node_long_name']} <b>and</b> {connection['neighbor_long_name']}<br>"
            f"<b>Average SNR:</b> {connection['average_snr']:.2f}<br>"
            f"<b>Min SNR:</b> {connection['min_snr']:.2f}<br>"
            f"<b>Max SNR:</b> {connection['max_snr']:.2f}<br>"
            f"<b>Records Collected:</b> {connection['record_count']}", 
            max_width=300
        )
        folium.PolyLine(
            locations=[[connection['node_latitude'], connection['node_longitude']], [connection['neighbor_latitude'], connection['neighbor_longitude']]],
            color="blue",
            weight=2.5,
            popup=line_popup
        ).add_to(connection_group)

    # Add the groups to the map
    node_group.add_to(folium_map)
    connection_group.add_to(folium_map)

    # Add layer control to toggle visibility
    folium.LayerControl().add_to(folium_map)

    # Save the map to an HTML file
    folium_map.save("mesh_network_osm_map.html")

    print("Map has been created. Open 'mesh_network_osm_map.html' in your browser to view it.")
else:
    print("No valid coordinates available to create the map.")
