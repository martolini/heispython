from threading import Thread, Timer
import socket
from time import sleep
import struct
import select
import json
from models import Order, OrderQueue, ORDERDIR
from random import randint, choice
from Queue import Queue
from functools import partial
from channels import INPUT, OUTPUT
import time

class NetworkHandler(Thread):
	""" 
	Handling all the network interaction. Receiving messages on its main thread, and spawns a listening thread
	"""
	def __init__(self):
		super(NetworkHandler, self).__init__()
		self.daemon = True
		self.networkReceiver = NetworkReceiver()
		self.networkSender = NetworkSender()	

	def run(self):
		"""
		Spawns a senderthread and handling responses its main thread
		"""
		self.networkSender.start()
		self.networkReceiver.serve_forever()

class NetworkReceiver():

	def __init__(self, callbackQueue=None):
		"""
		Initializing the networkreciever
		"""
		self.callbackQueue = callbackQueue
		self.addOrderCallback = None
		self.setLightCallback = None
		self.globalOrders = {ORDERDIR.DOWN: [False] * INPUT.NUM_FLOORS, ORDERDIR.UP: [False] * INPUT.NUM_FLOORS}
		self.ip = self.get_ip()
		self.MCAST_GROUP = "224.1.1.1"
		self.MCAST_PORT = 5007
		self.elevators = {}
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GROUP), socket.INADDR_ANY)
		self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

	def get_ip(self):
		"""
		Getting the IP of the current elevator (hackish)
		@return ip
		"""
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(('google.com', 0))
		return s.getsockname()[0]


	def serve_forever(self):
		""" 
		Binding to multicast and listening for messages without blocking 
		"""
		self.sock.bind(('', self.MCAST_PORT))
		self.sock.setblocking(0)
		while True:
			r, _, _ = select.select([self.sock], [], [], 0.1)
			if r:
				self.handle_message(r[0].recvfrom(1024))
			else:
				self.handle_timeouts()
		print "receiver stopped"
		self.sock.close()

	def determine_cost(self, order, message):
		"""
		Determines the cost of an order based on the message from an elevator
		@input order, message
		@return cost
		"""
		direction = int(message['direction'])
		currentFloor = int(message['currentFloor'])
		orderQueue = OrderQueue.deserialize(message['orderQueue'])
		orderweight = 5
		floorweight = 1
		cost = 0
		if orderQueue.has_order_in_floor(direction=order.direction, floor=order.floor):
			return -1
		if not orderQueue.has_orders():
			return abs(currentFloor-order.floor)
		if direction == OUTPUT.MOTOR_UP:
			for floor in range(currentFloor+1, INPUT.NUM_FLOORS):
				if floor == order.floor and direction == order.direction and not orderQueue.has_order_in_floor(direction=ORDERDIR.DOWN, floor=floor):
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

	def handle_new_elevator(self, ip):
		"""
		Prints that a new elevator has joined the network
		@input ip
		"""
		if ip not in self.elevators and ip != self.ip:
			print 'NEW ELEVATOR WITH IP %s DISCOVERED' % ip
		
	def handle_timeouts(self):
		"""
		Handles when a elevator has timed out, disconnecting it and removing it from its list of elevators
		"""
		for ip, message in self.elevators.items():
			if 'timestamp' not in message:
				message['timestamp'] = time.time()
			timestamp = message['timestamp']
			if time.time() - timestamp > 1:
				self.distribute_dead_orders(ip)
				del self.elevators[ip] # BROADCAST ORDERS
				print 'DELETED ELEVATOR WITH IP %s' % ip


	def distribute_dead_orders(self, dead_ip):
		"""
		Distributes the external orders of the dead elevator
		@input dead_ip
		"""
		for order in OrderQueue.deserialize(self.elevators[dead_ip]['orderQueue']).yield_orders():
			ip, value = self.get_best_elevator_for_order(order, exclude=dead_ip)
			if ip == self.ip and value >= 0:
				self.callbackQueue.put(partial(self.addOrderCallback, order))
				print "%s is taking over %s order with cost %d" % (self.ip, dead_ip, value)



	def get_best_elevator_for_order(self, order, exclude=None):
		"""
		Determines the best elevator for a certain order
		@input order
		@input exclude (default None)
		@return (ip, cost) [(-1, -1) if no elevator fits]
		"""
		scores = {}
		for ip, message in self.elevators.items():
			if ip != exclude:
				scores[ip] = self.determine_cost(order, message)
		if scores:
			best = min(scores, key=scores.get)
			return best, scores[best]
		print "NO ELEVATORS CAN TAKE THIS ORDER"
		return -1, -1

	def handle_new_orders(self, ip):
		"""
		Handles new orders broadcasted from a certain ip
		@input ip
		"""
		newOrders = self.elevators[ip]['newOrders']
		for order in newOrders:
			order = Order.deserialize(order)
			ip, value = self.get_best_elevator_for_order(order)
			if self.ip == ip and value >= 0:
				self.callbackQueue.put(partial(self.addOrderCallback, order))
				print "%s is taking this order with cost %d" % (self.ip, value)

	def handle_global_orders(self):
		newGlobalOrders = {ORDERDIR.UP: [False]*INPUT.NUM_FLOORS, ORDERDIR.DOWN: [False]*INPUT.NUM_FLOORS}
		for ip, message in self.elevators.items():
			orderQueue = OrderQueue.deserialize(message['orderQueue'])
			for direction, floors in orderQueue.orders.items():
				if direction == ORDERDIR.IN:
					continue
				for floor in range(len(floors)):
					newGlobalOrders[direction][floor] |= floors[floor]
		for direction, floors in newGlobalOrders.items():
			for floor in range(len(floors)):
				if newGlobalOrders[direction][floor] != self.globalOrders[direction][floor]:
					self.callbackQueue.put(partial(self.setLightCallback, direction, floor, floors[floor]))
		self.globalOrders = newGlobalOrders



	def handle_message(self, message):
		"""
		Handles the message broadcasted
		@input message
		"""
		message, (ip, port) = message
		message = json.loads(message)
		self.handle_new_elevator(ip)
		self.elevators[ip] = message
		self.elevators[ip]['timestamp'] = time.time()
		self.handle_new_orders(ip)
		self.handle_global_orders()



