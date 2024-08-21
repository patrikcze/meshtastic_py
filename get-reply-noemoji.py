#!/usr/bin/env python3
import sys
import meshtastic
import meshtastic.stream_interface
import meshtastic.tcp_interface
import meshtastic.serial_interface
from meshtastic import BROADCAST_ADDR
from meshtastic.protobuf import mesh_pb2, portnums_pb2
from pubsub import pub
import time as time_module
import datetime
from google.protobuf.json_format import MessageToDict
import sqlite3
import logging
import serial.tools.list_ports
import codecs

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("meshtastic.log", encoding='utf-8'),
        logging.StreamHandler(codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict'))
    ]
)

# Enforcing UTF-8 encoding for Windows
# if sys.platform == "win32":
#     sys.stdout.reconfigure(encoding='utf-8', errors='replace')

logger = logging.getLogger(__name__)

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
                    user_id TEXT PRIMARY KEY,
                    node_number TEXT,
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
    c.execute('''CREATE TABLE IF NOT EXISTS neighbors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT,
                neighbor_node_id TEXT,
                snr REAL,
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
    logger.info("Database initialized successfully.")

# Connection setup function (REMOVED)
# def get_interface(interface_type='serial', port=None, hostname=None):
#     """
#     Opens and returns an instance of the meshtastic interface based on the provided configuration.

#     Args:
#         interface_type (str): Type of the interface ('serial' or 'tcp').
#         port (str): Serial port to connect to (for 'serial' interface).
#         hostname (str): Hostname for TCP connection (for 'tcp' interface).

#     Raises:
#         ValueError: For invalid or incomplete configurations.

#     Returns:
#         meshtastic.stream_interface.StreamInterface: Instance of StreamInterface.
#     """
#     while True:
#         try:
#             if interface_type == 'serial':
#                 if port:
#                     return meshtastic.serial_interface.SerialInterface(port)
#                 else:
#                     ports = list(serial.tools.list_ports.comports())
#                     if len(ports) == 1:
#                         return meshtastic.serial_interface.SerialInterface(ports[0].device)
#                     elif len(ports) > 1:
#                         port_list = ', '.join([p.device for p in ports])
#                         raise ValueError(f"Multiple serial ports detected: {port_list}. Specify one with the 'port' argument.")
#                     else:
#                         raise ValueError("No serial ports detected.")
#             elif interface_type == 'tcp':
#                 if not hostname:
#                     raise ValueError("Hostname must be specified for TCP interface")
#                 return meshtastic.tcp_interface.TCPInterface(hostname=hostname)
#             else:
#                 raise ValueError("Invalid interface type specified.")
#         except PermissionError as e:
#             logger.error(f"PermissionError: {e}. Retrying in 5 seconds...")
#             time_module.sleep(5)
#         except ValueError as e:
#             logger.error(f"ValueError: {e}.")
#             break  # Exit the loop on ValueError
#         except Exception as e:
#             logger.error(f"Unexpected error: {e}. Retrying in 5 seconds...")
#             time_module.sleep(5)


# Store functions (from the second script)
def store_message(message_id, sender, recipient, message, timestamp, channel):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO messages (message_id, sender, recipient, message, timestamp, channel) VALUES (?, ?, ?, ?, ?, ?)''', 
                  (message_id, sender, recipient, message, timestamp, channel))
        conn.commit()
    except sqlite3.IntegrityError:
        logger.warning(f"Duplicate message with ID {message_id} detected. Ignoring...")
    conn.close()

