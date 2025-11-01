#import socket module
import os
from socket import *

serverSocket = socket(AF_INET, SOCK_STREAM)
#Prepare a sever socket
#Fill in start
serverPort = 7030
serverSocket.bind(("localhost", serverPort))
serverSocket.listen(1)
#Fill in end
# print("Current working directory:", os.getcwd())
while True:
    #Establish the connection
    print('Ready to serve...')
    connectionSocket, addr =  serverSocket.accept() #Fill in start #Fill in end
    try:
        message =  connectionSocket.recv(1024).decode() #Fill in start #Fill in end
        filename = message.split()[1]
        print("Requested file:", filename[1:])
        f = open(filename[1:])

        outputdata = f.read() # Fill in start # Fill in end

        #Send one HTTP header line into socket
        #Fill in start
        header = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
        connectionSocket.send(header.encode())
        #Fill in end
        #Send the content of the requested file to the client
        for i in range(0, len(outputdata)):
            connectionSocket.send(outputdata[i].encode())
        connectionSocket.send("\r\n".encode())
        connectionSocket.close()
    except IOError as e:
        #Send response message for file not found
        # Fill in start
        print("IOError: ", e)
        print("Error finding file:", filename[1:])
        header = "HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n"
        body = "<html><body><h1>404 Not Found</h1></body></html>"
        connectionSocket.send(header.encode())
        connectionSocket.send(body.encode())
        # Fill in end

        #Close client socket
        # Fill in start
        connectionSocket.close()
        # Fill in end

serverSocket.close()

