from elevator import ElevatorDriver

def main():
	elev = ElevatorDriver()
	elev.set_speed(300)

	while True:
		if elev.get_floor() == 0:
			elev.set_speed(300)
		elif elev.get_floor() == elev.NUM_FLOORS-1:
			elev.set_speed(-300)

		if elev.get_stop_signal():
			elev.set_speed(0)
			break

if __name__ == "__main__":
	main()
