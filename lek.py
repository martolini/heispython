from socket import *
import sys
from time import sleep
import select

HOST, PORT = "", 9999
MESSAGE = "I'M ALIVE"
# SOCK_DGRAM is the socket type to use for UDP sockets
sock = socket(AF_INET, SOCK_DGRAM)
sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
sock.setblocking(0)
sock.bind((HOST, PORT))

# As you can see, there is no connect() call; UDP has no connections.
# Instead, data is directly sent to the recipient via sendto().
elevators = []

while True:
	print "sending message"
	sock.sendto(MESSAGE, (HOST, PORT))
	while True:
		print "waiting for received"
		r, _, _ = select.select([sock], [], [])
		print "received!"
		if not r:
			break
		print sock.recvfrom(1024)
	sleep(0.2)