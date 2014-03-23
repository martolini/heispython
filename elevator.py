from signalpoller import SignalPoller
from channels import INPUT, OUTPUT
from functools import partial
from IO import io
import config
from models import OrderQueue, Order, DoorTimer, ORDERDIR
from time import sleep
from networkhandler import NetworkHandler
from threading import active_count, current_thread
from Queue import Queue

class Elevator:
	def __init__(self):
		"""
		Initialize variables and starts threads
		"""
		self.interrupt = False
		self.direction = OUTPUT.MOTOR_DOWN
		self.moving = False
		self.currentFloor = -1

		self.orderQueue = OrderQueue.load_from_file()
		self.callbackQueue = Queue()
		self.newOrderQueue = Queue()
		self.signalPoller = SignalPoller(self.callbackQueue)
		self.doorTimer = DoorTimer(self.close_door, self.callbackQueue)
		self.initialize_lights()
		self.initialize_networkHandler()
		self.update_and_send_elevator_info()
		self.set_callbacks()
		self.networkHandler.start()
		self.signalPoller.start()
		self.drive()
		self.run()

	def initialize_lights(self):
		"""
		Turn of all lights on the panel
		"""
		for light in OUTPUT.LIGHTS:
			if light != -1:
				io.set_bit(light, 0)
		for order in self.orderQueue.yield_orders():
			self.set_button_light(order.floor, OUTPUT.IN_LIGHTS, 1)


	def initialize_networkHandler(self):
		"""
		Initialize the networkhandler, pass along callbacks
		"""
		self.networkHandler = NetworkHandler(
			self.callbackQueue,
			self.received_order,
			self.set_light_callback,
			self.newOrderQueue,
			self.lost_connection
			)

	def set_callbacks(self):
		"""
		Setting callbacks for threads
		"""
		self.set_floor_callbacks()
		self.set_button_callbacks()
		self.set_stop_callback()

	def run(self):
		""" 
		Main thread - block while waiting on something to do 
		"""
		while not self.interrupt:
			func = self.callbackQueue.get()
			func()
		self.stop_elevator()

	def stop(self):
		""" Stops EVERYTHING """
		self.interrupt = True
		print "# threads: ", active_count()

	def lost_connection(self):
		"""
		Called when networkhandler lost connection
		"""
		for light in OUTPUT.UP_LIGHTS + OUTPUT.DOWN_LIGHTS:
			if light != -1:
				io.set_bit(light, 0)
		if self.orderQueue.has_orders():
			self.orderQueue.delete_all_orders(exclude=ORDERDIR.IN)



	def set_stop_callback(self):
		""" 
		Listen on stop button 
		"""
		self.signalPoller.add_callback_to_channel(INPUT.STOP, self.stop)

	def set_floor_callbacks(self):
		""" 
		Set callbackon on floor changes 
		"""
		for floor, channel in enumerate(INPUT.SENSORS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.floor_reached_callback, floor))

	def set_button_callbacks(self):
		""" 
		Set callback on button pressed 
		"""
		for floor, channel in enumerate(INPUT.IN_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, ORDERDIR.IN, floor))

		for floor, channel in enumerate(INPUT.UP_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, ORDERDIR.UP, floor))

		for floor, channel in enumerate(INPUT.DOWN_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, ORDERDIR.DOWN, floor))


	def set_floor_indicator_light(self):
		""" 
		Switching the floor indicators
		@input floor
		"""
		if self.currentFloor & 0x01:
			io.set_bit(OUTPUT.FLOOR_IND1, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND1, 0)
		if self.currentFloor & 0x02:
			io.set_bit(OUTPUT.FLOOR_IND2, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND2, 0)

	def received_order(self, order):
		"""
		External orders come from NetworkHandler, internal from self
		@input order
		"""
		if order.direction == ORDERDIR.IN:
			self.set_button_light(order.floor, OUTPUT.IN_LIGHTS, 1)
		self.orderQueue.add_order(order)
		print 'added order ',
		print order
		self.update_and_send_elevator_info()
		self.should_drive()


	def floor_reached_callback(self, floor):
		""" 
		Callback on floor is reached
		@input floor
		"""
		self.currentFloor = floor
		self.set_floor_indicator_light()
		self.should_stop()


	def button_pressed_callback(self, orderdir, floor):
		""" 
		Callback on button is pressed
		@input orderdir, floor
		"""
		order = Order(orderdir, floor)
		if order.direction == ORDERDIR.IN:
			self.received_order(order)
			return
		self.newOrderQueue.put(order)

	def set_light_callback(self, direction, floor, value):
		"""
		Setting lights on orders coming from the networkHandler
		@input direction, floor, value
		"""
		if direction == ORDERDIR.UP:
			lights = OUTPUT.UP_LIGHTS
		elif direction == ORDERDIR.DOWN:
			lights = OUTPUT.DOWN_LIGHTS
		self.set_button_light(floor, lights, value)


	def set_button_light(self, floor, lights, value):
		"""
		Sets a button light
		@input floor, lights, value
		"""
		if lights[floor] != -1:
			io.set_bit(lights[floor], value)

	def find_direction(self):
		""" 
		Returns the direction in which the elevator should move
		"""
		if self.direction == OUTPUT.MOTOR_UP:
			for floor in xrange(self.currentFloor+1, config.NUM_FLOORS):
			   if self.orderQueue.has_order_in_floor(floor):
					return OUTPUT.MOTOR_UP
			return OUTPUT.MOTOR_DOWN
		else:
			for floor in xrange(self.currentFloor-1, -1, -1):
				if self.orderQueue.has_order_in_floor(floor):
					return OUTPUT.MOTOR_DOWN
			return OUTPUT.MOTOR_UP
		return OUTPUT.MOTOR_UP

	def drive(self, speed=300):
		"""
		Finding direction and starts the elevator
		"""
		self.direction = self.find_direction()
		io.set_bit(OUTPUT.MOTORDIR, self.direction)
		io.write_analog(OUTPUT.MOTOR, 2048+4*abs(config.SPEED))
		self.moving = True

	def stop_elevator(self):
		""" 
		Stops the elevator
		"""
		if not self.moving:
			return
		if self.direction == OUTPUT.MOTOR_UP:
			io.set_bit(OUTPUT.MOTORDIR, OUTPUT.MOTOR_DOWN)
		else:
			io.set_bit(OUTPUT.MOTORDIR, OUTPUT.MOTOR_UP)

		sleep(0.01)
		io.write_analog(OUTPUT.MOTOR, 2048)
		self.moving = False

	def open_door(self):
		"""
		Opens door and fires a thread with callback in x seconds
		"""
		self.set_button_light(self.currentFloor, OUTPUT.IN_LIGHTS, 0)
		io.set_bit(OUTPUT.DOOR_OPEN, 1)
		print 'opening door'
		self.doorTimer.start()

	def close_door(self):
		"""
		Closes door and checking if the elevator should drive
		"""
		print "closing door"
		io.set_bit(OUTPUT.DOOR_OPEN, 0)
		self.should_drive()

	def should_stop(self):
		"""
		Decides whether the elevator should stop when arriving in a certain floor
		"""
		newDirection = self.find_direction()
		if not self.orderQueue.has_orders():
			# After initial or if dead.
			self.stop_elevator()
		elif self.orderQueue.has_order_in_floor_and_direction(self.direction, self.currentFloor) or self.orderQueue.has_order_in_floor_and_direction(ORDERDIR.IN, self.currentFloor):
			# Elevator has order in same floor same direction
			if self.direction != newDirection:
				print 'deleting both order'
				self.orderQueue.delete_order_in_floor(newDirection, self.currentFloor)
			self.orderQueue.delete_order_in_floor(self.direction, self.currentFloor)
			self.update_and_send_elevator_info()
			self.stop_elevator()
			self.open_door()
		elif self.direction != newDirection:
			# Elevator has no order further in its direction
			if self.orderQueue.has_order_in_floor(self.currentFloor):
				# It has an order in the opposite direction in the same floor
				self.orderQueue.delete_order_in_floor(not self.direction, self.currentFloor)
				self.update_and_send_elevator_info()
				self.stop_elevator()
				self.open_door()
			else:
				# It ran here on a mistake, probably on startup it checks the closest floor before inner orders
				self.stop_elevator()
				self.should_drive()

	def should_drive(self):
		"""
		Decides whether the elevator should drive after stopping in a floor
		"""
		if not self.moving:
			new_direction = self.find_direction()
			if self.orderQueue.has_order_in_floor_and_direction(self.direction, self.currentFloor) or self.orderQueue.has_order_in_floor_and_direction(ORDERDIR.IN, self.currentFloor):
				self.orderQueue.delete_order_in_floor(self.direction, self.currentFloor)
				self.open_door()
			elif new_direction != self.direction and self.orderQueue.has_order_in_floor_and_direction(not self.direction, self.currentFloor):
				self.orderQueue.delete_order_in_floor(not self.direction, self.currentFloor)
				self.open_door()
			elif self.orderQueue.has_orders() and not self.moving and self.doorTimer.is_finished:
				self.drive()
			self.update_and_send_elevator_info()

	def update_and_send_elevator_info(self):
		"""
		Updates and sends a copy of its elevatorinfo to the networkHandler and saving orderQueue to file
		"""
		self.networkHandler.networkSender.elevatorInfo = {'currentFloor': self.currentFloor, 'direction': self.find_direction(), 'orderQueue': self.orderQueue.get_copy()}
		self.orderQueue.save_to_file()