from threading import Thread
from time import sleep
from channels import INPUT, OUTPUT
from IO import io


class SignalPoller(Thread):

	def __init__(self):
		super(SignalPoller, self).__init__()
		self.callbacks = {}
		self.running = None
		self.frequency = 1000.0

	def add_callback_to_channe(self, channel, callback):
		""" Fires the callback when the value on the channel changes """
		self.callbacks[channel] = {'lastval': None, 'callback': callback}

	def run(self):
		""" Run the poller until stop is called """
		self.running = True
		while self.running:
			sleep(1/self.frequency)
			for channel in INPUT.ALL:
				value = io.read_bit(channel)
				if value != self.callbacks[channel]['lastval']:
					self.callbacks[channel]['callback']()
					self.callbacks[channel]['lastvalue'] = value

	def stop(self):
		self.running = False