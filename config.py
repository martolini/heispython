"""
Settings for the elevator system
"""
# General settings
NUM_FLOORS = 4
MCAST_GROUP = "224.1.1.1"
MCAST_PORT = 5007

# Time the door should open for clients to go in
DOOR_OPEN_SECONDS = 3

# Parameters for tuning the cost function
FLOOR_WEIGHT = 1
ORDER_WEIGHT = 2
DIRECTION_WEIGHT = 5

# How long it should wait before assuming the elevator is dead
TIMEOUT_LIMIT = 0.5

# For how many heartbeats it should send an order
BROADCAST_HEARTBEATS = 3

# The frequency of sending heartbeats
HEARTBEAT_FREQUENCY = 100.0 #Keep as a float

# Speed of the elevator
SPEED = 300

# How long the sender should sleep before trying to reconnect to the system
RECONNECT_SECONDS = 5