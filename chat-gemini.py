import sys
import meshtastic
import meshtastic.serial_interface
import time
import requests

# Constants
GEMINI_API_URL = "https://api.gemini.ai/v1/chat"
API_KEY = "your_gemini_api_key_here"  # Replace with your API key
MAX_MESSAGE_LENGTH = 224

# Function to split long messages

def split_message(message, max_length):
    """Split a long message into chunks of a specified maximum length."""
    return [message[i:i + max_length] for i in range(0, len(message), max_length)]

# Function to send a message to Gemini AI

def send_to_gemini(prompt):
    """Send a prompt to Gemini AI and get the response."""
    try:
        response = requests.post(
            GEMINI_API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"prompt": prompt}
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.RequestException as e:
        print(f"Error communicating with Gemini AI: {e}")
        return "Sorry, I couldn't process your request."

# Function to send a message through Meshtastic

def send_message(interface, destination_id, text, channel):
    """Send a message to a specific node or broadcast."""
    interface.sendText(text, destinationId=destination_id, wantAck=True, channelIndex=channel)

# Callback function for received messages

def on_receive(packet, interface):
    """Handle incoming messages."""
    if 'decoded' in packet and packet['decoded'].get('portnum') == 'TEXT_MESSAGE_APP':
        text = packet['decoded'].get('text', "")
        from_id = packet.get('fromId', "Unknown")
        channel = packet.get('channel', 0)

        print(f"Message received from {from_id} on channel {channel}: {text}")

        # Send the text to Gemini AI and get the response
        response = send_to_gemini(text)

        # Split the response into smaller chunks if necessary
        response_chunks = split_message(response, MAX_MESSAGE_LENGTH)

        # Send each chunk as a separate message
        for chunk in response_chunks:
            send_message(interface, from_id, chunk, channel)

# Main function

def main():
    # Initialize the Meshtastic interface
    interface = meshtastic.serial_interface.SerialInterface()

    # Subscribe to incoming messages
    interface.subscribe(on_receive)

    print("Listening for messages... Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping message listener...")

if __name__ == "__main__":
    main()
