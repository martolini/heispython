from threading import Thread
import socket
from time import sleep
import struct
import select

class NetworkHandler(Thread):
	""" Handling all the network interaction. Receiving messages on its main thread, and spawns a listening thread"""

	def __init__(self):
		super(NetworkHandler, self).__init__()
		self.daemon = True
		self.networkReceiver = NetworkReceiver()
		self.networkSender = NetworkSender()
	
	def test(self):
		print "test"	

	def run(self):
		""" Spawning a senderthread and starting to server on its main thread"""
		self.networkSender.start()
		self.networkReceiver.serve_forever()

	def stop(self):
		""" Sending interrupt signals and joins subthread"""
		self.networkSender.interrupt = True
		self.networkReceiver.interrupt = True
		print "Sending interrupt"
		self.networkSender.join()

class NetworkReceiver():

	def __init__(self):
		self.interrupt = False
		self.MCAST_GROUP = "224.1.1.1"
		self.MCAST_PORT = 5007
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GROUP), socket.INADDR_ANY)
		self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)



	def serve_forever(self):
		""" Binding to multicast and listening for messages nonblocking """
		self.sock.bind(('', self.MCAST_PORT))
		self.sock.setblocking(0)
		while not self.interrupt:
			r, _, _ = select.select([self.sock], [], [], 1)
			if r:
				self.handle_message(r[0].recvfrom(1024))
		print "receiver stopped"
		self.sock.close()

	def handle_message(self, message):
		message, (ip, port) = message
		print message, (ip, port)
		

class NetworkSender(Thread):

	def __init__(self):
		super(NetworkSender, self).__init__()
		self.MCAST_GROUP = "224.1.1.1"
		self.MCAST_PORT = 5007
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
		self.interrupt = False
		self.daemon = True

	def run(self):
		""" Sending status messages over the network """
		while not self.interrupt:
			self.sock.sendto("IM ALIVE", (self.MCAST_GROUP, self.MCAST_PORT))
			sleep(0.5)
		print "sender out of loop"

if __name__ == '__main__':
	a = NetworkHandler()
	a.start()
	while True:
		pass


