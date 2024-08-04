import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import time as time_module
import sqlite3

# Initialize the database
def initialize_db():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    # Create necessary tables
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
    c.execute('''CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    short_name TEXT,
                    long_name TEXT,
                    hw_model TEXT,
                    last_heard INTEGER
                )''')
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
    c.execute('''CREATE TABLE IF NOT EXISTS environment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT,
                    temperature REAL,
                    humidity REAL,
                    bar REAL,
                    iaq REAL,
                    timestamp INTEGER
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS traceroute (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_node TEXT,
                    to_node TEXT,
                    hop_id INTEGER,
                    hop_node TEXT,
                    hop_snr REAL,
                    timestamp INTEGER
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS routing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_node TEXT,
                    to_node TEXT,
                    routes TEXT,
                    timestamp INTEGER
                )''')
    conn.commit()
    conn.close()

# Store functions
def store_message(message_id, sender, recipient, message, timestamp, channel):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO messages (message_id, sender, recipient, message, timestamp, channel) VALUES (?, ?, ?, ?, ?, ?)''', 
                  (message_id, sender, recipient, message, timestamp, channel))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Duplicate message with ID {message_id} detected. Ignoring...")
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

def store_environment(node_id, temperature, relative_humidity, barometric_pressure, iaq, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO environment (node_id, temperature, humidity, bar, iaq, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (node_id, temperature, relative_humidity, barometric_pressure, iaq, timestamp))
    conn.commit()
    conn.close()

def store_traceroute(from_node, to_node, hops, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    hop_id = 0
    for hop in hops:
        hop_id += 1
        hop_node = hop.get('nodeId')
        hop_snr = hop.get('snr')
        c.execute('''INSERT INTO traceroute (from_node, to_node, hop_id, hop_node, hop_snr, timestamp)
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                  (from_node, to_node, hop_id, hop_node, hop_snr, timestamp))
    conn.commit()
    conn.close()

def store_routing(from_node, to_node, routes, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO routing (from_node, to_node, routes, timestamp)
                 VALUES (?, ?, ?, ?)''', 
              (from_node, to_node, routes, timestamp))
    conn.commit()
    conn.close()

def upsert_node(node_id, short_name, long_name, hw_model, last_heard):
    if node_id is None:
        print(f"Skipping upsert for node with None node_id: {short_name}, {long_name}, {hw_model}, {last_heard}")
        return
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO nodes (node_id, short_name, long_name, hw_model, last_heard)
                 VALUES (?, ?, ?, ?, ?)
                 ON CONFLICT(node_id) DO UPDATE SET
                 short_name=excluded.short_name, long_name=excluded.long_name, hw_model=excluded.hw_model, last_heard=excluded.last_heard''', 
              (node_id, short_name, long_name, hw_model, last_heard))
    conn.commit()
    conn.close()

