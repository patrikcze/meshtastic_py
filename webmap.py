#!/usr/bin/env python3
from flask import Flask, render_template_string
import sqlite3
import folium
from folium.plugins import MarkerCluster
from datetime import datetime, timedelta

app = Flask(__name__)

# Define the cutoff for "active" nodes (last 1 days)
active_cutoff = datetime.now() - timedelta(days=1)

def generate_map():
    # Connect to the SQLite database
    conn = sqlite3.connect('messages.db')
    cursor = conn.cursor()

    #  Combined query to fetch nodes, neighbors, positions, and SNR details
    query = f"""
    WITH LatestPositions AS (
        SELECT 
            p.node_id,
            p.latitude,
            p.longitude,
            p.altitude,
            strftime('%d.%m.%Y %H:%M:%S', p.timestamp, 'unixepoch', 'localtime') AS last_position_time,
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
    ),
    NodesWithNeighbors AS (
        SELECT 
            n1.user_id AS node_user_id,
            n1.long_name AS node_long_name,
            n1.hw_model AS node_hw_model,
            n1.short_name AS node_short_name,
            strftime('%d.%m.%Y %H:%M:%S', n1.last_heard, 'unixepoch', 'localtime') AS node_last_heard,
            n2.user_id AS neighbor_user_id,
            n2.long_name AS neighbor_long_name,
            n2.hw_model AS neighbor_hw_model,
            n2.short_name AS neighbor_short_name,
            strftime('%d.%m.%Y %H:%M:%S', ag.last_seen, 'unixepoch', 'localtime') AS neighbor_last_heard,
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
            n1.long_name, neighbor_last_heard DESC
    )
    SELECT * FROM NodesWithNeighbors
    UNION ALL
    SELECT 
        n.user_id AS node_user_id,
        n.long_name AS node_long_name,
        n.hw_model AS node_hw_model,
        n.short_name AS node_short_name,
        strftime('%d.%m.%Y %H:%M:%S', n.last_heard, 'unixepoch', 'localtime') AS node_last_heard,
        NULL AS neighbor_user_id,
        NULL AS neighbor_long_name,
        NULL AS neighbor_hw_model,
        NULL AS neighbor_short_name,
        NULL AS neighbor_last_heard,
        lp.latitude AS node_latitude,
        lp.longitude AS node_longitude,
        NULL AS neighbor_latitude,
        NULL AS neighbor_longitude,
        NULL AS average_snr,
        NULL AS min_snr,
        NULL AS max_snr,
        NULL AS record_count
    FROM 
        nodes n
    LEFT JOIN 
        AggregatedNeighbors ag ON n.node_number = ag.node_id
    LEFT JOIN 
        LatestPositions lp ON n.user_id = lp.node_id AND lp.rn = 1
    WHERE 
        ag.node_id IS NULL AND lp.latitude IS NOT NULL AND lp.longitude IS NOT NULL;
    """

    cursor.execute(query)
    results = cursor.fetchall()

    # Close the database connection
    conn.close()

    # Prepare lists for the map
    node_positions = {}
    connections = []
    no_neighbor_positions = []

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

        node_last_heard_dt = datetime.strptime(node_last_heard, '%d.%m.%Y %H:%M:%S')
        node_is_active = node_last_heard_dt > active_cutoff

        if neighbor_last_heard:
            neighbor_last_heard_dt = datetime.strptime(neighbor_last_heard, '%d.%m.%Y %H:%M:%S')
            neighbor_is_active = neighbor_last_heard_dt > active_cutoff
        else:
            neighbor_is_active = False

        if neighbor_long_name is None:
            # Handle nodes without neighbors
            no_neighbor_positions.append({
                'latitude': node_latitude,
                'longitude': node_longitude,
                'user_id': node_user_id,
                'hw_model': node_hw_model,
                'short_name': node_short_name,
                'last_heard': node_last_heard,
                'long_name': node_long_name,
                'is_active': node_is_active
            })
        else:
            # Ensure each node has only one marker on the map
            if node_long_name not in node_positions:
                node_positions[node_long_name] = {
                    'latitude': node_latitude,
                    'longitude': node_longitude,
                    'user_id': node_user_id,
                    'hw_model': node_hw_model,
                    'short_name': node_short_name,
                    'last_heard': node_last_heard,
                    'is_active': node_is_active
                }

            if neighbor_long_name not in node_positions:
                node_positions[neighbor_long_name] = {
                    'latitude': neighbor_latitude,
                    'longitude': neighbor_longitude,
                    'user_id': neighbor_user_id,
                    'hw_model': neighbor_hw_model,
                    'short_name': neighbor_short_name,
                    'last_heard': neighbor_last_heard,
                    'is_active': neighbor_is_active
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
                'neighbor_long_name': neighbor_long_name,
                'node_is_active': node_is_active,
                'neighbor_is_active': neighbor_is_active
            })

    # Count the total number of unique nodes
    total_nodes = len(node_positions) + len(no_neighbor_positions)

    # Create the map centered around the first node with Folium
    if node_positions or no_neighbor_positions:
        first_position = (next(iter(node_positions.values()))['latitude'], next(iter(node_positions.values()))['longitude']) \
            if node_positions else (no_neighbor_positions[0]['latitude'], no_neighbor_positions[0]['longitude'])
        folium_map = folium.Map(location=first_position, zoom_start=10)

        # Create feature groups for markers, lines, and nodes without neighbors
        node_group = folium.FeatureGroup(name="Nodes with neigbors")
        connection_group = folium.FeatureGroup(name="Neigbors")
        no_neighbor_group = folium.FeatureGroup(name="Nodes without neighbors")

        # Use MarkerCluster to handle overlapping markers
        marker_cluster = MarkerCluster().add_to(node_group)

        # Add nodes to the map with customized popups
        for node_long_name, details in node_positions.items():
            color = "blue" if details['is_active'] else "gray"
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
                icon=folium.Icon(color=color)
            ).add_to(marker_cluster)

        # Draw connections between nodes and their neighbors with SNR details
        for connection in connections:
            line_style = {'color': 'blue', 'weight': 2.5}
            if not connection['node_is_active'] or not connection['neighbor_is_active']:
                line_style['dash_array'] = '5, 5'  # dashed line for inactive nodes

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
                **line_style,
                popup=line_popup
            ).add_to(connection_group)

        # Add nodes without neighbors to the map
        for details in no_neighbor_positions:
            color = "red" if details['is_active'] else "gray"
            popup_html = f"""
            <div style="font-size: 14px; text-align: left; width: 250px;">
                <b>{details['long_name']}</b><br>
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
                icon=folium.Icon(color=color)
            ).add_to(no_neighbor_group)

        # Add the groups to the map
        node_group.add_to(folium_map)
        connection_group.add_to(folium_map)
        no_neighbor_group.add_to(folium_map)

        # Add a timestamp and total node count at the top of the map as a custom HTML element
        timestamp = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        info_html = f"""
        <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
                    font-size: 12px; color: black; background-color: white; padding: 5px; 
                    border: 2px solid gray; z-index: 9999; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);">
            Map generated on {timestamp}<br>
            Total nodes displayed: {total_nodes}
        </div>
        """
        folium_map.get_root().html.add_child(folium.Element(info_html))

        # Add layer control to toggle visibility
        folium.LayerControl().add_to(folium_map)

        # Save the map to an HTML string
        map_html = folium_map._repr_html_()

        return map_html
    else:
        return "<p>No valid coordinates available to create the map.</p>"

@app.route('/')
def index():
    map_html = generate_map()
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Mesh Network Map</title>
        </head>
        <body>
            {{ map_html | safe }}
        </body>
        </html>
    """, map_html=map_html)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
