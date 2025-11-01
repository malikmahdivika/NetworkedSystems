# UDPPingerClient.py
from socket import *
import time

# RTT array
rtts = []
num_lost = 0

# initialize client socket
clientSocket = socket(AF_INET, SOCK_DGRAM)
#clientSocket.connect(("localhost", 7038))
clientSocket.settimeout(1.0)    # set 1s timeout

# Pinger start
for seq in range(1, 11):
    try:
        time_sent = time.time()
        
        # format is Ping <sequence #> <time sent>
        message = f"Ping {seq} {time_sent}"

        clientSocket.sendto(message.encode(), ("localhost", 7038))     # send message to server
        print(f"Sent: {message}")
        
        # server reply (if any)
        servermessage, address = clientSocket.recvfrom(1024)
        time_rcvd = time.time()

        rtt = time_rcvd - time_sent
        rtts.append(rtt)
    except TimeoutError:
        print("Request timed out\n")
        num_lost += 1

# compute and print required stats
if rtts:
    min_rtt = min(rtts)
    max_rtt = max(rtts)
    avg_rtt = sum(rtts) / len(rtts)
else:
    min_rtt = max_rtt = avg_rtt = 0.0

loss_rate = (num_lost / 10) * 100

print("---- Ping statistics ----")
print(f"Packets: Sent = 10, Received = {10 - num_lost}, Lost = {num_lost} ({loss_rate:.0f}% loss)")
print(f"RTT (seconds): min = {min_rtt:.6f}, avg = {avg_rtt:.6f}, max = {max_rtt:.6f}")

clientSocket.close()