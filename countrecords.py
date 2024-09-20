import sqlite3

def count_records_in_tables(database_path):
    conn = sqlite3.connect(database_path)
    c = conn.cursor()
    
    # List of all your tables
    tables = [
        'environment', 
        'neighbors', 
        'positions', 
        'telemetry', 
        'messages', 
        'nodes', 
        'routing', 
        'traceroute'
    ]
    
    table_counts = {}

    for table in tables:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        table_counts[table] = count
    
    conn.close()
    
    return table_counts

# Usage
database_path = 'messages.db'  # Replace with your actual database path
table_counts = count_records_in_tables(database_path)

for table, count in table_counts.items():
    print(f"Table '{table}' has {count} records.")

