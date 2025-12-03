import argparse
import SWRDT
import time

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWRDT Receiver.")
    parser.add_argument("port", help="Port.", type=int)
    args = parser.parse_args()

    timeout = 10  # close connection if no new data within 10 seconds
    time_of_last_data = time.time()

    # Receiver mode
    swrdt = SWRDT.SWRDT("receiver", None, args.port)

    last_echoed = None
    while True:
        # Try to receive message before timeout
        msg_S = swrdt.swrdt_receive()

        if msg_S is None:
            # If no message after timeout -> terminate
            if time.time() - time_of_last_data > timeout:
                break
            time.sleep(0.05)  # reduce CPU usage
            continue

        # Check for shutdown signal
        if msg_S == "END":
            print("Shutdown signal received. Exiting.")
            break

        # Message received successfully
        time_of_last_data = time.time()

        # Only echo if this is a new message
        if msg_S != last_echoed:
            print(f"Reply: {msg_S}\n")
            swrdt.swrdt_send(msg_S)
            last_echoed = msg_S
        else:
            print(f"Duplicate message ignored at application layer: {msg_S}\n")

    swrdt.disconnect()
