from signalpoller import SignalPoller
from channels import INPUT, OUTPUT
from functools import partial
from io import IO

class Elevator:
	def __init__(self):
		self.signalPoller = SignalPoller()
		self.direction = OUTPUT.MOTOR_DOWN
		self.moving = False

	def set_floor_callbacks(self):
		""" Decide what will happen when floor changes """
		for floor, channel in enumerate(INPUT.SENSORS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.set_floor_indicator, floor))

	def set_button_callbacks(self):
		""" Set what will happen when button is pressed """
		for floor, channel in enumerate(INPUT.IN_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, "IN", floor))

		for floor, channel in enumerate(INPUT.UP_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, "UP", floor))

		for floor, channel in enumerate(INPUT.DOWN_BUTTONS):
			self.signalPoller.add_callback_to_channel(channel, partial(self.button_pressed_callback, "DOWN", floor))


	def turn_off_lights_in_floor(self, floor):
		""" Turn of all light in a certain floor """
		self.set_button_lamp(floor, OUTPUT.UP_LIGHTS, 0)
		self.set_button_lamp(floor, OUTPUT.DOWN_LIGHTS, 0)
		self.set_button_lamp(floor, OUTPUT.IN_LIGHTS, 0)

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

	def button_pressed_callback(self, button_type, floor):
		print button_type, direction, floor
