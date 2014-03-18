from IO import io
from channels import INPUT, OUTPUT
from threading import Timer
import json
from copy import deepcopy

class ORDERDIR:
	UP = 0
	DOWN = 1
	IN = 2

class SIGNAL:
	HAS_ORDERS = 0
	SHOULD_STOP = 1
	TIMER_FINISHED = 2
	EMERGENCY_STOP = 3
	OBSTRUCTION = 4
	NUM_SIGNALS = 5

class STATE:
	IDLE = 0
	DRIVE = 1
	OPEN_DOOR = 2
	CLOSE_DOOR = 3
	EMERGENCY_STOP = 4

class DoorTimer:
	def __init__(self, callback, callbackQueue):
		self.is_finished = True
		self.callback = callback
		self.callbackQueue = callbackQueue

	def start(self):
		self.is_finished = False
		Timer(3, self.set_finished).start()

	def set_finished(self):
		self.is_finished = True
		self.callbackQueue.put(self.callback)



class Order:
	def __init__(self, direction, floor):
		self.direction = direction
		self.floor = floor

	def __str__(self):
		return "direction: %d, floor: %d" % (self.direction, self.floor)

class OrderSerializer:
	@staticmethod
	def serialize(order):
		return {'direction': order.direction, 'floor': order.floor, 'id': int('%s%s' % (order.floor, order.direction))}

	@staticmethod
	def deserialize(object):
		return Order(direction=object['direction'], floor=object['floor'])

class Panel:
	def __init__(self):
		""" Initializing the panel"""
		for light in OUTPUT.LIGHTS:
			if light != -1:
				io.set_bit(light, 0)

		self.set_floor_indicator(1)
		self.timer = DoorTimer()

	def set_floor_indicator(self, floor):
		""" Set floor indicators based on floor 
		@input floor
		"""
		if floor & 0x01:
			io.set_bit(OUTPUT.FLOOR_IND1, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND1, 0)
		if floor & 0x02:
			io.set_bit(OUTPUT.FLOOR_IND2, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND2, 0)

	def set_button_lamp(self, floor, light, value):
		""" Set button lamp
		@input floor, light, value
		"""
		if floor == INPUT.NUM_FLOORS-1 and light == OUTPUT.UP_LIGHTS or floor == 0 and light == OUTPUT.DOWN_LIGHTS:
			return
		io.set_bit(light[floor], value)

	def set_stop_lamp(self, value):
		""" Set stop lamp
		@input value (0, 1)
		"""
		io.set_bit(OUTPUT.LIGHT_STOP, value)

	def turn_off_lights_in_floor(self, floor):
		self.set_button_lamp(floor, OUTPUT.UP_LIGHTS, 0)
		self.set_button_lamp(floor, OUTPUT.DOWN_LIGHTS, 0)
		self.set_button_lamp(floor, OUTPUT.IN_LIGHTS, 0)

	def set_door_light(self, value):
		""" Set door light
		@input value (0, 1)
		"""
		io.set_bit(OUTPUT.DOOR_OPEN, value)

	def get_stop_signal(self):
		""" Get stop signal
		@return 0, 1
		"""
		return io.read_bit(INPUT.STOP)

	def get_obstruction_signal(self):
		""" Get obstruction signal
		@return 0, 1
		"""
		return io.read_bit(INPUT.OBSTRUCTION)

	def get_floor(self):
		""" Return current floor
		@return floor (range(1,N_FLOORS))
		"""
		for floor, sensor in enumerate(INPUT.SENSORS):
			if io.read_bit(sensor):
				return floor
		return -1

	def get_button_signal(self, button):
		""" Get button signal 
		@input floor, button (BUTTON_UP, BUTTON_DOWN, BUTTON_COMMAND)
		"""
		return io.read_bit(button).value

	def get_order(self, currentFloor):
		""" Return orders
		@input currentFloor of elevator
		@return orders (generator)
		"""

		for index, button in enumerate(INPUT.UP_BUTTONS):
			if button != -1:
				if self.get_button_signal(button):
					self.set_button_lamp(index, OUTPUT.UP_LIGHTS, 1)
					return Order(OUTPUT.MOTOR_UP, index)

		for index, button in enumerate(INPUT.DOWN_BUTTONS):
			if button != -1:
				if self.get_button_signal(button):
					self.set_button_lamp(index, OUTPUT.DOWN_LIGHTS, 1)
					return Order(OUTPUT.MOTOR_DOWN, index)

		for index, button in enumerate(INPUT.IN_BUTTONS):
			if button != -1:
				if self.get_button_signal(button):
					if index < currentFloor:
						direction = OUTPUT.MOTOR_DOWN
					else:
						direction = OUTPUT.MOTOR_UP
					self.set_button_lamp(index, OUTPUT.IN_LIGHTS, 1)
					return Order(direction, index)

class OrderQueue:
	def __init__(self):
		""" Initializing OrderQueue setting False in every order """
		self.orders = {ORDERDIR.UP: [False] * INPUT.NUM_FLOORS, ORDERDIR.DOWN: [False] * INPUT.NUM_FLOORS, ORDERDIR.IN: [False] * INPUT.NUM_FLOORS}

	def get_copy(self):
		return deepcopy(self.orders)#deepcopy({k:v for k, v in self.orders.items() if k != 2})

	def has_orders(self):
		""" 
		@return true, false
		"""
		for key, val in self.orders.items():
			if True in val:
				return True
		return False

	def add_order(self, order):
		""" Adding order to OrderQueue
		@input order (Order)
		"""
		self.orders[order.direction][order.floor] = True

	def delete_order_in_floor(self, floor):
		for direction, floors in self.orders.items():
			floors[floor] = False

	def has_order_in_floor(self, direction, floor):
		return self.orders[direction][floor] or self.orders[ORDERDIR.IN][floor]

	def delete_all_orders(self):
		for direction, floors in self.orders.items():
			floors[floor] = False





	
