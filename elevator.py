from signalpoller import SignalPoller
from channels import INPUT, OUTPUT
from functools import partial
from IO import io
from models import OrderQueue, Order, DoorTimer, ORDERDIR
from time import sleep
from networkhandler import NetworkHandler
from threading import active_count, current_thread
from Queue import Queue

class Elevator:
	def __init__(self):
		self.interrupt = False
		self.orderQueue = OrderQueue.load_from_file()
		self.initialize_lights()
		self.callbackQueue = Queue()
		self.signalPoller = SignalPoller(self.callbackQueue)
		self.newOrderQueue = Queue()
		self.doorTimer = DoorTimer(self.close_door, self.callbackQueue)
		self.direction = OUTPUT.MOTOR_DOWN
		self.moving = False
		self.currentFloor = -1
		self.initialize_networkhandler()
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
		for order in self.orderQueue.yield_orders(exclude=(ORDERDIR.UP, ORDERDIR.DOWN,)):
			print order
			self.set_button_light(order.floor, OUTPUT.IN_LIGHTS, 1)


	def initialize_networkhandler(self):
		"""
		Initialize the networkhandler, pass along callbacks
		"""
		self.networkHandler = NetworkHandler()
		self.networkHandler.networkReceiver.callbackQueue = self.callbackQueue
		self.networkHandler.networkSender.newOrderQueue = self.newOrderQueue
		self.networkHandler.networkSender.callbackQueue = self.callbackQueue
		self.networkHandler.networkSender.lostConnectionCallback = self.lost_connection
		self.networkHandler.networkReceiver.addOrderCallback = self.received_order
		self.networkHandler.networkReceiver.setLightCallback = self.set_light_callback

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
		self.stop_elevator()
		# self.signalPoller.interrupt = True
		# self.signalPoller.join()
		# self.networkHandler.stop()
		# self.networkHandler.join()
		print "# threads: ", active_count()

	def lost_connection(self):
		"""
		Called when networkhandler lost connection
		"""
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
		"""
		if order.direction == ORDERDIR.IN:
			self.set_button_light(order.floor, OUTPUT.IN_LIGHTS, 1)
		self.orderQueue.add_order(order)
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
		if direction == ORDERDIR.UP:
			lights = OUTPUT.UP_LIGHTS
		elif direction == ORDERDIR.DOWN:
			lights = OUTPUT.DOWN_LIGHTS
		self.set_button_light(floor, lights, value)


	def set_button_light(self, floor, lights, value):
		if lights[floor] != -1:
			io.set_bit(lights[floor], value)


	def find_direction(self):
		""" 
		Returns the direction in which the elevator should move
		"""
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
		"""
		Finding direction and starts the elevator
		"""
		self.direction = self.find_direction()
		io.set_bit(OUTPUT.MOTORDIR, self.direction)
		io.write_analog(OUTPUT.MOTOR, 2048+4*abs(300))
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

		sleep(0.02)
		io.write_analog(OUTPUT.MOTOR, 2048)
		self.moving = False

	def open_door(self):
		"""
		Opens door and fires a thread with callback in x seconds
		"""
		self.set_button_light(self.currentFloor, OUTPUT.UP_LIGHTS, 0)
		self.set_button_light(self.currentFloor, OUTPUT.DOWN_LIGHTS, 0)
		self.set_button_light(self.currentFloor, OUTPUT.IN_LIGHTS, 0)
		io.set_bit(OUTPUT.DOOR_OPEN, 1)
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
		if not self.orderQueue.has_orders():
			self.stop_elevator()
		elif self.orderQueue.has_order_in_floor(self.direction, self.currentFloor) or self.direction != self.find_direction():
			self.orderQueue.delete_order_in_floor(self.currentFloor)
			self.update_and_send_elevator_info()
			self.stop_elevator()
			self.open_door()

	def should_drive(self):
		"""
		Decides whether the elevator should drive after stopping in a floor
		"""
		if (self.orderQueue.has_order_in_floor(direction=OUTPUT.MOTOR_UP, floor=self.currentFloor) or self.orderQueue.has_order_in_floor(direction=OUTPUT.MOTOR_DOWN, floor=self.currentFloor)) and not self.moving:
			self.orderQueue.delete_order_in_floor(self.currentFloor)
			self.update_and_send_elevator_info()
			self.open_door()
		elif self.orderQueue.has_orders() and not self.moving and self.doorTimer.is_finished:
			self.drive()

	def update_and_send_elevator_info(self):
		"""
		Updates and sends a copy of its elevatorinfo to the networkHandler
		"""
		self.networkHandler.networkSender.elevatorInfo = {'currentFloor': self.currentFloor, 'direction': self.find_direction(), 'orderQueue': self.orderQueue.get_copy()}
		self.orderQueue.save_to_file()