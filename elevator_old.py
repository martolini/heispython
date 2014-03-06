from channels import INPUT, OUTPUT
from IO import io
from time import sleep
from models import Panel, OrderQueue, Order, STATE, SIGNAL, DoorTimer

class Elevator:
	def __init__(self):
		self.panel = Panel()
		self.orderQueue = OrderQueue()
		self.direction = OUTPUT.MOTOR_UP
		self.currentFloor=1
		self.currentState = STATE.IDLE
		self.nextState = STATE.IDLE
		self.signals = [False] * SIGNAL.NUM_SIGNALS
		self.NUM_FLOORS = INPUT.NUM_FLOORS
		self.speed = 100
		self.drive()
		self.moving = True
		while self.panel.get_floor() == -1:
			pass
		self.currentFloor = self.panel.get_floor()
		self.stop()
		self.moving = False
		self.speed = 300

	def run(self):
		while not self.panel.get_stop_signal():
			self.nextState = self.currentState

			if self.currentState == STATE.IDLE:
				if self.signals[SIGNAL.HAS_ORDERS]:
					if self.signals[SIGNAL.SHOULD_STOP]:
						self.nextState = STATE.OPEN_DOOR
					else: self.nextState = STATE.DRIVE

			elif self.currentState == STATE.DRIVE:
				if self.signals[SIGNAL.SHOULD_STOP]:
					self.nextState = STATE.OPEN_DOOR

			elif self.currentState == STATE.OPEN_DOOR:
				if self.signals[SIGNAL.TIMER_FINISHED]:
					self.nextState = STATE.CLOSE_DOOR

			elif self.currentState == STATE.CLOSE_DOOR:
				if self.signals[SIGNAL.OBSTRUCTION]:
					self.nextState = STATE.OPEN_DOOR
				elif self.signals[SIGNAL.HAS_ORDERS]:
					self.nextState = STATE.DRIVE

			if self.nextState != self.currentState:
				if self.nextState == STATE.DRIVE:
					self.drive()

				elif self.nextState == STATE.OPEN_DOOR:
					print "YO KIDS"
					if self.currentState == STATE.DRIVE:
						self.stop()
					self.orderQueue.delete_order_in_floor(self.currentFloor)
					self.panel.turn_off_lights_in_floor(self.currentFloor)
					self.panel.set_door_light(1)
					self.panel.timer.start()

				elif self.nextState == STATE.CLOSE_DOOR:
					self.panel.set_door_light(0)

				elif self.nextState == STATE.EMERGENCY_STOP:
					self.stop()

			self.currentState = self.nextState
			self.update_signals()
			order = self.panel.get_order(self.currentFloor)
			if order:
				self.orderQueue.add_order(order)
		self.stop()




	def update_signals(self):
		if self.currentState == STATE.IDLE:
			self.signals[SIGNAL.HAS_ORDERS] = self.orderQueue.has_orders()
			self.signals[SIGNAL.SHOULD_STOP] = self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_UP, self.currentFloor) or self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_DOWN, self.currentFloor)

		elif self.currentState == STATE.DRIVE:
			tempFloor = self.panel.get_floor()
			if tempFloor != -1:
				self.currentFloor = tempFloor
				self.panel.set_floor_indicator(self.currentFloor)
				if self.orderQueue.has_order_in_floor(self.direction, self.currentFloor) or self.find_direction() != self.direction:
					self.signals[SIGNAL.SHOULD_STOP] = 1
				else: self.signals[SIGNAL.SHOULD_STOP] = 0
			else: self.signals[SIGNAL.SHOULD_STOP] = 0

		elif self.currentState == STATE.OPEN_DOOR:
			self.signals[SIGNAL.TIMER_FINISHED] = self.panel.timer.is_finished

		elif self.currentState == STATE.CLOSE_DOOR:
			self.signals[SIGNAL.HAS_ORDERS] = self.orderQueue.has_orders()
			self.signals[SIGNAL.OBSTRUCTION] = self.panel.get_obstruction_signal()

		self.signals[SIGNAL.EMERGENCY_STOP] = self.panel.get_stop_signal()



	def find_direction(self):
		if self.direction == OUTPUT.MOTOR_UP:
			for floor in xrange(self.currentFloor+1, self.NUM_FLOORS):
			   if self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_UP, floor) or self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_DOWN, floor):
					return OUTPUT.MOTOR_UP
			return OUTPUT.MOTOR_DOWN
		else:
			for floor in xrange(self.currentFloor-1, -1, -1):
				if self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_UP, floor) or self.orderQueue.has_order_in_floor(OUTPUT.MOTOR_DOWN, floor):
					return OUTPUT.MOTOR_DOWN
			return OUTPUT.MOTOR_UP
		return OUTPUT.MOTOR_UP

	def drive(self):
		self.direction = self.find_direction()

		io.set_bit(OUTPUT.MOTORDIR, self.direction)
		io.write_analog(OUTPUT.MOTOR, 2048+4*abs(self.speed))
		self.moving = True

	def stop(self):
		if not self.moving:
			return
		if self.direction == OUTPUT.MOTOR_UP:
			io.set_bit(OUTPUT.MOTORDIR, OUTPUT.MOTOR_DOWN)
		else:
			io.set_bit(OUTPUT.MOTORDIR, OUTPUT.MOTOR_UP)

		sleep(0.02)
		io.write_analog(OUTPUT.MOTOR, 2048)

	