class NetworkSender(Thread):

	def __init__(self):
		"""
		Initializing the networkSender
		"""
		super(NetworkSender, self).__init__()
		self.elevatorInfo = None
		self.newOrderQueue = None
		self.callbackQueue = None
		self.lostConnectionCallback = None
		self.message = {'newOrders': []}
		self.MCAST_GROUP = "224.1.1.1"
		self.MCAST_PORT = 5007
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
		self.interrupt = False
		self.daemon = True

	def build_message(self):
		"""
		Builds a JSONmessage based on the info about its elevator,
		starting a thread that removes the order in x seconds
		@return JSONmessage
		"""
		self.message['direction'] = self.elevatorInfo['direction']
		self.message['currentFloor'] = self.elevatorInfo['currentFloor']
		self.message['orderQueue'] = OrderQueue.serialize(self.elevatorInfo['orderQueue'])
		try:
			order = Order.serialize(self.newOrderQueue.get_nowait())
			self.message['newOrders'].append(order)
			Timer(1.5, self.remove_order, (order, )).start()
		except:
			pass
		return json.dumps(self.message)

	def remove_order(self, order):
		"""
		Removes a new order after broadcasting it for x seconds
		@input order
		"""
		self.message['newOrders'].remove(order)

	def run(self):
		""" 
		Constantly broadcasting information over the network
		if the connection breaks, it sends a message to the elevator and deleting orders. 
		"""
		while not True:
			sleep(0.1)
			try:
				self.sock.sendto(self.build_message(), (self.MCAST_GROUP, self.MCAST_PORT))
			except:
				print 'NO NETWORK, deleting orders and sleeping for 5 second'
				self.callbackQueue.put(self.lostConnectionCallback)
				while True:
					try:
						self.newOrderQueue.get_nowait()
					except:
						break

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



