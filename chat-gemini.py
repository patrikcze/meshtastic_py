import sys
import meshtastic
import meshtastic.serial_interface
import time
import google.generativeai as genai
from pubsub import pub
import logging
from meshtastic import mesh_pb2

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Configure Gemini AI
API_KEY = "YOUR_API_KEY"  # Replace with your actual API key
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

MAX_MESSAGE_LENGTH = 224

# Function to split long messages
def split_message(message, max_length):
    """Split a long message into chunks of a specified maximum length."""
    return [message[i:i + max_length] for i in range(0, len(message), max_length)]

# Function to send a message to Gemini AI
def send_to_gemini(prompt):
    """Send a prompt to Gemini AI and get the response."""
    try:
        response = model.generate_content(prompt)
        logger.info("Gemini AI response received.")
        return response.text
    except Exception as e:
        logger.error(f"Error communicating with Gemini AI: {e}")
        return "Sorry, I couldn't process your request."

# Function to send a message through Meshtastic
def send_message(interface, destination_id, text, channel):
    """Send a message to a specific node or broadcast."""
    try:
        interface.sendText(text, destinationId=destination_id, wantAck=True, channelIndex=channel)
        logger.info(f"Message sent to {destination_id} on channel {channel}: {text}")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

# Callback function for received messages
def on_receive(packet, interface):
    """Handle incoming messages."""
    logger.debug(f"Raw packet received: {packet}")

    # Check if packet is encrypted
    if 'encrypted' in packet:
        logger.info("Encrypted packet received.")
        encrypted_payload = packet.get('encrypted')
        try:
            # Attempt to decrypt
            decrypted = interface.localNode.decryptMessage(mesh_pb2.Data(payload=encrypted_payload))
            text = decrypted.get('text', "")
            logger.info(f"Decrypted text: {text}")
        except Exception as e:
            logger.error(f"Failed to decrypt message: {e}")
            return
    elif 'decoded' in packet:
        portnum = packet['decoded'].get('portnum')
        text = packet['decoded'].get('text', "")
        logger.debug(f"Decoded portnum: {portnum}, text: {text}")
        if portnum == mesh_pb2.PortNum.TEXT_MESSAGE_APP:
            logger.info(f"Plain text message received: {text}")
        else:
            logger.warning(f"Unexpected portnum: {portnum}")
    else:
        logger.warning("No recognized message format in packet.")
        return

    from_id = packet.get('fromId', "Unknown")
    channel = packet.get('channel', 0)

    logger.info(f"Message received from {from_id} on channel {channel}: {text}")

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
    try:
        interface = meshtastic.serial_interface.SerialInterface()
        logger.info("Meshtastic interface initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to Meshtastic device: {e}")
        sys.exit(1)

    # Subscribe to incoming messages
    pub.subscribe(lambda packet: on_receive(packet, interface), "meshtastic.receive")
    logger.info("Subscribed to Meshtastic messages.")

    # Display device information
    if interface.nodes:
        for node in interface.nodes.values():
            if node.get("num") == interface.myInfo.my_node_num:
                logger.info(f"Connected to device: {node['user']['shortName']} ({node['num']})")

    # Display LoRa configuration if available
    lora_config = getattr(interface.localNode.localConfig, 'lora', None)
    if lora_config:
        modem_preset = getattr(lora_config, 'modem_preset', "Unknown")
        region = getattr(lora_config, 'region', "Unknown")
        logger.info(f"LoRa Config - Modem Preset: {modem_preset}, Region: {region}")
    else:
        logger.warning("No LoRa configuration found.")

    logger.info("Listening for messages... Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping message listener...")
    finally:
        interface.close()
        logger.info("Meshtastic interface closed.")

if __name__ == "__main__":
    main()
