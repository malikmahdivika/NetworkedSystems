import argparse
import SWRDT
import time

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Quotation sender talking to a receiver."
    )
    parser.add_argument("receiver", help="receiver.")
    parser.add_argument("port", help="Port.", type=int)
    args = parser.parse_args()

    msg_L = [
        "sending message - 1",
        "sending message - 2",
        "sending message - 3",
        "sending message - 4",
        "sending message - 5",
        "sending message - 6",
        "sending message - 7",
        "sending message - 8",
        "sending message - 9",
        "sending message - 10",
    ]

    timeout = 2  # Receiver echo timeout (not transport-layer timeout)

    swrdt = SWRDT.SWRDT("sender", args.receiver, args.port)

    for message in msg_L:
        # Application-layer print (transport prints happen inside SWRDT)
        print("Sent Message: " + message)

        # Send via stop-and-wait protocol
        swrdt.swrdt_send(message)

        # Now attempt to receive echo back from Receiver.py
        reply = None
        start_wait = time.time()

        while reply is None and (time.time() - start_wait < timeout):
            reply = swrdt.swrdt_receive()
            if reply is None:
                time.sleep(0.05)

        if reply:
            print("Received Message: " + reply + "\n")
        else:
            print("NO ECHO RECEIVED (receiver timeout)\n")

    # Send shutdown signal to receiver
    swrdt.swrdt_send("END")
    swrdt.disconnect()
