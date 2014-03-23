from IO import io
from channels import INPUT, OUTPUT
from threading import Timer
import json
from copy import deepcopy
import pickle
from os.path import isfile
import config


class ORDERDIR:
	UP = 0
	DOWN = 1
	IN = 2

class DoorTimer:
	"""
	Fires a thread that asks elevator to handle door closed in DOOR_OPEN_SECONDS seconds
	"""
	def __init__(self, callback, callbackQueue):
		self.is_finished = True
		self.callback = callback
		self.callbackQueue = callbackQueue
		self.set_timer()

	def set_timer(self):
		self.timer = Timer(config.DOOR_OPEN_SECONDS, self.set_finished)

	def start(self):
		"""
		If already started, cancel the job and start a new one
		"""
		if not self.is_finished:
			self.timer.cancel()
			self.set_timer()
		self.is_finished = False
		self.timer.start()

	def set_finished(self):
		self.is_finished = True
		self.set_timer()
		self.callbackQueue.put(self.callback)



class Order:
	def __init__(self, direction, floor):
		self.direction = direction
		self.floor = floor

	def serialize(self):
		return {'direction': self.direction, 'floor': self.floor, 'id': int('%s%s' % (self.floor, self.direction))}

	@staticmethod
	def deserialize(object):
		return Order(direction=object['direction'], floor=object['floor'])

	def __str__(self):
		return "direction: %d, floor: %d" % (self.direction, self.floor)

class OrderQueue:
	def __init__(self, orders=None):
		""" Initializing OrderQueue setting False in every order """
		if orders:
			self.orders = orders
		else:
			self.orders = {ORDERDIR.UP: [False] * config.NUM_FLOORS, ORDERDIR.DOWN: [False] * config.NUM_FLOORS, ORDERDIR.IN: [False] * config.NUM_FLOORS}

	def serialize(self):
		"""
		Serializing itself
		"""
		return self.orders

	@staticmethod
	def deserialize(orders):
		"""
		Deserializing an orderobject
		@input orders (serialized object)
		@return Object
		"""
		try:
			return OrderQueue(orders={int(k):v for k, v in orders.items()})
		except:
			raise ValueError("WRONG ORDERQUEUE")

	def get_copy(self):
		""" Returns a deep copy of itself """
		return deepcopy(self)

	def has_orders(self):
		""" 
		Determines whether the queue has any orders
		@return true, false
		"""
		for key, val in self.orders.items():
			if True in val:
				return True
		return False

	def add_order(self, order):
		"""
		Adding order to OrderQueue
		@input order (Order)
		"""
		self.orders[order.direction][order.floor] = True

	def delete_order_in_floor(self, direction, floor):
		"""
		Deleting an order in a certain floor
		@input floor
		"""
		for _direction, floors in self.orders.items():
			if _direction in (direction, ORDERDIR.IN):
				floors[floor] = False

	def has_order_in_floor_and_direction(self, direction, floor):
		"""
		Returns if the queue has order in a floor in a certain direction
		@input direction, floor
		@return true, false
		"""
		return self.orders[direction][floor]

	def has_order_in_floor(self, floor):
		"""
		Returns if the queue has order in a floor and any direction
		@return true, false
		"""
		for direction, floors in self.orders.items():
			if floors[floor]:
				return True
		return False

	def delete_all_orders(self, exclude=None):
		"""
		Deletes all orders
		"""
		for direction, floors in self.orders.items():
			if direction == exclude:
				continue
			for floor in range(len(floors)):
				floors[floor] = False

	def yield_orders(self, exclude=(ORDERDIR.IN,)):
		"""
		Yielding all orders
		@return generator of Orders
		"""
		for direction, floors in self.orders.items():
			if direction in exclude:
				continue
			for floor in range(len(floors)):
				if floors[floor]:
					yield Order(direction, floor)

	def create_backup(self):
		"""
		Creates a backup of the elevator containing only the inner orders,
		the rest is false
		@return OrderQueue
		"""
		orderQueue = self.get_copy()
		for direction, floors in orderQueue.orders.items():
			for floor in range(len(floors)):
				if direction != ORDERDIR.IN and floors[floor]:
					floors[floor] = False
		return orderQueue

	def save_to_file(self):
		orderQueue = self.create_backup()
		with open('orderqueue.backup', 'w+') as wfile:
			pickle.dump(orderQueue, wfile)
			
	@staticmethod
	def load_from_file():
		"""
		Loading from file and returning an OrderQueue
		"""
		if not isfile('orderqueue.backup'):
			return OrderQueue()
		with open('orderqueue.backup', 'r') as rfile:
			orderQueue = pickle.load(rfile)
			return orderQueue if orderQueue else OrderQueue()