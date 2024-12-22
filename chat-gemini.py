import sys
import meshtastic
import meshtastic.serial_interface
import time
import meshtastic
from meshtastic import BROADCAST_ADDR
import meshtastic.stream_interface
import meshtastic.tcp_interface
import meshtastic.serial_interface
#from meshtastic.protobufs.config_pb2 import LoRaConfig
#from meshtastic.protobuf import mesh_pb2
from pubsub import pub
import time as time_module

import google.generativeai as genai
import logging
import unicodedata

# Set max message length in bytes
MAX_MESSAGE_BYTES = 200  # Reduced to 200 bytes
# MAX_MESSAGE_LENGTH is not actively used, we are limiting by bytes

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG for detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Configure Gemini AI
API_KEY = "YOUR_API_KEY"  # Replace with your actual API key
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

# Dictionary to store conversation history per user
# Key: fromId (string), Value: conversation object
conversations = {}

def split_message_utf8(message, max_bytes):
    """
    Splits a message into chunks that respect UTF-8 encoding and maximum byte size.

    Args:
        message: The message string to split.
        max_bytes: The maximum number of bytes allowed per chunk.

    Returns:
        A list of strings, where each string is a chunk of the original message.
    """
    chunks = []
    current_chunk_bytes = bytearray()

    for char in message:
        char_bytes = char.encode('utf-8')
        if len(current_chunk_bytes) + len(char_bytes) <= max_bytes:
            current_chunk_bytes.extend(char_bytes)
        else:
            chunks.append(current_chunk_bytes.decode('utf-8'))
            current_chunk_bytes = bytearray(char_bytes)

    if current_chunk_bytes:
        chunks.append(current_chunk_bytes.decode('utf-8'))

    return chunks

# Function to send a message to Gemini AI
def send_to_gemini(fromId, prompt):
    """Send a prompt to Gemini AI and get the response, maintaining conversation history."""
    global conversations

    # Get or create conversation for the user
    if fromId not in conversations:
        conversations[fromId] = model.start_chat(history=[])

    conversation = conversations[fromId]

    try:
        # Add context to the prompt
        context_prompt = f"You are a helpful assistant responding to messages on a limited bandwidth, low-power radio network (Meshtastic). Keep your responses concise and relevant.\n\n{prompt}"

        # Send prompt and get response
        conversation.send_message(context_prompt)
        response = conversation.last.text # Access the response text directly

        logger.info("Gemini AI response received.")
        return response
    except Exception as e:
        # Handle conversation errors, including exceeding safety thresholds
        if "response: ''" in str(e):
          logger.error(f"Error communicating with Gemini AI: Response was blocked. Likely due to exceeding safety thresholds. Clearing conversation history for {fromId}.")
          conversations[fromId] = model.start_chat(history=[]) # Reset conversation
          return "Sorry, I couldn't process your request due to safety restrictions. I've reset our conversation, please try asking something different."
        else:
          logger.error(f"Error communicating with Gemini AI: {e}")
          return "Sorry, I couldn't process your request."

# Function to send a message through Meshtastic
def send_message(interface, destination_id, text, channel, sequence_number=0, total_parts=1):
    """Send a message to a specific node or broadcast, including sequence information."""
    try:
        header = f"[{sequence_number+1}/{total_parts}] " if total_parts > 1 else ""
        if destination_id == BROADCAST_ADDR:
            # Send to broadcast address on the specified channel
            interface.sendText(header + text, destinationId=destination_id, wantAck=True, channelIndex=channel)
            logger.info(f"Message part {sequence_number+1}/{total_parts} sent to broadcast address on channel {channel}: {text}")
        else:
            # Send directly to the destination node
            interface.sendText(header + text, destinationId=destination_id, wantAck=True, channelIndex=channel)
            logger.info(f"Message part {sequence_number+1}/{total_parts} sent to {destination_id} on channel {channel}: {text}")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

# Callback function for received messages
def on_receive(packet, interface):
    """Callback function to handle received messages."""
    timestamp = int(time_module.time())

    if 'decoded' in packet:
        portnum = packet['decoded'].get('portnum')
        text = packet['decoded'].get('text')
        message_id = packet.get('id')  # Unique message ID
        from_node_number = packet.get('from', None)  # Node number from the packet
        fromId = packet.get('fromId')
        toId = packet.get('toId')
        channel = packet.get('channel', 0)  # Default to 0 if channel is not found

        if portnum == 'TEXT_MESSAGE_APP' and text:
            # Check if the message is a part of a multi-part message and ignore it for now
            if text.startswith("[") and "]" in text:
                logger.info(f"Ignoring multi-part message part for now: {text}")
                return

            logger.info(f"{timestamp} Plain text message Id: {message_id} received from {from_node_number} (nodeId: {fromId}) to {toId} on channel {channel}: {text}")

            # Send the text to Gemini AI and get the response
            try:
                response = send_to_gemini(fromId, text)
                logger.info(f"Received response from Gemini AI: {response}")
            except Exception as e:
                logger.error(f"Error communicating with Gemini AI: {e}")
                return

            # Split the response into UTF-8 byte-safe chunks
            response_chunks = split_message_utf8(response, MAX_MESSAGE_BYTES - 6) # Reserve space for header

            # Determine the destination for the response
            response_destination = fromId
            if toId == "^all" or toId == BROADCAST_ADDR:
              response_destination = BROADCAST_ADDR
            logger.info(f"Response will be sent to: {response_destination}")

            # Send each chunk as a separate message with sequence information
            total_parts = len(response_chunks)
            for i, chunk in enumerate(response_chunks):
                try:
                    send_message(interface, response_destination, chunk, channel, sequence_number=i, total_parts=total_parts)
                    logger.info(f"Sent response chunk {i+1}/{total_parts} to {response_destination}: {chunk}")
                    time.sleep(2)  # Increased delay for reliability
                except Exception as e:
                    logger.error(f"Error sending response chunk {i+1}: {e}")
    else:
        logger.warning("Packet does not contain a 'decoded' field or is not a TEXT_MESSAGE_APP.")

# Main function
def main():
    # Initialize the Meshtastic interface
    try:
        # Try Serial first, then TCP
        try:
            interface = meshtastic.serial_interface.SerialInterface()
            logger.info("Meshtastic interface initialized successfully (Serial).")
        except Exception as e:
            logger.warning(f"Failed to connect via Serial: {e}")
            logger.info("Attempting TCP connection...")
            interface = meshtastic.tcp_interface.TCPInterface(hostname="meshtastic.local") # Replace with your device address if needed
            logger.info("Meshtastic interface initialized successfully (TCP).")

    except Exception as e:
        logger.error(f"Failed to connect to Meshtastic device: {e}")
        sys.exit(1)

   # IMPORTANT: Subscribe to messages
    pub.subscribe(on_receive, "meshtastic.receive")
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