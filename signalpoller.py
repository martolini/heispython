from threading import Thread
from time import sleep
from channels import INPUT, OUTPUT
from IO import io


class SignalPoller(Thread):

	def __init__(self):
		super(SignalPoller, self).__init__()
		self.daemon = True
		self.callbacks = {}
		self.interrupt = False
		self.frequency = 10.0

	def add_callback_to_channel(self, channel, callback):
		""" Fires the callback when the value on the channel changes """
		self.callbacks[channel] = {'lastval': 0, 'callback': callback}

	def run(self):
		""" Run the poller until stop is called """
		while not self.interrupt:
			sleep(1/self.frequency)
			for channel in self.callbacks.keys():
				if channel != -1:
					value = io.read_bit(channel)
					if value == 1 and value != self.callbacks[channel]['lastval']:
						self.callbacks[channel]['callback']()
					self.callbacks[channel]['lastval'] = value