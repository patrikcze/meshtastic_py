import meshtastic
import meshtastic.serial_interface
from meshtastic import BROADCAST_ADDR
from pubsub import pub
import time as time_module
import datetime

# Function to handle received messages
def on_receive(packet, interface):
    """Callback function to handle received messages."""
    timestamp = int(time_module.time())

    # Debug print statement to log the entire packet
    # print(f"Received packet: {packet}")

    if 'decoded' in packet:
        portnum = packet['decoded'].get('portnum')
        text = packet['decoded'].get('text')
        fromId = packet.get('fromId')
        toId = packet.get('toId')
        channel = packet.get('channel', 0)  # Default to 0 if channel is not found

        # Check if the message is 'Ping'
        if text == 'Ping':
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Received 'Ping' from {fromId}. Sending 'pong'.")
            reply_text = f"[Automatic] 🏓 pong to {fromId} at {current_time}."
            send_message(interface, fromId, reply_text, channel, toId)
        
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
        print(f"Sent message to all nodes in channel {channel}.")
    else:
        # Send directly to the sender
        interface.sendText(text, destinationId=fromId, wantAck=True)
        print(f"Sent message to {fromId}.")

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
