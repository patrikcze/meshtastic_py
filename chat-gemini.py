import sys
import time
import logging
import unicodedata
import google.generativeai as genai

import meshtastic
from meshtastic import BROADCAST_ADDR
from meshtastic.stream_interface import StreamInterface
from meshtastic.tcp_interface import TCPInterface
from meshtastic.serial_interface import SerialInterface
from pubsub import pub

# -------------- Constants & Configuration --------------

API_KEY = "YOURAPIKEY"  # Replace with your actual API key
MAX_MESSAGE_BYTES = 200  # Maximum bytes for a single chunk (consider overhead)
REPLY_DELAY = 2         # Seconds to wait between sending multi-chunk replies

# Configure Gemini AI
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Store conversation history per user
# Key: fromId (string), Value: conversation object
conversations = {}

# -------------- Helper Functions --------------

def split_message_utf8(message, max_bytes):
    """
    Splits a message into chunks that respect UTF-8 encoding and maximum byte size.
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


def send_to_gemini(from_id, prompt):
    """
    Send a prompt to Gemini AI and get the response, maintaining conversation history.
    """
    global conversations

    # Retrieve or start conversation for this user
    if from_id not in conversations:
        conversations[from_id] = model.start_chat(history=[])

    conversation = conversations[from_id]

    try:
        # Provide context to the prompt
        context_prompt = (
            "You are a helpful assistant responding to messages on a limited bandwidth, "
            "low-power radio network (Meshtastic). Keep your responses concise and relevant. "
            "Speak Czech language. You are located in Brno, Czech Republic.\n\n" + prompt
        )

        # Send prompt
        conversation.send_message(context_prompt)

        # Get the response text
        response = conversation.last.text
        logger.info("Gemini AI response received.")
        return response

    except Exception as e:
        # Handle safety blocks or other exceptions
        if "response: ''" in str(e):
            logger.error(
                f"Error communicating with Gemini AI for user {from_id}: "
                "Response was blocked (likely safety threshold). Resetting conversation."
            )
            conversations[from_id] = model.start_chat(history=[])  # reset
            return ("Sorry, I couldn't process your request due to safety restrictions. "
                    "I've reset our conversation; please try asking something different.")
        else:
            logger.error(f"Error communicating with Gemini AI for user {from_id}: {e}")
            return "Sorry, I couldn't process your request."


def send_message(interface, destination_id, text, channel_index,
                 sequence_number=0, total_parts=1):
    """
    Send a message chunk to a destination ID on the specified channel.
    """
    try:
        header = f"[{sequence_number + 1}/{total_parts}] " if total_parts > 1 else ""
        interface.sendText(
            header + text,
            destinationId=destination_id,
            wantAck=True,
            channelIndex=channel_index
        )
        logger.info(
            f"Message part {sequence_number + 1}/{total_parts} sent to {destination_id} "
            f"on channel {channel_index}: {text}"
        )
    except Exception as e:
        logger.error(f"Failed to send message chunk {sequence_number + 1}: {e}")


# -------------- Callback for Received Packets --------------

def on_receive(packet, interface):
    """
    Callback function to handle incoming Meshtastic messages.
    """
    timestamp = int(time.time())

    if 'decoded' in packet:
        portnum = packet['decoded'].get('portnum')
        text = packet['decoded'].get('text')
        message_id = packet.get('id')
        from_node_number = packet.get('from', None)
        from_id = packet.get('fromId')
        to_id = packet.get('toId')
        channel = packet.get('channel')  # If missing, might be None

        if portnum == 'TEXT_MESSAGE_APP' and text:
            # ----------------------------------
            # 1) Decide channelIndex fallback
            # ----------------------------------
            if channel is None:
                # If it is a direct message (not ^all or BROADCAST_ADDR), assume channel 0
                if to_id not in ("^all", BROADCAST_ADDR):
                    channel = 0
                    logger.info(
                        f"No channel index provided for direct message from {from_id}. "
                        "Using channel 0 as fallback."
                    )
                else:
                    # If broadcast, do not respond
                    logger.warning(
                        f"Channel index missing for broadcast message from {from_id}; "
                        "refusing to respond."
                    )
                    return

            # If text looks like a multi-part piece, ignore
            if text.startswith("[") and "]" in text:
                logger.info(f"Ignoring multi-part message part: {text}")
                return

            logger.info(
                f"{timestamp} Plain text message Id: {message_id} "
                f"from {from_node_number} (nodeId: {from_id}) to {to_id} "
                f"on channel {channel}: {text}"
            )

            # Get Gemini AI response
            try:
                response = send_to_gemini(from_id, text)
            except Exception as e:
                logger.error(f"Error sending to Gemini: {e}")
                return

            # Break response into chunks
            response_chunks = split_message_utf8(response, MAX_MESSAGE_BYTES - 6)

            # Decide destination
            response_destination = from_id
            if to_id in ("^all", BROADCAST_ADDR):
                response_destination = BROADCAST_ADDR

            logger.info(f"Response will be sent to: {response_destination}")

            # Send each chunk with a delay
            total_parts = len(response_chunks)
            for i, chunk in enumerate(response_chunks):
                send_message(
                    interface=interface,
                    destination_id=response_destination,
                    text=chunk,
                    channel_index=channel,
                    sequence_number=i,
                    total_parts=total_parts
                )
                time.sleep(REPLY_DELAY)
    else:
        logger.warning("Packet missing 'decoded' field or is not 'TEXT_MESSAGE_APP'.")

# -------------- Main Entrypoint --------------

def main():
    # Attempt Serial interface first, then TCP
    try:
        try:
            interface = SerialInterface()
            logger.info("Meshtastic interface initialized successfully (Serial).")
        except Exception as e:
            logger.warning(f"Failed to connect via Serial: {e}")
            logger.info("Attempting TCP connection...")
            interface = TCPInterface(hostname="meshtastic.local")
            logger.info("Meshtastic interface initialized successfully (TCP).")
    except Exception as e:
        logger.error(f"Failed to connect to Meshtastic device: {e}")
        sys.exit(1)

    # Subscribe to incoming messages
    pub.subscribe(on_receive, "meshtastic.receive")
    logger.info("Subscribed to Meshtastic messages.")

    # Identify this node
    if interface.nodes:
        for node in interface.nodes.values():
            if node.get("num") == interface.myInfo.my_node_num:
                logger.info(f"Connected to device: {node['user']['shortName']} ({node['num']})")

    # Display LoRa config if available
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
            time.sleep(1)  # Keep the main thread alive
    except KeyboardInterrupt:
        logger.info("Stopping message listener...")
    finally:
        interface.close()
        logger.info("Meshtastic interface closed.")


if __name__ == "__main__":
    main()
