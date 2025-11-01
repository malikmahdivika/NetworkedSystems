from socket import *
import sys
clientName = input("Please enter client name: ")
serverPort = 7030
messageReceived = ""

clientSocket = socket(AF_INET, SOCK_STREAM)
print("Client socket created.")
clientSocket.connect(("localhost", serverPort))
print(f"Connected to server on {serverPort}!")

# send name
clientSocket.send(clientName.encode())
print("Sent client name to server.")
# receive server name
serverName = clientSocket.recv(2048).decode()
print("Received server name!")

while messageReceived != "bye":
    messageSent = input(f"{clientName}'s (Client) message to send: ")
    if (messageSent == "bye"): 
        clientSocket.send(messageSent.encode())
        clientSocket.close()
        sys.exit("Client socket closed.")
    else: 
        clientSocket.send(messageSent.encode())
    # now wait for message receive before looping back
    messageReceived = clientSocket.recv(2048).decode()
    print(f"Client received:  {messageReceived}")

clientSocket.close()
print("Client socket closed.")