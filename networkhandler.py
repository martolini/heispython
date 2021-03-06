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
import config

class NetworkHandler(Thread):
	""" 
	Handling all the network interaction. Receiving messages on its main thread, and spawns a listening thread
	"""
	def __init__(self, callbackQueue, addOrderCallback, setLightCallback, newOrderQueue, startedOrderQueue, lostConnectionCallback, elevatorInfo=None):
		super(NetworkHandler, self).__init__()
		self.daemon = True
		self.networkReceiver = NetworkReceiver(
			callbackQueue,
			addOrderCallback,
			setLightCallback
			)

		self.networkSender = NetworkSender(
			elevatorInfo, 
			newOrderQueue, 
			callbackQueue,
			startedOrderQueue, 
			lostConnectionCallback
			)	

	def run(self):
		"""
		Spawns a senderthread and handling responses on its main thread
		"""
		self.networkSender.start()
		self.networkReceiver.serve_forever()

class NetworkReceiver():

	def __init__(self, callbackQueue, addOrderCallback, setLightCallback):
		"""
		Initializing the networkreciever
		"""
		self.callbackQueue = callbackQueue
		self.addOrderCallback = addOrderCallback
		self.setLightCallback = setLightCallback
		self.globalOrders = {ORDERDIR.DOWN: [False] * config.NUM_FLOORS, ORDERDIR.UP: [False] * config.NUM_FLOORS}
		self.ip = self.get_ip()
		self.elevators = {}
		self.startedOrders = {}
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		mreq = struct.pack("4sl", socket.inet_aton(config.MCAST_GROUP), socket.INADDR_ANY)
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
		self.sock.bind(('', config.MCAST_PORT))
		self.sock.setblocking(0)
		while True:
			r, _, _ = select.select([self.sock], [], [], 0.1)
			if r:
				self.handle_message(r[0].recvfrom(1024))
			self.handle_timeouts()
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
		orderweight = config.ORDER_WEIGHT
		floorweight = config.FLOOR_WEIGHT
		directionweight = config.DIRECTION_WEIGHT
		cost = 0
		if orderQueue.has_order_in_floor_and_direction(order.direction, order.floor):
			return -1
		floors = (currentFloor, order.floor)
		for _order in orderQueue.yield_orders(exclude=(None,)):
			if min(currentFloor, _order.floor) <= order.floor <= max(currentFloor, _order.floor):
				if order.direction != _order.direction:
					cost += directionweight
			cost += orderweight
		return cost+abs(floors[0]-floors[1])*floorweight

	def handle_new_elevator(self, ip):
		"""
		Prints that a new elevator has joined the network
		@input ip
		"""
		if ip not in self.elevators and ip != self.ip:
			self.startedOrders[ip] = []
			print 'NEW ELEVATOR WITH IP %s DISCOVERED' % ip
		
	def handle_timeouts(self):
		"""
		Handles when a elevator has timed out, disconnecting it and removing it from its list of elevators
		"""
		for ip, message in self.elevators.items():
			if 'timestamp' not in message:
				message['timestamp'] = time.time()
			timestamp = message['timestamp']
			if time.time() - timestamp > config.TIMEOUT_LIMIT:
				self.distribute_dead_orders(ip)
				del self.elevators[ip] # BROADCAST ORDERS
				if ip != self.ip:
					del self.startedOrders[ip]
				print 'DELETED ELEVATOR WITH IP %s' % ip


	def distribute_dead_orders(self, dead_ip):
		"""
		Distributes the external orders of the dead elevator
		@input dead_ip
		"""
		for order in OrderQueue.deserialize(self.elevators[dead_ip]['orderQueue']).yield_orders():
			ip, value = self.get_best_elevator_for_order(order, exclude=dead_ip)
			if value >= 0:
				self.distribute_order(ip, order)



	def get_best_elevator_for_order(self, order, exclude=None):
		"""
		Determines the best elevator for a certain order
		@input order
		@input exclude (default None)
		@return (ip, cost) [(-1, -1) if no elevator fits (none is alive)]
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

	def check_if_order_started(self, ip, order):
		"""
		A separate threads runs this to check whether the order is started. If not, it finds a new elevator to handle it.
		@input ip, order
		"""
		if ip in self.startedOrders:
			if order.serialize() in self.startedOrders[ip]:
				self.distribute_order(ip, order)

	def distribute_order(self, ip, order):
		"""
		If the best ip is itself, it calls the main thread. If not, it adds it to startedOrders and check if it's done.
		@input ip, order
		"""
		if self.ip == ip:
			self.callbackQueue.put(partial(self.addOrderCallback, order))
		else:
			self.startedOrders[ip].append(order.serialize())
			Timer(1/config.HEARTBEAT_FREQUENCY*config.BROADCAST_HEARTBEATS, self.check_if_order_started, (ip, order)).start()



	def handle_new_orders(self, ip):
		"""
		Handles new orders broadcasted from a certain ip
		@input ip
		"""
		newOrders = self.elevators[ip]['newOrders']
		for order in newOrders:
			order = Order.deserialize(order)
			best_ip, value = self.get_best_elevator_for_order(order)
			if value >= 0:
				self.distribute_order(best_ip, order)

	def handle_global_orders(self):
		"""
		Updates self.globalOrders to keep track of all the elevators in the whole system and settings lights accordingly.
		"""
		newGlobalOrders = {ORDERDIR.UP: [False]*config.NUM_FLOORS, ORDERDIR.DOWN: [False]*config.NUM_FLOORS}
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

	def handle_started_orders(self, ip, message):
		"""
		Removes the started order if the assigned elevator started the job.
		@input ip, message
		"""
		if ip == self.ip:
			return
		startedOrders = message['startedOrders']
		for order in startedOrders:
			if order in self.startedOrders[ip]:
				self.startedOrders[ip].remove(order)

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
		self.handle_started_orders(ip, message)
		self.handle_new_orders(ip)
		self.handle_global_orders()



class NetworkSender(Thread):

	def __init__(self, elevatorInfo, newOrderQueue, callbackQueue, startedOrderQueue, lostConnectionCallback):
		"""
		Initializing the networkSender
		"""
		super(NetworkSender, self).__init__()
		self.elevatorInfo = elevatorInfo
		self.newOrderQueue = newOrderQueue
		self.callbackQueue = callbackQueue
		self.startedOrderQueue = startedOrderQueue
		self.lostConnectionCallback = lostConnectionCallback
		self.message = {'newOrders': [], 'startedOrders': []}
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
		self.message['orderQueue'] = self.elevatorInfo['orderQueue'].serialize()
		try:
			order = self.newOrderQueue.get_nowait().serialize()
			self.message['newOrders'].append(order)
			Timer(1/config.HEARTBEAT_FREQUENCY*config.BROADCAST_HEARTBEATS, self.remove_order, (order, )).start()
		except:
			pass
		try:
			startedorder = self.startedOrderQueue.get_nowait().serialize()
			self.message['startedOrders'].append(startedorder)
			Timer(1/config.HEARTBEAT_FREQUENCY*config.BROADCAST_HEARTBEATS, self.remove_started_order, (startedorder, )).start()
		except:
			pass
		return json.dumps(self.message)

	def remove_started_order(self, order):
		"""
		Removes the started order from the message after broadcasting it for BROADCAST_HEARTBEATS in the configfile.
		@input order
		"""
		try:
			self.message['startedOrders'].remove(order)
		except Exception, e:
			print e

	def remove_order(self, order):
		"""
		Removes a new order after broadcasting it for x seconds
		@input order
		"""
		try:
			self.message['newOrders'].remove(order)
		except Exception, e:
			print e

	def run(self):
		""" 
		Constantly broadcasting information over the network
		if the connection breaks, it sends a message to the elevator and deleting orders. 
		"""
		while True:
			try:
				self.sock.sendto(self.build_message(), (config.MCAST_GROUP, config.MCAST_PORT))
			except:
				print 'NO NETWORK, deleting orders and sleeping for %d seconds' % config.RECONNECT_SECONDS
				self.callbackQueue.put(self.lostConnectionCallback)
				while True:
					# EMPTYING newOrderQueue to discard all new orders
					try:
						self.newOrderQueue.get_nowait()
					except:
						break

				sleep(config.RECONNECT_SECONDS)
			sleep(1/config.HEARTBEAT_FREQUENCY)

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



