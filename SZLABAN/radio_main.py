from radio_handle import *

## Example usage of the RadioHandler class

# Some defines
# To fully customize the radio settings, you can change the values in radio_defines.py
RADIO_MODE = RadioMode.FSK # Set the radio modulation: RadioMode.LORA or RadioMode.FSK
SEND_DELAY = 5  # Delay [s] between sending messages
SEND_MSG = "Hello!"  # Message to send
SEND_MESSAGES = False  # Set to False to only receive messages




# Callback function to handle received data.
# This function will be called every time data is received.
def data_callback(data, rssi=None, index=None):
    print(f"Received data: {data}")

# Initialize the RadioHandler with mode of choice and the data callback.
# The RadioHandler will start receiving data in a separate thread. 
radio_handler = RadioHandler(RADIO_MODE, data_callback)


if SEND_MESSAGES:
    # Function to send messages every 10 seconds
    def send_messages():
        while True:
            radio_handler.send(SEND_MSG)
            sleep(SEND_DELAY)  # Add a delay to avoid spamming messages

    # Start the send_messages function in a separate thread
    send_thread = Thread(target=send_messages)
    # Set the thread as a daemon so it will shut down on program exit
    send_thread.daemon = True  

    # Start the send thread. It will send messages every 10 seconds. After every send operation, the radio handler will go back to receiving mode.
    send_thread.start()

try:
    while True:
        pass
except KeyboardInterrupt:
    print("Reception stopped.")
finally:
    radio_handler.cleanup()  # Clean up GPIO and close SPI