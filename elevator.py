from signalpoller import SignalPoller
from channels import INPUT, OUTPUT
from functools import partial
from IO import io
from models import OrderQueue, Order, DoorTimer
from time import sleep


class Elevator:
	def __init__(self):
		self.signalPoller = SignalPoller()
		self.orderQueue = OrderQueue()
		
		self.doorTimer = DoorTimer(self.close_door, 3)
		self.set_floor_callbacks()
		self.set_button_callbacks()
		self.direction = OUTPUT.MOTOR_DOWN
		self.moving = False
		self.currentFloor = -1
		for light in OUTPUT.LIGHTS:
			if light != -1:
				io.set_bit(light, 0)
		self.signalPoller.start()
		self.drive()

	def stop(self):
		""" Stop EVERYTHING """
		self.stop_elevator()
		self.signalPoller.interrupt = True
		self.signalPoller.join()


	def set_floor_callbacks(self):
		""" Decide what will happen when floor changes """
		for floor, channel in enumerate(INPUT.SENSORS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.floor_indicator_callback, floor))

	def set_button_callbacks(self):
		""" Decide what will happen when button is pressed """
		for floor, channel in enumerate(INPUT.IN_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, "IN", floor))

		for floor, channel in enumerate(INPUT.UP_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, "UP", floor))

		for floor, channel in enumerate(INPUT.DOWN_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, "DOWN", floor))


	def turn_off_lights_in_floor(self, floor):
		""" Turn of all light in a certain floor 
		@input floor"""
		self.set_button_lamp(floor, OUTPUT.UP_LIGHTS, 0)
		self.set_button_lamp(floor, OUTPUT.DOWN_LIGHTS, 0)
		self.set_button_lamp(floor, OUTPUT.IN_LIGHTS, 0)

	def floor_indicator_callback(self, floor):
		""" Handle floor is reached
		@input floor"""
		if floor & 0x01:
			io.set_bit(OUTPUT.FLOOR_IND1, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND1, 0)
		if floor & 0x02:
			io.set_bit(OUTPUT.FLOOR_IND2, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND2, 0)
		self.currentFloor = floor
		if not self.orderQueue.has_orders():
			self.stop_elevator()
		elif self.orderQueue.has_order_in_floor(self.direction, floor) or self.direction != self.find_direction():
			self.orderQueue.delete_order_in_floor(floor)
			self.stop_elevator()
			self.open_door()


	def button_pressed_callback(self, button_type, floor):
		""" Handle button is pressed
		@input button_type, floor"""
		if floor == self.currentFloor:
			print "Tried to go to the same floor"
			return
		if button_type == "UP":
			order = Order(OUTPUT.MOTOR_UP, floor)
		elif button_type == "DOWN":
			order = Order(OUTPUT.MOTOR_DOWN, floor)
		elif button_type == "IN":
			if floor > self.currentFloor:
				order = Order(OUTPUT.MOTOR_UP, floor)
			elif floor < self.currentFloor:
				order = Order(OUTPUT.MOTOR_DOWN, floor)
		else:
			print "Unknown button type %s" % button_type
			return
		self.orderQueue.add_order(order)
		self.should_drive()

	def get_next_order(self):
		if self.direction == OUTPUT.MOTOR_UP:
			for floor in xrange(self.currentFloor+1, INPUT.NUM_FLOORS):
				if self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_UP, floor):
					return Order(OUTPUT.MOTOR_UP, floor)
				if self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_DOWN, floor):
					return Order(OUTPUT.MOTOR_DOWN, floor)
			return None
		else:
			for floor in xrange(self.currentFloor-1, -1, -1):
				if self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_UP, floor):
					return Order(OUTPUT.MOTOR_UP, floor)
				if self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_DOWN, floor):
					return Order(OUTPUT.MOTOR_DOWN, floor)
			return None
		return None

	def find_direction(self):
		""" Returns the direction in which the elevator should move"""
		if self.direction == OUTPUT.MOTOR_UP:
			for floor in xrange(self.currentFloor+1, INPUT.NUM_FLOORS):
			   if self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_UP, floor) or self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_DOWN, floor):
					return OUTPUT.MOTOR_UP
			return OUTPUT.MOTOR_DOWN
		else:
			for floor in xrange(self.currentFloor-1, -1, -1):
				if self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_UP, floor) or self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_DOWN, floor):
					return OUTPUT.MOTOR_DOWN
			return OUTPUT.MOTOR_UP
		return OUTPUT.MOTOR_UP

	def drive(self, speed=300):
		self.direction = self.find_direction()
		io.set_bit(OUTPUT.MOTORDIR, self.direction)
		io.write_analog(OUTPUT.MOTOR, 2048+4*abs(300))
		self.moving = True

	def should_drive(self):
		if not self.orderQueue.has_orders:
			return
		self.drive()

	def stop_elevator(self):
		""" Stop the elevator """
		if not self.moving:
			return
		if self.direction == OUTPUT.MOTOR_UP:
			io.set_bit(OUTPUT.MOTORDIR, OUTPUT.MOTOR_DOWN)
		else:
			io.set_bit(OUTPUT.MOTORDIR, OUTPUT.MOTOR_UP)

		sleep(0.02)
		io.write_analog(OUTPUT.MOTOR, 2048)
		self.moving = False

	def open_door(self):
		print "opening door"
		self.doorTimer.start()

	def close_door(self):
		print "closing door"
		self.should_drive()

	def should_drive(self):
		if self.orderQueue.has_orders() and not self.moving:
			self.drive()

	def will_stop(self):
		self.stop_elevator()
		self.orderQueue.delete_order_in_floor(self.currentFloor)
		self.open_door()
		self.turn_off_lights_in_floor(self.currentFloor)

