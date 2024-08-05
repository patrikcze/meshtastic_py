import meshtastic
import meshtastic.serial_interface
from meshtastic import BROADCAST_ADDR
from meshtastic.protobuf import mesh_pb2, portnums_pb2
from pubsub import pub
import time as time_module
import datetime
from google.protobuf.json_format import MessageToDict

# Function to handle received messages
def on_receive(packet, interface):
    """Callback function to handle received messages."""
    timestamp = int(time_module.time())

    # Debug print statement to log the entire packet
    print(f"Received packet: {packet}")

    if 'decoded' in packet:
        portnum = packet['decoded'].get('portnum')
        text = packet['decoded'].get('text')
        fromId = packet.get('fromId')
        toId = packet.get('toId')
        channel = packet.get('channel', 0)  # Default to 0 if channel is not found

        # Check if the message is 'Ping'
        if text == 'Ping':
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Received 'Ping' from {fromId}. Sending 'pong' and trace route.")
            reply_text = f"[Automatic] 🏓 pong to {fromId} at {current_time}."
            send_message(interface, fromId, reply_text, channel, toId)
            send_trace_route(interface, fromId, hop_limit=5, channelIndex=channel)
        
        # Check if the message is 'Alive?'
        elif text == 'Alive?':
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reply_text = f"[Automatic] Yes I'm alive ⏱️ {current_time}."
            print(f"Received 'alive?' from {fromId}. Sending '{reply_text}'.")
            send_message(interface, fromId, reply_text, channel, toId)

# Function to send a message
def send_message(interface, fromId, text, channel, toId):
    """Function to send a message to a specific node or channel."""
    if toId == '^all':
        # Send to the same channel it was received from
        interface.sendText(text, destinationId=BROADCAST_ADDR, wantAck=True, channelIndex=channel)
    else:
        # Send directly to the sender
        interface.sendText(text, destinationId=fromId, wantAck=True)

def send_trace_route(interface, dest, hop_limit, channelIndex=0):
    """Send the trace route"""
    r = mesh_pb2.RouteDiscovery()
    # Set the hop limit if needed; assuming it needs to be set in the message
    # r.hopLimit = hop_limit  # Uncomment if RouteDiscovery has a hopLimit field
    
    interface.sendData(
        r,
        destinationId=dest,
        portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
        wantResponse=True,
        onResponse=on_response_trace_route,
        channelIndex=channelIndex,
        # hopLimit=hop_limit,  # Removed this argument since sendData doesn't accept it
    )

def on_response_trace_route(p):
    """on response for trace route"""
    routeDiscovery = mesh_pb2.RouteDiscovery()
    routeDiscovery.ParseFromString(p["decoded"]["payload"])
    asDict = MessageToDict(routeDiscovery)

    print("Route traced:")
    routeStr = f'{p["to"]:08x}'
    if "route" in asDict:
        for nodeNum in asDict["route"]:
            routeStr += " --> " + f"{nodeNum:08x}"
    routeStr += " --> " + f'{p["from"]:08x}'
    print(routeStr)

# Function to initialize Meshtastic and start listening for messages
def main():
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
    main()
