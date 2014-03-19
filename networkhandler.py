from threading import Thread, Timer
import socket
from time import sleep
import struct
import select
import json
from models import Order, OrderQueue
from random import randint, choice
from Queue import Queue
from functools import partial
from channels import INPUT, OUTPUT
import time

class NetworkHandler(Thread):
	""" Handling all the network interaction. Receiving messages on its main thread, and spawns a listening thread"""
	def __init__(self):
		super(NetworkHandler, self).__init__()
		self.daemon = True
		self.networkReceiver = NetworkReceiver()
		self.networkSender = NetworkSender()	

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

	def __init__(self, callbackQueue=None):
		self.interrupt = False
		self.callbackQueue = callbackQueue
		self.addOrderCallback = None
		self.ip = self.get_ip()
		self.MCAST_GROUP = "224.1.1.1"
		self.MCAST_PORT = 5007
		self.elevators = {}
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GROUP), socket.INADDR_ANY)
		self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

	def get_ip(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(('google.com', 0))
		return s.getsockname()[0]


	def serve_forever(self):
		""" Binding to multicast and listening for messages nonblocking """
		self.sock.bind(('', self.MCAST_PORT))
		self.sock.setblocking(0)
		while not self.interrupt:
			r, _, _ = select.select([self.sock], [], [])
			if r:
				self.handle_message(r[0].recvfrom(1024))
		print "receiver stopped"
		self.sock.close()

	def determine_cost(self, order, value):
		direction = int(value['direction'])
		currentFloor = int(value['currentFloor'])
		orderQueue = OrderQueue.deserialize(value['orderQueue'])
		orderweight = 5
		floorweight = 1
		cost = 0
		if orderQueue.has_order_in_floor(direction=order.direction, floor=order.floor):
			return -1
		if not orderQueue.has_orders():
			return abs(currentFloor-order.floor)
		if direction == OUTPUT.MOTOR_UP:
			for floor in range(currentFloor+1, INPUT.NUM_FLOORS):
				if floor == order.floor and direction == order.direction and not orderQueue.has_order_in_floor(direction=OUTPUT.MOTOR_DOWN, floor=floor):
					cost+=floorweight
					break
				cost += floorweight + orderQueue.has_order_in_floor(direction=direction, floor=floor)*orderweight
			if floor != order.floor:
				cost -= floorweight
				for floor in range(floor, order.floor, -1):
					cost += floorweight +orderQueue.has_order_in_floor(direction=order.direction, floor=floor)*orderweight

		else:
			for floor in range(currentFloor-1, -1, -1):
				if floor == order.floor and direction == order.direction:
					cost+=floorweight
					break
				cost += floorweight + orderQueue.has_order_in_floor(direction=direction, floor=floor)*orderweight
			if floor != order.floor:
				cost -= floorweight
				for floor in range(floor, currentFloor):
					cost += floorweight + orderQueue.has_order_in_floor(direction=order.direction, floor=floor)*orderweight


		return cost

	def handle_new_elevator(self, message, ip):
		if ip not in self.elevators:
			print 'NEW ELEVATOR WITH IP %s DISCOVERED' % ip
		self.elevators[ip] = message
		
	def handle_timeouts(self):
		for ip, message in self.elevators.items():
			if 'timestamp' not in message:
				message['timestamp'] = time.time()
			timestamp = message['timestamp']
			if time.time() - timestamp > 1:
				del self.elevators[ip] # BROADCAST ORDERS
				print 'DELETED ELEVATOR WITH IP %s' % ip

	def handle_message(self, message):
		message, (ip, port) = message
		message = json.loads(message)
		self.handle_new_elevator(message, ip)
		self.handle_timeouts()
		self.elevators[ip] = message
		self.elevators[ip]['timestamp'] = time.time()
		newOrders = message['newOrders']
		for order in newOrders:
			order = Order.deserialize(order)
			scores = {}
			for ip, value in self.elevators.items():
				scores[ip] = self.determine_cost(order, value)
			best = min(scores, key=scores.get)
			if self.ip == best and scores[best] >= 0:
				self.callbackQueue.put(partial(self.addOrderCallback, order))
				print "%s is taking this order with cost %d" % (self.ip, scores[best])
		#print message



class NetworkSender(Thread):

	def __init__(self):
		super(NetworkSender, self).__init__()
		self.elevatorInfo = None
		self.newOrderQueue = None
		self.message = {'newOrders': []}
		self.MCAST_GROUP = "224.1.1.1"
		self.MCAST_PORT = 5007
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
		self.interrupt = False
		self.daemon = True

	def build_message(self):
		self.message['direction'] = self.elevatorInfo['direction']
		self.message['currentFloor'] = self.elevatorInfo['currentFloor']
		self.message['orderQueue'] = OrderQueue.serialize(self.elevatorInfo['orderQueue'])
		try:
			order = Order.serialize(self.newOrderQueue.get_nowait())
			self.message['newOrders'].append(order)
			Timer(1, self.remove_order, (order, )).start()
		except:
			pass
		return json.dumps(self.message)

	def remove_order(self, order):
		self.message['newOrders'].remove(order)

	def run(self):
		""" Sending status messages over the network """
		while not self.interrupt:
			sleep(0.1)
			try:
				self.sock.sendto(self.build_message(), (self.MCAST_GROUP, self.MCAST_PORT))
			except:
				print 'NO NETWORK, sleeping for 5 second'
				sleep(5)
		print "sender out of loop"

if __name__ == '__main__':
	a = NetworkHandler()
	a.start()
	queue = a.networkSender.newOrders
	while True:
		num = randint(0,10)
		if num > 7:
			direction = choice([0,1])
			floor = choice([0,1,2,3])
			order = Order(direction=direction, floor=floor)
			queue.put(order)
		sleep(1)



