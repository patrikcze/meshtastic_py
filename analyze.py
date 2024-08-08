import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import time as time_module
import sqlite3

# Initialize the database
def initialize_db():
    conn = sqlite3.connect('traffic_analysis.db')
    c = conn.cursor()
    # Create necessary tables
    c.execute('''CREATE TABLE IF NOT EXISTS packets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    packet_id INTEGER UNIQUE,
                    from_node TEXT,
                    to_node TEXT,
                    portnum TEXT,
                    message TEXT,
                    timestamp INTEGER,
                    anomaly_detected INTEGER DEFAULT 0,
                    rx_time INTEGER,
                    rx_snr REAL,
                    rx_rssi REAL,
                    hop_start INTEGER,
                    packet_blob BLOB
                )''')
    conn.commit()
    conn.close()

# Store packet data
def store_packet(packet_id, from_node, to_node, portnum, message, timestamp, anomaly_detected, rx_time, rx_snr, rx_rssi, hop_start, packet_blob):
    conn = sqlite3.connect('traffic_analysis.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO packets (packet_id, from_node, to_node, portnum, message, timestamp, anomaly_detected, rx_time, rx_snr, rx_rssi, hop_start, packet_blob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                  (packet_id, from_node, to_node, portnum, message, timestamp, anomaly_detected, rx_time, rx_snr, rx_rssi, hop_start, packet_blob))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"Duplicate packet with ID {packet_id} detected. Ignoring...")
    conn.close()

# Analyze packet
def analyze_packet(packet):
    # Basic anomaly detection logic
    if 'decoded' in packet:
        portnum = packet['decoded'].get('portnum')
        text = packet['decoded'].get('text', '')
        
        if portnum not in ['TEXT_MESSAGE_APP', 'TELEMETRY_APP', 'POSITION_APP', 'ENVIRONMENTAL_MEASUREMENT_APP', 'NODEINFO_APP', 'TRACEROUTE_APP', 'ROUTING_APP']:
            return True  # Unrecognized portnum indicates potential anomaly
        
        if any(word in text.lower() for word in ['attack', 'shutdown', 'disrupt']):
            return True  # Detect suspicious keywords in text messages
    
    return False

# on_receive function
def on_receive(packet, interface):
    """Callback function to handle received messages."""
    timestamp = int(time_module.time())
    packet_id = packet['id']  # Unique packet ID
    from_node = packet.get('fromId')
    to_node = packet.get('toId')
    portnum = packet.get('decoded', {}).get('portnum', 'UNKNOWN')
    message = packet.get('decoded', {}).get('text', '')
    rx_time = packet.get('rxTime')
    rx_snr = packet.get('rxSnr')
    rx_rssi = packet.get('rxRssi')
    hop_start = packet.get('hopStart')
    packet_blob = sqlite3.Binary(str(packet).encode('utf-8'))  # Store the entire packet as binary

    # Analyze the packet for anomalies
    anomaly_detected = analyze_packet(packet)

    if anomaly_detected:
        print(f"⚠️ Anomaly detected in packet from {from_node} to {to_node} on port {portnum}: {message}")

    store_packet(packet_id, from_node, to_node, portnum, message, timestamp, anomaly_detected, rx_time, rx_snr, rx_rssi, hop_start, packet_blob)

def print_meshtastic_banner():
    banner = """
         ███   ███      ████████ ███████  ██     ███████████   ███      ███████ █████████   ███ ███████ 
       ████  ██████     ██       ███      ██     ██   ███     ██████    ███   ██    ██     ███ ███    ██
      ████  ███   ███   ███████   ███████ █████████   ███   ███   ███    ███████    ██   ████  ██       
    ████  ████     ███  ██             ██ ██     ██   ███  ███     ███  ██    ██    ██  ████   ███    ██
    ███   ██         ██ ████████ ████████ ██     ██   ███ ███        ██ ████████    ██ ███      ████████
    Analyze and log traffic from Meshtastic to a SQLite database.
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
