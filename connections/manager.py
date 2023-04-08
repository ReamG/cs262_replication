import time
import socket
import threading
import pdb
from typing import Mapping
from queue import Queue
from threading import Thread
import connections.consts as consts
import connections.errors as errors
from connections.schema import Machine, Message, Request, Response
from utils import print_error


class ConnectionManager:
    """
    Handles the dirty work of opening sockets to the other machines.
    Abstracts to allow machines to operate at the level of sending
    messages based on machine name, ignoring underlying sockets.
    """

    def __init__(self, identity: Machine):
        self.identity = identity
        self.is_primary = False  # Is this the primary?
        self.living_siblings = consts.get_other_machines(identity.name)
        self.alive = True
        self.internal_lock = threading.Lock()
        self.internal_sockets: Mapping[str, any] = {}
        self.internal_requests: "Queue[Request]" = Queue()
        self.client_lock = threading.Lock()
        self.client_sockets: Mapping[str, any] = {}
        self.client_requests: "Queue[(str, Request)]" = Queue()

    def initialize(self):
        """
        Does the work of initializing the connection manager
        """
        # First it should establish connections to all other internal machines
        listen_thread = Thread(target=self.listen_internally)
        connect_thread = Thread(target=self.handle_internal_connections)
        listen_thread.start()
        connect_thread.start()
        listen_thread.join()
        connect_thread.join()

        # At this point we assume that self.internal_sockets is populated
        # with sockets to all other internal machines
        for (name, sock) in self.internal_sockets.items():
            # Be sure to consume with the internal flag set to True
            consumer_thread = Thread(
                target=self.consume_internally,
                args=(sock,)
            )
            consumer_thread.start()

        # Once all the servers are up we start doing health checks
        health_listen_thread = Thread(target=self.listen_health)
        health_listen_thread.start()
        health_probe_thread = Thread(target=self.probe_health)
        health_probe_thread.start()

        # Now we can setup another server socket to listen for connections from clients
        client_listen_thread = Thread(target=self.listen_externally)
        client_listen_thread.start()

    def listen_internally(self, sock=None):
        """
        Listens for incoming internal connections. Adds a connection to the socket
        map once connected, and repeats num_listens times.
        """
        # Setup the socket
        if not sock:
            # NOTE: The second parameter is only for unit testing purposes
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.identity.host_ip, self.identity.internal_port))
        sock.listen()
        # Listen the specified number of times
        listens_completed = 0
        while listens_completed < self.identity.num_listens:
            # Accept the connection
            conn, _ = sock.accept()
            # Get the name of the machine that connected
            name = conn.recv(1024).decode()
            # Add the connection to the map
            with self.internal_lock:
                self.internal_sockets[name] = conn
            listens_completed += 1
        sock.close()

    def listen_externally(self):
        """
        Listens for incoming external connections. Adds a connection to the socket
        map once connected, and repeats indefinitely
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.identity.host_ip, self.identity.client_port))
        sock.listen()
        # Listen the specified number of times
        while self.alive:
            # Accept the connection
            conn, _ = sock.accept()
            name = conn.getpeername()
            name = str(name[1])
            with self.client_lock:
                self.client_sockets[name] = conn
            client_thread = Thread(
                target=self.handle_client, args=(name,))
            client_thread.start()
        sock.close()

    def listen_health(self):
        """
        Listens for incoming health checks, responds with okay
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.identity.host_ip, self.identity.health_port))
        sock.listen()
        while self.alive:
            conn, _ = sock.accept()
            conn.recv(1024)
            conn.send("OK".encode())
            conn.close()

    def probe_health(self):
        """
        Sends a health check to every sibling every second
        """
        FREQUENCY = 2  # seconds
        time.sleep(FREQUENCY)
        while self.alive:
            print(self.identity.name, "is alive")
            for sibling in self.living_siblings:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(FREQUENCY)
                try:
                    sock.connect((sibling.host_ip, sibling.health_port))
                    sock.send("OK".encode())
                    sock.recv(1024)
                    sock.close()
                except:
                    print_error(f"Machine {sibling.name} is dead")
                    self.living_siblings.remove(sibling)
            self.is_primary = consts.should_i_be_primary(
                self.identity.name, self.living_siblings)
            time.sleep(FREQUENCY)

    def connect_internally(self, name: str):
        """
        Connects to the machine with the given name
        NOTE: Can/is expected to sometimes throw errors
        """
        # Get the identity of the machine to connect to
        if name not in consts.MACHINE_MAP:
            print_error(f"Machine {name} is not in the identity map")
            print_error("Please recheck your configuration and try again")
            raise (errors.MachineNotFoundException("Invalid machine name"))
        identity = consts.MACHINE_MAP[name]
        # Setup the socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((identity.host_ip, identity.internal_port))
        # Send the name of this machine
        sock.send(self.identity.name.encode())
        # Add the connection to the map
        self.internal_sockets[name] = sock

    def consume_internally(self, conn):
        """
        Once a connection is established, open a thread that continuously
        listens for incoming requests
        """
        try:
            # NOTE: The use of timeout here is to ensure that we can
            # gracefully kill machines. Essentially the machine will check
            # in once a second to make sure it hasn't been killed, instead
            # of listening forever.
            while True:
                # Get the message
                msg = conn.recv(2048).decode()
                if not msg or len(msg) <= 0:
                    raise Exception("Connection closed")
                req_obj = Request.unmarshal(msg)
                print(f"Received {req_obj.type} from sibling")
                self.internal_requests.put(req_obj)
        except Exception:
            conn.close()

    def handle_internal_connections(self):
        """
        Handles the connections to other machines
        """
        # Connect to the machines in the connection list
        for name in self.identity.connections:
            connected = False
            while not connected:
                try:
                    self.connect_internally(name)
                    connected = True
                except Exception:
                    print_error(
                        f"Failed to connect to {name}, retrying in 1 second")
                    time.sleep(1)

    def handle_client(self, name):
        """
        Handles a client connection
        """
        with self.client_lock:
            conn = self.client_sockets[name]
        while True:
            try:
                msg = conn.recv(2048).decode()
                if not msg or len(msg) <= 0:
                    continue
                req_obj = Request.unmarshal(msg)
                print(
                    f"Machine {self.identity.name} received {msg} from client {name} (type {req_obj.type})")
                self.client_requests.put((name, req_obj))
            except Exception as e:
                print(f"Got error in handle_client: {e}")
                conn.close()
                return

    def broadcast_to_backups(self, req: Request):
        """
        Takes care of state-updates.
        NOTE: We let this be called on any kind of request, but notice
        that we only have to actually do stuff on account changes or messages
        NOTE: If this machine does not have `is_primary` we'll do nothing
        """
        print("in broadcast")
        if not self.is_primary:
            return
        if req.type in ["list", "logs"]:
            return
        print(f"sending {req.type} to", [s.name for s in self.living_siblings])
        for sibling in self.living_siblings:
            self.internal_sockets[sibling.name].send(req.marshal().encode())

    def send_response(self, client_name, resp: Response):
        """
        Sends a response to a client
        """
        if client_name not in self.client_sockets:
            print_error(f"Client {client_name} is not connected")
            return
        self.client_sockets[client_name].send(resp.marshal().encode())

    def request_generator(self):
        """
        Generates client requests from the queue
        """
        while True:
            yield self.client_requests.get()

    def kill(self):
        """
        Kills the connection manager
        """
        self.alive = False
        for sock in list(self.internal_sockets.values()) + self.client_sockets:
            # Helps prevent the weird "address is already in use" error
            try:
                sock.shutdown(1)
            except Exception:
                # Makes sure that we at least close every socket
                pass
            sock.close()
