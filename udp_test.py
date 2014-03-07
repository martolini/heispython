import SocketServer

class MyUDPHandler(SocketServer.BaseRequestHandler):
    """
    This class works similar to the TCP handler class, except that
    self.request consists of a pair of data and client socket, and since
    there is no connection the client address must be given explicitly
    when sending data back via sendto().
    """
    elevators = []

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        if self.client_address not in self.elevators:
        	self.elevators.append(self.client_address)
        print "{} wrote:".format(self.client_address), 
        print data
        print self.elevators
        socket.sendto(data.upper(), self.client_address)

if __name__ == "__main__":
    HOST, PORT = "localhost", 9999
    server = SocketServer.UDPServer((HOST, PORT), MyUDPHandler)
    server.serve_forever()