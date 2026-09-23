import socket
import sys

SERVER_HOST = sys.argv[1]
SERVER_PORT = 42701

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((SERVER_HOST, SERVER_PORT))

command = input("Enter command: ")

client_socket.sendall((command + "\n").encode())

response = client_socket.recv(1024).decode()

print(response)

client_socket.close()