import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import time as time_module
import sqlite3
import threading
from queue import Queue, Empty

# Global variables for database connection pooling
db_queue = Queue()
stop_event = threading.Event()

def initialize_db():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    # Create messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER UNIQUE,
                    sender TEXT,
                    recipient TEXT,
                    message TEXT,
                    timestamp INTEGER,
                    channel INTEGER,
                    read INTEGER DEFAULT 0
                )''')
    # Create telemetry table
    c.execute('''CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT,
                    battery_level INTEGER,
                    voltage REAL,
                    channel_utilization REAL,
                    air_util_tx REAL,
                    uptime_seconds INTEGER,
                    timestamp INTEGER
                )''')
    # Create nodes table
    c.execute('''CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    short_name TEXT,
                    long_name TEXT,
                    hw_model TEXT,
                    last_heard INTEGER
                )''')
    # Create positions table
    c.execute('''CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT,
                    latitude REAL,
                    longitude REAL,
                    altitude REAL,
                    time INTEGER,
                    sats_in_view INTEGER,
                    timestamp INTEGER
                )''')
    # Create environment metrics table
    c.execute('''CREATE TABLE IF NOT EXISTS environment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT,
                    temperature REAL,
                    humidity REAL,
                    bar REAL,
                    iaq REAL,
                    timestamp INTEGER
                )''')
    conn.commit()
    conn.close()

def db_worker():
    conn = sqlite3.connect('messages.db')
    while not stop_event.is_set():
        try:
            task = db_queue.get(timeout=1)
        except Empty:
            continue
        cursor = conn.cursor()
        try:
            cursor.execute(*task)
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"SQLite Error: {e}")
        db_queue.task_done()
    conn.close()

def store_message(message_id, sender, recipient, message, timestamp, channel):
    query = '''INSERT INTO messages (message_id, sender, recipient, message, timestamp, channel) VALUES (?, ?, ?, ?, ?, ?)'''
    db_queue.put((query, (message_id, sender, recipient, message, timestamp, channel)))

def store_telemetry(node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp):
    query = '''INSERT INTO telemetry (node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?)'''
    db_queue.put((query, (node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp)))

def store_position(node_id, latitude, longitude, altitude, time, sats_in_view, timestamp):
    query = '''INSERT INTO positions (node_id, latitude, longitude, altitude, time, sats_in_view, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?)'''
    db_queue.put((query, (node_id, latitude, longitude, altitude, time, sats_in_view, timestamp)))

def store_environment(node_id, temperature, humidity, bar, iaq, timestamp):
    query = '''INSERT INTO environment (node_id, temperature, humidity, bar, iaq, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?)'''
    db_queue.put((query, (node_id, temperature, humidity, bar, iaq, timestamp)))

def upsert_node(node_id, short_name, long_name, hw_model, last_heard):
    query = '''INSERT INTO nodes (node_id, short_name, long_name, hw_model, last_heard)
                 VALUES (?, ?, ?, ?, ?)
                 ON CONFLICT(node_id) DO UPDATE SET
                 short_name=excluded.short_name, long_name=excluded.long_name, hw_model=excluded.hw_model, last_heard=excluded.last_heard'''
    db_queue.put((query, (node_id, short_name, long_name, hw_model, last_heard)))

def on_receive(packet, interface):
    """Callback function to handle received messages."""
    timestamp = int(time_module.time())
    
    if 'decoded' in packet:
        portnum = packet['decoded'].get('portnum')
        text = packet['decoded'].get('text')
        message_id = packet['id']  # Unique message ID
        fromId = packet.get('fromId')
        toId = packet.get('toId')
        channel = packet.get('channel', -1)  # Default to -1 if channel is not found
        
        # Get node information
        from_node_info = interface.nodes.get(fromId, {})
        from_short_name = from_node_info.get('user', {}).get('shortName', '')
        from_long_name = from_node_info.get('user', {}).get('longName', '')
        from_hw_model = from_node_info.get('user', {}).get('hwModel', '')
        from_last_heard = from_node_info.get('lastHeard', 0)
        to_node_info = interface.nodes.get(toId, {})
        to_short_name = to_node_info.get('user', {}).get('shortName', '')
        to_long_name = to_node_info.get('user', {}).get('longName', '')
        to_hw_model = to_node_info.get('user', {}).get('hwModel', '')
        to_last_heard = to_node_info.get('lastHeard', 0)
        
        # Upsert node information
        upsert_node(fromId, from_short_name, from_long_name, from_hw_model, from_last_heard)
        upsert_node(toId, to_short_name, to_long_name, to_hw_model, to_last_heard)
        
        # Filter for text messages only
        if portnum == 'TEXT_MESSAGE_APP' and text:
            print(f"Plain text message received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {text}")
            store_message(message_id, fromId, toId, text, timestamp, channel)
        elif portnum == 'TELEMETRY_APP':
            telemetry = packet['decoded'].get('telemetry', {})
            battery_level = telemetry.get('deviceMetrics', {}).get('batteryLevel', None)
            voltage = telemetry.get('deviceMetrics', {}).get('voltage', None)
            channel_utilization = telemetry.get('deviceMetrics', {}).get('channelUtilization', None)
            air_util_tx = telemetry.get('deviceMetrics', {}).get('airUtilTx', None)
            uptime_seconds = telemetry.get('deviceMetrics', {}).get('uptimeSeconds', None)
            
            print(f"Telemetry data received from {from_short_name} ({fromId}): battery_level={battery_level}, voltage={voltage}, channel_utilization={channel_utilization}, air_util_tx={air_util_tx}, uptime_seconds={uptime_seconds}")
            store_telemetry(fromId, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp)
        elif portnum == 'POSITION_APP':
            position = packet['decoded'].get('position', {})
            latitude = position.get('latitude', None)
            longitude = position.get('longitude', None)
            altitude = position.get('altitude', None)
            time = position.get('time', None)
            sats_in_view = position.get('satsInView', None)
            
            print(f"Position data received from {from_short_name} ({fromId}): latitude={latitude}, longitude={longitude}, altitude={altitude}, time={time}, sats_in_view={sats_in_view}")
            store_position(fromId, latitude, longitude, altitude, time, sats_in_view, timestamp)
        elif portnum == 'ENVIRONMENT_APP':
            environment = packet['decoded'].get('environment', {})
            temperature = environment.get('temperature', None)
            humidity = environment.get('humidity', None)
            bar = environment.get('bar', None)
            iaq = environment.get('iaq', None)

            print(f"Environment data received from {from_short_name} ({fromId}): temperature={temperature}, humidity={humidity}, bar={bar}, iaq={iaq}")
            store_environment(fromId, temperature, humidity, bar, iaq, timestamp)
        elif portnum == 'NODEINFO_APP':
            node_info = packet['decoded'].get('user', {})
            long_name = node_info.get('longName', None)
            short_name = node_info.get('shortName', None)
            hw_model = node_info.get('hwModel', None)
            last_heard = packet['decoded'].get('lastHeard', None)
            device_metrics = packet['decoded'].get('deviceMetrics', {})
            battery_level = device_metrics.get('batteryLevel', None)
            voltage = device_metrics.get('voltage', None)
            channel_utilization = device_metrics.get('channelUtilization', None)
            air_util_tx = device_metrics.get('airUtilTx', None)
            uptime_seconds = device_metrics.get('uptimeSeconds', None)
            
            print(f"Node info received from {from_short_name} ({fromId}): long_name={long_name}, short_name={short_name}, hw_model={hw_model}, last_heard={last_heard}, battery_level={battery_level}, voltage={voltage}, channel_utilization={channel_utilization}, air_util_tx={air_util_tx}, uptime_seconds={uptime_seconds}")
            upsert_node(fromId, short_name, long_name, hw_model, last_heard)
        else:
            print(f"Non-text message or empty text received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {portnum}")
    elif 'encrypted' in packet:
        encrypted_text = packet.get('encrypted')
        message_id = packet['id']  # Unique message ID
        fromId = packet.get('fromId')
        toId = packet.get('toId')
        channel = packet.get('channel', -1)  # Default to -1 if channel is not found
        
        from_node_info = interface.nodes.get(fromId, {})
        from_short_name = from_node_info.get('user', {}).get('shortName', '')
        from_long_name = from_node_info.get('user', {}).get('longName', '')
        from_hw_model = from_node_info.get('user', {}).get('hwModel', '')
        from_last_heard = from_node_info.get('lastHeard', 0)
        to_node_info = interface.nodes.get(toId, {})
        to_short_name = to_node_info.get('user', {}).get('shortName', '')
        to_long_name = to_node_info.get('user', {}).get('longName', '')
        to_hw_model = to_node_info.get('user', {}).get('hwModel', '')
        to_last_heard = to_node_info.get('lastHeard', 0)
        
        upsert_node(fromId, from_short_name, from_long_name, from_hw_model, from_last_heard)
        upsert_node(toId, to_short_name, to_long_name, to_hw_model, to_last_heard)
        
        print(f"Encrypted message received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {encrypted_text}")
        store_message(message_id, fromId, toId, encrypted_text, timestamp, channel)
    else:
        print(f"Unknown message format: {packet}")

def reconnect(interface):
    while not stop_event.is_set():
        try:
            if not interface.isConnected:
                print("Reconnecting...")
                interface.connect()
            time_module.sleep(10)
        except Exception as e:
            print(f"Reconnection failed: {e}")
            time_module.sleep(10)

def main():
    # Initialize the database
    initialize_db()

    # Start the database worker thread
    threading.Thread(target=db_worker, daemon=True).start()

    # Initialize the serial interface
    interface = meshtastic.serial_interface.SerialInterface()

    # Start the reconnection thread
    threading.Thread(target=reconnect, args=(interface,), daemon=True).start()

    # Subscribe to messages
    pub.subscribe(on_receive, "meshtastic.receive")

    print("Listening for messages... Press Ctrl+C to stop.")
    try:
        while True:
            # Keep the script running to listen for messages
            time_module.sleep(1)
    except KeyboardInterrupt:
        print("Stopping message listener...")
        stop_event.set()
        db_queue.join()

if __name__ == "__main__":
    main()