# on_receive function
def on_receive(packet, interface):
    """Callback function to handle received messages."""
    timestamp = int(time_module.time())

    # Debug print statement to log the entire packet
    # print(f"Received packet: {packet}")

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
        from_last_heard = from_node_info.get('lastHeard')
        if from_last_heard is None:
            from_last_heard = 0

        to_node_info = interface.nodes.get(toId, {})
        to_short_name = to_node_info.get('user', {}).get('shortName', '')
        to_long_name = to_node_info.get('user', {}).get('longName', '')
        to_hw_model = to_node_info.get('user', {}).get('hwModel', '')
        to_last_heard = to_node_info.get('lastHeard')
        if to_last_heard is None:
            to_last_heard = 0

        # Debugging information
        #print(f"From node: {fromId}, {from_short_name}, {from_long_name}, {from_hw_model}, {from_last_heard}")
        #print(f"To node: {toId}, {to_short_name}, {to_long_name}, {to_hw_model}, {to_last_heard}")

        # Upsert node information
        upsert_node(fromId, from_short_name, from_long_name, from_hw_model, from_last_heard)
        upsert_node(toId, to_short_name, to_long_name, to_hw_model, to_last_heard)

        if portnum == 'TEXT_MESSAGE_APP' and text:
            print(f"✉️  Plain text message received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {text}")
            store_message(message_id, fromId, toId, text, timestamp, channel)
        elif portnum == 'TELEMETRY_APP':
            telemetry = packet['decoded'].get('telemetry', {})
            battery_level = telemetry.get('deviceMetrics', {}).get('batteryLevel', None)
            voltage = telemetry.get('deviceMetrics', {}).get('voltage', None)
            channel_utilization = telemetry.get('deviceMetrics', {}).get('channelUtilization', None)
            air_util_tx = telemetry.get('deviceMetrics', {}).get('airUtilTx', None)
            uptime_seconds = telemetry.get('deviceMetrics', {}).get('uptimeSeconds', None)
            
            print(f"📊 Telemetry data received from {from_short_name} ({fromId}): battery_level={battery_level}, voltage={voltage}, channel_utilization={channel_utilization}, air_util_tx={air_util_tx}, uptime_seconds={uptime_seconds}")
            store_telemetry(fromId, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp)

            # Check if environmental data is present in telemetry
            environment_metrics = telemetry.get('environmentMetrics', {})
            if environment_metrics:
                temperature = environment_metrics.get('temperature', None)
                relative_humidity = environment_metrics.get('relativeHumidity', None)
                barometric_pressure = environment_metrics.get('barometricPressure', None)
                iaq = environment_metrics.get('iaq', None)  # Assuming IAQ (Indoor Air Quality) might be included

                print(f"🌲 Environment data found in telemetry from {from_short_name} ({fromId}): temperature={temperature}, relative_humidity={relative_humidity}, barometric_pressure={barometric_pressure}, iaq={iaq}")
                store_environment(fromId, temperature, relative_humidity, barometric_pressure, iaq, timestamp)

        elif portnum == 'POSITION_APP':
            position = packet['decoded'].get('position', {})
            latitude = position.get('latitude', None)
            longitude = position.get('longitude', None)
            altitude = position.get('altitude', None)
            time = position.get('time', None)
            sats_in_view = position.get('satsInView', None)
            
            print(f"📌 Position data received from {from_short_name} ({fromId}): latitude={latitude}, longitude={longitude}, altitude={altitude}, time={time}, sats_in_view={sats_in_view}")
            store_position(fromId, latitude, longitude, altitude, time, sats_in_view, timestamp)
        elif portnum == 'ENVIRONMENTAL_MEASUREMENT_APP':
            environment = packet['decoded'].get('environment', {})
            temperature = environment.get('temperature', None)
            humidity = environment.get('humidity', None)
            bar = environment.get('bar', None)
            iaq = environment.get('iaq', None)

            print(f"🌲 Environment data received from {from_short_name} ({fromId}): temperature={temperature}, humidity={humidity}, bar={bar}, iaq={iaq}")
            store_environment(fromId, temperature, humidity, bar, iaq, timestamp)
        elif portnum == 'NODEINFO_APP':
            node_info = packet['decoded'].get('user', {})
            long_name = node_info.get('longName', None)
            short_name = node_info.get('shortName', None)
            hw_model = node_info.get('hwModel', None)
            snr = packet['decoded'].get('snr', None)
            last_heard = packet['decoded'].get('lastHeard', None)
            device_metrics = packet['decoded'].get('deviceMetrics', {})
            battery_level = device_metrics.get('batteryLevel', None)
            voltage = device_metrics.get('voltage', None)
            channel_utilization = device_metrics.get('channelUtilization', None)
            air_util_tx = device_metrics.get('airUtilTx', None)
            uptime_seconds = device_metrics.get('uptimeSeconds', None)
            
            print(f"🕸️ Node info received from {from_short_name} ({fromId}): long_name={long_name}, short_name={short_name}, hw_model={hw_model}, snr={snr}, last_heard={last_heard}, battery_level={battery_level}, voltage={voltage}, channel_utilization={channel_utilization}, air_util_tx={air_util_tx}, uptime_seconds={uptime_seconds}")
            upsert_node(fromId, short_name, long_name, hw_model, last_heard)
        elif portnum == 'TRACEROUTE_APP':
            hops = packet['decoded'].get('hops', [])
            print(f"🧭 Traceroute data received from {from_short_name} ({fromId}) to {to_short_name} ({toId}): hops={hops}")
            store_traceroute(fromId, toId, hops, timestamp)
        elif portnum == 'ROUTING_APP':
            routes = packet['decoded'].get('routes', [])
            print(f"🚏 Routing data received from {from_short_name} ({fromId}) to {to_short_name} ({toId}): routes={routes}")
            store_routing(fromId, toId, str(routes), timestamp)
        else:
            print(f"🗞️ Non-text message or empty text received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {portnum}")
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
        
        print(f"📧 Encrypted message received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {encrypted_text}")
        store_message(message_id, fromId, toId, encrypted_text, timestamp, channel)
    else:
        print(f"🚨 Unknown message format: {packet}")

# Mark message as read
def mark_message_as_read(message_id):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('UPDATE messages SET read = 1 WHERE message_id = ?', (message_id,))
    conn.commit()
    conn.close()

# Get unread messages
def get_unread_messages():
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('SELECT * FROM messages WHERE read = 0')
    messages = c.fetchall()
    conn.close()
    return messages

def print_meshtastic_banner():
    banner = """
         ███   ███      ████████ ███████  ██     ███████████   ███      ███████ █████████   ███ ███████ 
       ████  ██████     ██       ███      ██     ██   ███     ██████    ███   ██    ██     ███ ███    ██
      ████  ███   ███   ███████   ███████ █████████   ███   ███   ███    ███████    ██   ████  ██       
    ████  ████     ███  ██             ██ ██     ██   ███  ███     ███  ██    ██    ██  ████   ███    ██
    ███   ██         ██ ████████ ████████ ██     ██   ███ ███        ██ ████████    ██ ███      ████████
    Save messages from Meshtastic to a SQLite database.
    """
    print(banner)
# Main function
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
            time_module.sleep(1)
    except KeyboardInterrupt:
        print("Stopping message listener...")

if __name__ == "__main__":
    print_meshtastic_banner()
    main()
