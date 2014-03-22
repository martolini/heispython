Real-time elevator working for N elevators and M floors.

--------------------------------------------------------

The project runs on 4 main threads:
- Elevator (main thread)
- SignalPoller (reads IO and notifies elevator)
- NetworkHandler.NetworkReceiver (listens on a UDP port)
- NetworkHandler.NetworkSender (sends messages on UDP port)
All the threads mentioned are daemonized, so when Elevator recieves a stopsignal, everything stops. The sockets are garbagecollected.

Also, there may exist 2 additional threads:
- DoorTimer (starts a timer do close the door after opening)
- OrderRemover (removes the order from NetworkSender so it only brodcasts it for x seconds)
These are not daemonized, so the program may wait an additional x seconds to shut down.

--------------------------------------------------------

*signalpoller.SignalPoller* is the only module reading from IO
*elevator.Elevator* is the only module writing to IO
*schlang* is a comedi library ported to python

