from elevator import Elevator
from IO import io
from channels import INPUT, OUTPUT
import os
def main():
	elev = Elevator()
	stop = io.read_bit(INPUT.STOP)
	while not stop:
		stop = io.read_bit(INPUT.STOP)
	elev.stop()

if __name__ == "__main__":
	print os.getpid()
	main()
