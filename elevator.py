from channels import INPUT, OUTPUT
from IO import io
from time import sleep

class ElevatorDriver:
	def __init__(self):
		self.direction = OUTPUT.MOTOR_DOWN
		self.moving = False
		self.NUM_FLOORS = INPUT.NUM_FLOORS

		for light in OUTPUT.LIGHTS:
			if light != -1:
				io.set_bit(light, 0)

	def set_speed(self, speed):
		if speed > 0:
			self.direction = OUTPUT.MOTOR_UP
		elif speed < 0:
			self.direction = OUTPUT.MOTOR_DOWN
		else:
			self.stop()

		io.set_bit(OUTPUT.MOTORDIR, self.direction)
		io.write_analog(OUTPUT.MOTOR, 2048+4*abs(speed))
		self.moving = True

	def stop(self):
		if not self.moving:
			return
		if self.direction is OUTPUT.MOTOR_UP:
			io.set_bit(OUTPUT.MOTORDIR, OUTPUT.MOTOR_DOWN)
		else:
			io.set_bit(OUTPUT.MOTORDIR, OUTPUT.MOTOR_UP)

		sleep(0.02)
		io.write_analog(OUTPUT.MOTOR, 2048)

	def set_floor_indicator(self, floor):
		if floor & 0x01:
			io.set_bit(OUTPUT.FLOOR_IND1, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND1, 0)
		if floor & 0x02:
			io.set_bit(OUTPUT.FLOOR_IND2, 1)
		else:
			io.set_bit(OUTPUT.FLOOR_IND2, 0)

	def set_button_lamp(self, floor, light, value):
		if floor == self.NUM_FLOORS-1 and light == OUTPUT.UP_LIGHTS or floor == 0 and light == OUTPUT.DOWN_LIGHTS:
			return
		io.set_bit(light[floor], value)

	def set_stop_lamp(self, value):
		io.set_bit(OUTPUT.LIGHT_STOP, value)

	def set_door_light(self, value):
		io.set_bit(OUTPUT.DOOR_OPEN, value)

	def get_stop_signal(self):
		return io.read_bit(INPUT.STOP)

	def get_obstruction_signal(self):
		return io.read_bit(INPUT.OBSTRUCTION)

	def get_floor(self):
		for floor, sensor in enumerate(INPUT.SENSORS):
			if io.read_bit(sensor):
				return floor
		return -1

	def get_button_signal(self, floor, button):
		return io.read_bit(button[floor]).value

	