def store_telemetry(node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO telemetry (node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (node_id, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp))
    conn.commit()
    conn.close()
    logger.info(f"Stored telemetry data for node {node_id}.")

def store_position(node_id, latitude, longitude, altitude, time, sats_in_view, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO positions (node_id, latitude, longitude, altitude, time, sats_in_view, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (node_id, latitude, longitude, altitude, time, sats_in_view, timestamp))
    conn.commit()
    conn.close()
    logger.info(f"Stored position data for node {node_id}.")

def store_environment(node_id, temperature, relative_humidity, barometric_pressure, iaq, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO environment (node_id, temperature, humidity, bar, iaq, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (node_id, temperature, relative_humidity, barometric_pressure, iaq, timestamp))
    conn.commit()
    conn.close()
    logger.info(f"Stored environmental data for node {node_id}.")

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
    logger.info(f"Stored traceroute data from {from_node} to {to_node}.")

def store_routing(from_node, to_node, routes, timestamp):
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO routing (from_node, to_node, routes, timestamp)
                 VALUES (?, ?, ?, ?)''', 
              (from_node, to_node, routes, timestamp))
    conn.commit()
    conn.close()
    logger.info(f"Stored routing data from {from_node} to {to_node}.")

def upsert_node(user_id, node_number, short_name, long_name, hw_model, last_heard):
    if user_id is None:
        logger.warning(f"Skipping upsert for node with None user_id: {short_name}, {long_name}, {hw_model}, {last_heard}")
        return
    
    # Log the values being upserted
    logger.info(f"Upserting node: user_id={user_id}, node_number={node_number}, short_name={short_name}, long_name={long_name}, hw_model={hw_model}, last_heard={last_heard}")
    
    # Ensure node_number is not None or an empty string
    if node_number is None or node_number == '':
        logger.warning(f"Skipping upsert for node {user_id} because node_number is None or empty.")
        return
    
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO nodes (user_id, node_number, short_name, long_name, hw_model, last_heard)
                     VALUES (?, ?, ?, ?, ?, ?)
                     ON CONFLICT(user_id) DO UPDATE SET
                     node_number=excluded.node_number, short_name=excluded.short_name,
                     long_name=excluded.long_name, hw_model=excluded.hw_model,
                     last_heard=excluded.last_heard''',
                  (user_id, node_number, short_name, long_name, hw_model, last_heard))
        conn.commit()
    except Exception as e:
        logger.error(f"Error upserting node {user_id}: {e}")
    finally:
        conn.close()
    logger.info(f"Upserted node information for {short_name} ({user_id} #{node_number}).")

def store_neighbors(node_id, neighbor_node_id, snr, timestamp):
    """Store neighbor information in the database."""
    conn = sqlite3.connect('messages.db')
    c = conn.cursor()
    c.execute('''INSERT INTO neighbors (node_id, neighbor_node_id, snr, timestamp)
                 VALUES (?, ?, ?, ?)''',
              (node_id, neighbor_node_id, snr, timestamp))
    conn.commit()
    conn.close()
    logger.info(f"Stored neighbor information: {node_id} -> {neighbor_node_id} with SNR {snr}.")

# Function to send a message (from the first script)
def send_message(interface, fromId, text, channel, toId):
    """Function to send a message to a specific node or channel."""
    if toId == '^all':
        # Send to the same channel it was received from
        interface.sendText(text, destinationId=BROADCAST_ADDR, wantAck=True, channelIndex=channel)
    else:
        # Send directly to the sender
        interface.sendText(text, destinationId=fromId, wantAck=True)
    logger.info(f"Message sent from {fromId} to {toId} on channel {channel}: {text}")

def send_trace_route(interface, dest, hop_limit, channelIndex=0):
    """Send the trace route"""
    r = mesh_pb2.RouteDiscovery()
    # Set the hop limit if needed; assuming it needs to be set in the message
    
    interface.sendData(
        r,
        destinationId=dest,
        portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
        wantResponse=True,
        onResponse=on_response_trace_route,
        channelIndex=channelIndex,
    )
    logger.info(f"Trace route request sent to {dest} with hop limit {hop_limit}.")

def on_response_trace_route(p):
    """on response for trace route"""
    routeDiscovery = mesh_pb2.RouteDiscovery()
    routeDiscovery.ParseFromString(p["decoded"]["payload"])
    asDict = MessageToDict(routeDiscovery)

    routeStr = f'{p["to"]:08x}'
    if "route" in asDict:
        for nodeNum in asDict["route"]:
            routeStr += " --> " + f"{nodeNum:08x}"
    routeStr += " --> " + f'{p["from"]:08x}'
    logger.info(f"Route traced: {routeStr}")

# on_receive function (merged from both scripts)
def on_receive(packet, interface):
    """Callback function to handle received messages."""
    timestamp = int(time_module.time())

    # Initialize node_number variables to None
    from_node_number = None
    to_node_number = None

    if 'decoded' in packet:
        portnum = packet['decoded'].get('portnum')
        text = packet['decoded'].get('text')
        message_id = packet['id']  # Unique message ID
        fromId = packet.get('fromId')
        toId = packet.get('toId')
        from_node_number = packet.get('from', None)  # Node number from the packet, default to None
        to_node_number = packet.get('to', None)  # Destination Node number from the packet, default to None
        channel = packet.get('channel', 0)  # Default to 0 if channel is not found
        hop_limit = packet.get('hopLimit', 0)
        hop_start = packet.get('hopStart', 0)
        rx_time = packet.get('rxTime', 0)

        # Calculate hops away
        hops_away = hop_start - hop_limit

        # Convert rx_time to human-readable format
        rx_time_human = datetime.datetime.fromtimestamp(rx_time).strftime("%Y-%m-%d %H:%M:%S")

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

        # Upsert node information if available
        if from_node_number is not None:
            upsert_node(fromId, from_node_number, from_short_name, from_long_name, from_hw_model, from_last_heard)
        if to_node_number is not None:
            upsert_node(toId, to_node_number, to_short_name, to_long_name, to_hw_model, to_last_heard)

        # Handle different message types
        if portnum == 'TEXT_MESSAGE_APP' and text:
            logger.info(f"Plain text message received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {text}")
            store_message(message_id, fromId, toId, text, timestamp, channel)
        # Respond to specific messages
            if text == 'Ping':
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Received 'Ping' from {fromId}. Sending 'pong' and trace route.")
                reply_text = (
                    f"[Automatic Reply]\n Reply to {fromId} at {current_time}.\n"
                    f"Hops away: {hops_away}\n"
                    f"Receive time: {rx_time_human}"
                )
                try:
                    send_message(interface, fromId, reply_text, channel, toId)
                    send_trace_route(interface, fromId, hop_limit=3, channelIndex=channel)
                except Exception as e:
                    logger.error(f"Error while sending response or trace route: {e}")

            elif text == 'Alive?':
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                reply_text = f"[Automatic Reply] Yes I'm alive {current_time}."
                logger.info(f"Received 'Alive?' from {fromId}. Sending '{reply_text}'.")
                try:
                    send_message(interface, fromId, reply_text, channel, toId)
                except Exception as e:
                    logger.error(f"Error while sending 'Alive?' response: {e}")

        elif portnum == 'TELEMETRY_APP':
            telemetry = packet['decoded'].get('telemetry', {})
            battery_level = telemetry.get('deviceMetrics', {}).get('batteryLevel', None)
            voltage = telemetry.get('deviceMetrics', {}).get('voltage', None)
            channel_utilization = telemetry.get('deviceMetrics', {}).get('channelUtilization', None)
            air_util_tx = telemetry.get('deviceMetrics', {}).get('airUtilTx', None)
            uptime_seconds = telemetry.get('deviceMetrics', {}).get('uptimeSeconds', None)
            
            logger.info(f"Telemetry data received from {from_short_name} ({fromId}): battery_level={battery_level}, voltage={voltage}, channel_utilization={channel_utilization}, air_util_tx={air_util_tx}, uptime_seconds={uptime_seconds}")
            store_telemetry(fromId, battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds, timestamp)
            # Check if environmental data is present in telemetry
            environment_metrics = telemetry.get('environmentMetrics', {})
            if environment_metrics:
                temperature = environment_metrics.get('temperature', None)
                relative_humidity = environment_metrics.get('relativeHumidity', None)
                barometric_pressure = environment_metrics.get('barometricPressure', None)
                iaq = environment_metrics.get('iaq', None)  # Assuming IAQ (Indoor Air Quality) might be included

                logger.info(f"Environment data found in telemetry from {from_short_name} ({fromId}): temperature={temperature}, relative_humidity={relative_humidity}, barometric_pressure={barometric_pressure}, iaq={iaq}")
                store_environment(fromId, temperature, relative_humidity, barometric_pressure, iaq, timestamp)

        elif portnum == 'POSITION_APP':
            position = packet['decoded'].get('position', {})
            latitude = position.get('latitude', None)
            longitude = position.get('longitude', None)
            altitude = position.get('altitude', None)
            time = position.get('time', None)
            sats_in_view = position.get('satsInView', None)
            
            logger.info(f"Position data received from {from_short_name} ({fromId}): latitude={latitude}, longitude={longitude}, altitude={altitude}, time={time}, sats_in_view={sats_in_view}")
            store_position(fromId, latitude, longitude, altitude, time, sats_in_view, timestamp)

        elif portnum == 'ENVIRONMENTAL_MEASUREMENT_APP':
            environment = packet['decoded'].get('environment', {})
            temperature = environment.get('temperature', None)
            humidity = environment.get('humidity', None)
            bar = environment.get('bar', None)
            iaq = environment.get('iaq', None)

            logger.info(f"Environment data received from {from_short_name} ({fromId}): temperature={temperature}, humidity={humidity}, bar={bar}, iaq={iaq}")
            store_environment(fromId, temperature, humidity, bar, iaq, timestamp)

        elif portnum == 'NODEINFO_APP':
            node_info = packet['decoded'].get('user', {})
            number = node_info.get('from', None)
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
            
            logger.info(f"Node info received from {from_short_name} ({fromId}): long_name={long_name}, short_name={short_name}, hw_model={hw_model}, snr={snr}, last_heard={last_heard}, battery_level={battery_level}, voltage={voltage}, channel_utilization={channel_utilization}, air_util_tx={air_util_tx}, uptime_seconds={uptime_seconds}")
            upsert_node(fromId, number, short_name, long_name, hw_model, last_heard)

        elif portnum == 'TRACEROUTE_APP':
            hops = packet['decoded'].get('hops', [])
            logger.info(f"Traceroute data received from {from_short_name} ({fromId}) to {to_short_name} ({toId}): hops={hops}")
            store_traceroute(fromId, toId, hops, timestamp)

        elif portnum == 'ROUTING_APP':
            routes = packet['decoded'].get('routes', [])
            logger.info(f"Routing data received from {from_short_name} ({fromId}) to {to_short_name} ({toId}): routes={routes}")
            store_routing(fromId, toId, str(routes), timestamp)

        elif portnum == 'NEIGHBORINFO_APP':
            neighbor_info = packet['decoded'].get('neighborinfo', {})
            node_id = neighbor_info.get('nodeId')
            neighbors = neighbor_info.get('neighbors', [])

            # Store neighbor information and update the nodes table with neighbor_node_id
            for neighbor in neighbors:
                neighbor_node_number = neighbor.get('nodeId')
                snr = neighbor.get('snr')
                store_neighbors(node_id, neighbor_node_number, snr, timestamp)
                logger.info(f"Stored neighbor info: {node_id} has neighbor {neighbor_node_number} with SNR {snr}")

    elif 'encrypted' in packet:
        encrypted_text = packet.get('encrypted')
        message_id = packet['id']  # Unique message ID
        fromId = packet.get('fromId')
        toId = packet.get('toId')
        from_node_number = packet.get('from', None)  # Node number from the packet, default to None
        to_node_number = packet.get('to', None)  # Destination Node number from the packet, default to None
        channel = packet.get('channel', 0)  # Default to 0 if channel is not found

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
        
        if from_node_number is not None:
            upsert_node(fromId, from_node_number, from_short_name, from_long_name, from_hw_model, from_last_heard)
        if to_node_number is not None:
            upsert_node(toId, to_node_number, to_short_name, to_long_name, to_hw_model, to_last_heard)

        logger.info(f"Encrypted message received from {from_short_name} ({fromId}) to {to_short_name} ({toId}) on channel {channel}: {encrypted_text}")
        store_message(message_id, fromId, toId, encrypted_text, timestamp, channel)

    else:
        logger.error(f"Unknown message format: {packet}")

def print_meshtastic_banner():
    banner = """
         ███   ███      ████████ ███████  ██     ███████████   ███      ███████ █████████   ███ ███████
       ████  ██████     ██       ███      ██     ██   ███     ██████    ███   ██    ██     ███ ███    ██
      ████  ███   ███   ███████   ███████ █████████   ███   ███   ███    ███████    ██   ████  ██
    ████  ████     ███  ██             ██ ██     ██   ███  ███     ███  ██    ██    ██  ████   ███    ██
    ███   ██         ██ ████████ ████████ ██     ██   ███ ███        ██ ████████    ██ ███      ████████
    Save messages from Meshtastic to a SQLite database and Reply to Ping.
    """
    logger.info(banner)

# Main function
def main():
    # Initialize the database
    initialize_db()

       # Initialize the database
    initialize_db()
    # INFO: Using the serial interface for now NEED TO FIX
    # PROBLEMS REPORTED WITH CONNECTION!!!! RETURNING BACK TO SERIAL
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