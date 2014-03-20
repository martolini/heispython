from elevator import Elevator
from IO import io
from channels import INPUT, OUTPUT
import os
import signal
elev = None
def exit_with_pride():
	global elev
	elev.interrupt = True

def main():
	global elev
	elev = Elevator()

if __name__ == "__main__":
	print os.getpid()
	original_sigint = signal.getsignal(signal.SIGINT)
	signal.signal(signal.SIGINT, exit_with_pride)
	main()

