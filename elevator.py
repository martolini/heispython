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
		self.callbackQueue = Queue()
		self.signalPoller = SignalPoller(self.callbackQueue)
		self.orderQueue = OrderQueue()
		self.newOrderQueue = Queue()
		self.doorTimer = DoorTimer(self.close_door, self.callbackQueue)
		self.direction = OUTPUT.MOTOR_DOWN
		self.moving = False
		self.currentFloor = -1
		for light in OUTPUT.LIGHTS:
			if light != -1:
				io.set_bit(light, 0)
		self.networkHandler = NetworkHandler()
		self.networkHandler.networkReceiver.callbackQueue = self.callbackQueue
		self.networkHandler.networkSender.newOrderQueue = self.newOrderQueue
		self.update_and_send_elevator_info()
		self.set_callbacks()
		self.networkHandler.start()
		self.signalPoller.start()
		self.drive()
		self.run()

	def set_callbacks(self):
		self.set_floor_callbacks()
		self.set_button_callbacks()
		self.set_stop_callback()
		self.set_add_order_callback()

	def run(self):
		while not self.interrupt:
			func = self.callbackQueue.get()
			func()

	def stop(self):
		""" Stops EVERYTHING """
		self.interrupt = True
		self.stop_elevator()
		# self.signalPoller.interrupt = True
		# self.signalPoller.join()
		# self.networkHandler.stop()
		# self.networkHandler.join()
		print "# threads: ", active_count()

	def set_add_order_callback(self):
		self.networkHandler.networkReceiver.addOrderCallback = self.received_order

	def set_stop_callback(self):
		""" Listen on stop button """
		self.signalPoller.add_callback_to_channel(INPUT.STOP, self.stop)

	def set_floor_callbacks(self):
		""" Decide what will happen when floor changes """
		for floor, channel in enumerate(INPUT.SENSORS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.floor_indicator_callback, floor))

	def set_button_callbacks(self):
		""" Decide what will happen when button is pressed """
		for floor, channel in enumerate(INPUT.IN_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, ORDERDIR.IN, floor))

		for floor, channel in enumerate(INPUT.UP_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, ORDERDIR.UP, floor))

		for floor, channel in enumerate(INPUT.DOWN_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, ORDERDIR.DOWN, floor))


	def turn_off_lights_in_floor(self, floor):
		""" Turn of all light in a certain floor 
		@input floor"""
		self.set_button_lamp(floor, OUTPUT.UP_LIGHTS, 0)
		self.set_button_lamp(floor, OUTPUT.DOWN_LIGHTS, 0)
		self.set_button_lamp(floor, OUTPUT.IN_LIGHTS, 0)

	def set_floor_lights(self, floor):
		""" Switching the floor indicators
		@input floor """
		if floor & 0x01:
			io.set_bit(OUTPUT.FLOOR_IND1, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND1, 0)
		if floor & 0x02:
			io.set_bit(OUTPUT.FLOOR_IND2, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND2, 0)

	def received_order(self, order):
		if not self.moving and order.floor == self.currentFloor:
			return
		self.orderQueue.add_order(order)
		self.update_and_send_elevator_info()
		self.should_drive()

	def floor_indicator_callback(self, floor):
		""" Handle floor is reached
		@input floor"""
		self.set_floor_lights(floor)
		self.currentFloor = floor
		if not self.orderQueue.has_orders():
			self.stop_elevator()
		elif self.orderQueue.has_order_in_floor(self.direction, floor) or self.direction != self.find_direction():
			self.orderQueue.delete_order_in_floor(floor)
			self.stop_elevator()
			self.open_door()
		self.update_and_send_elevator_info()


	def button_pressed_callback(self, orderdir, floor):
		""" Handle button is pressed
		@input button_type, floor"""
		order = Order(orderdir, floor)
		if order.direction == ORDERDIR.IN:
			self.received_order(order)
			return
		if floor == self.currentFloor and not self.moving:
			print "Tried to go to the same floor"
			return
		self.newOrderQueue.put(order)


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
		if self.orderQueue.has_orders() and not self.moving and self.doorTimer.is_finished:
			self.drive()

	def will_stop(self):
		self.stop_elevator()
		self.orderQueue.delete_order_in_floor(self.currentFloor)
		self.open_door()
		self.turn_off_lights_in_floor(self.currentFloor)

	def update_and_send_elevator_info(self):
		self.networkHandler.networkSender.elevatorInfo = {'currentFloor': self.currentFloor, 'direction': self.find_direction(), 'orderQueue': self.orderQueue.get_copy()}