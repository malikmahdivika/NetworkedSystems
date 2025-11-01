from socket import *
import sys
serverName = input("Please enter server name: ")
serverPort = 7030
receivedMessage = ""

serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(("localhost", serverPort))
print(f"The server is initialized on port {serverPort}")
serverSocket.listen(1)
print("The server is ready to receive...")

while True:
    # accept connections
    connectionSocket, address = serverSocket.accept()
    print(f'Receiving connection from {address}...')

    # get data from client, and send server name to client
    clientName = connectionSocket.recv(1024).decode()
    connectionSocket.send(serverName.encode())

    while receivedMessage != "bye":
        # Client turn to send message, so receive first
        receivedMessage = connectionSocket.recv(1024).decode()
        print(f"Server received: {receivedMessage}")
        if (receivedMessage == "bye"):
            serverSocket.close()
            sys.exit("Server socket closed.")

        # server's turn to send message before looping back
        sentMessage = input(f"{serverName}'s (Server) message to send: ")
        if (sentMessage == "bye"): 
            connectionSocket.send(sentMessage.encode())
            serverSocket.close()
            sys.exit("Server socket closed.")
        else: 
            connectionSocket.send(sentMessage.encode())
    # close socket    
    serverSocket.close()
    print("Server socket closed.")
