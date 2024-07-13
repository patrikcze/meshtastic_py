import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import time
import sqlite3
import logging

logging.basicConfig(level=logging.DEBUG)

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
                    long_name TEXT
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
    conn.commit()
    conn.close()

def store_message(message_id, sender, recipient, message, timestamp, channel):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO messages (message_id, sender, recipient, message, timestamp, channel) VALUES (?, ?, ?, ?, ?, ?)''', 
                  (message_id, sender, recipient, message, timestamp, channel))
        conn.commit()
    except sqlite3.IntegrityError:
        logging.warning(f"Duplicate message with ID {message_id} detected. Ignoring...")
    conn.close()

def store_telemetry(node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO telemetry (node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp))
    conn.commit()
    conn.close()

def store_position(node_id, latitude, longitude, altitude, time, sats_in_view, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO positions (node_id, latitude, longitude, altitude, time, sats_in_view, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (node_id, latitude, longitude, altitude, time, sats_in_view, timestamp))
    conn.commit()
    conn.close()

def upsert_node(node_id, short_name, long_name):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO nodes (node_id, short_name, long_name)
                 VALUES (?, ?, ?)
                 ON CONFLICT(node_id) DO UPDATE SET
                 short_name=excluded.short_name, long_name=excluded.long_name''', 
              (node_id, short_name, long_name))
    conn.commit()
    conn.close()

def on_receive(packet, interface):
    """Callback function to handle received messages."""
    try:
        timestamp = int(time.time())
        
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
            to_node_info = interface.nodes.get(toId, {})
            to_short_name = to_node_info.get('user', {}).get('shortName', '')
            to_long_name = to_node_info.get('user', {}).get('longName', '')
            
            # Upsert node information
            upsert_node(fromId, from_short_name, from_long_name)
            upsert_node(toId, to_short_name, to_long_name)
            
            if portnum == 'TEXT_MESSAGE_APP' and text:
                # Filter for text messages only
                logging.info(f"Plain text message received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {text}")
                store_message(message_id, fromId, toId, text, timestamp, channel)
            elif portnum == 'TELEMETRY_APP':
                # Handle telemetry data
                telemetry = packet['decoded'].get('telemetry', {})
                battery_level = telemetry.get('deviceMetrics', {}).get('batteryLevel', None)
                voltage = telemetry.get('deviceMetrics', {}).get('voltage', None)
                channel_utilization = telemetry.get('deviceMetrics', {}).get('channelUtilization', None)
                air_util_tx = telemetry.get('deviceMetrics', {}).get('airUtilTx', None)
                uptime_seconds = telemetry.get('deviceMetrics', {}).get('uptimeSeconds', None)
                
                logging.info(f"Telemetry data received from {from_short_name} ({fromId}): battery_level={battery_level}, voltage={voltage}, channel_utilization={channel_utilization}, air_util_tx={air_util_tx}, uptime_seconds={uptime_seconds}")
                store_telemetry(fromId, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp)
            elif portnum == 'POSITION_APP':
                # Handle position data
                position = packet['decoded'].get('position', {})
                latitude = position.get('latitude', None)
                longitude = position.get('longitude', None)
                altitude = position.get('altitude', None)
                time = position.get('time', None)
                sats_in_view = position.get('satsInView', None)
                
                logging.info(f"Position data received from {from_short_name} ({fromId}): latitude={latitude}, longitude={longitude}, altitude={altitude}, time={time}, sats_in_view={sats_in_view}")
                store_position(fromId, latitude, longitude, altitude, time, sats_in_view, timestamp)
            else:
                logging.info(f"Non-text message or empty text received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {portnum}")
        elif 'encrypted' in packet:
            encrypted_text = packet.get('encrypted')
            message_id = packet['id']  # Unique message ID
            fromId = packet.get('fromId')
            toId = packet.get('toId')
            channel = packet.get('channel', -1)  # Default to -1 if channel is not found
            
            from_node_info = interface.nodes.get(fromId, {})
            from_short_name = from_node_info.get('user', {}).get('shortName', '')
            from_long_name = from_node_info.get('user', {}).get('longName', '')
            to_node_info = interface.nodes.get(toId, {})
            to_short_name = to_node_info.get('user', {}).get('shortName', '')
            to_long_name = to_node_info.get('user', {}).get('longName', '')
            
            upsert_node(fromId, from_short_name, from_long_name)
            upsert_node(toId, to_short_name, to_long_name)
            
            logging.info(f"Encrypted message received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {encrypted_text}")
            store_message(message_id, fromId, toId, encrypted_text, timestamp, channel)
        else:
            logging.info(f"Unknown message format: {packet}")
    except Exception as e:
        logging.error(f"Error processing packet: {e}")

def mark_message_as_read(message_id):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('UPDATE messages SET read = 1 WHERE message_id = ?', (message_id,))
    conn.commit()
    conn.close()

def get_unread_messages():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('SELECT * FROM messages WHERE read = 0')
    messages = c.fetchall()
    conn.close()
    return messages

def main():
    # Initialize the database
    initialize_db()

    # Initialize the serial interface
    interface = meshtastic.serial_interface.SerialInterface()

    # Subscribe to messages
    pub.subscribe(on_receive, "meshtastic.receive")

    print("Listening for messages... Press Ctrl+C to stop.")
    try:
        while True:
            # Keep the script running to listen for messages
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping message listener...")

if __name__ == "__main__":
    main()
