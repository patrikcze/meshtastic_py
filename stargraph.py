import sqlite3
import networkx as nx
import matplotlib.pyplot as plt

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

# Now `results` contains the data from the SQL query

# Initialize a new graph
G = nx.Graph()

# Add edges to the graph based on the query results
pos = {}
for row in results:
    node_long_name = row[0]
    neighbor_long_name = row[1]
    node_latitude = row[2]
    node_longitude = row[3]
    neighbor_latitude = row[4]
    neighbor_longitude = row[5]

    # Add an edge between the node and its neighbor
    if neighbor_long_name:  # Only add if neighbor exists
        G.add_edge(node_long_name, neighbor_long_name)

    # Add positions based on latitude and longitude if available
    if node_latitude is not None and node_longitude is not None:
        pos[node_long_name] = (node_longitude, node_latitude)
    if neighbor_latitude is not None and neighbor_longitude is not None:
        pos[neighbor_long_name] = (neighbor_longitude, neighbor_latitude)

# Use the positions (if available) to layout the nodes, else use spring_layout
default_pos = nx.spring_layout(G)

# Combine positions with default positions for nodes that don't have a specified position
for node in G.nodes():
    if node not in pos:
        pos[node] = default_pos[node]

nx.draw(G, pos, with_labels=True, node_size=3000, node_color='lightblue', font_size=10, font_weight='bold')

# Show the plot
plt.show()
