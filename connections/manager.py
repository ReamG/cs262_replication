import time
import socket
import threading
from typing import Mapping
from queue import Queue
from threading import Thread
import connections.consts as consts
import connections.errors as errors
from connections.schema import Machine, Message, Request
from utils import print_error


class ConnectionManager:
    """
    Handles the dirty work of opening sockets to the other machines.
    Abstracts to allow machines to operate at the level of sending
    messages based on machine name, ignoring underlying sockets.
    """

    def __init__(self, identity: Machine):
        self.identity = identity
        self.internal_sockets: Mapping[str, any] = {}
        self.client_sockets = []
        self.alive = True
        self.internal_lock = threading.Lock()
        self.internal_msgs: "Queue[Message]" = Queue()
        self.client_lock = threading.Lock()
        self.client_requests: "Queue[Request]" = Queue()

    def initialize(self):
        """
        Does the work of initializing the connection manager
        """
        # First it should establish connections to all other internal machines
        listen_thread = Thread(target=self.listen_internally)
        connect_thread = Thread(target=self.handle_connections)
        listen_thread.start()
        connect_thread.start()
        listen_thread.join()
        connect_thread.join()
        # At this point we assume that self.internal_sockets is populated
        # with sockets to all other internal machines
        for (name, sock) in self.internal_sockets.items():
            # Be sure to consume with the internal flag set to True
            consumer_thread = Thread(
                target=self.consume,
                args=(sock, True)
            )
            consumer_thread.start()
        # Now we can setup another server socket to listen for connections from clients

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
            conn.close()
        sock.close()

    def connect(self, name: str):
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

    def consume(self, conn, is_internal: bool):
        """
        Once a connection is established, open a thread that continuously
        listens for incoming messages
        conn: connection object
        name: name of the machine that connected
        """
        try:
            # NOTE: The use of timeout here is to ensure that we can
            # gracefully kill machines. Essentially the machine will check
            # in once a second to make sure it hasn't been killed, instead
            # of listening forever.
            conn.settimeout(1)
            while True:
                try:
                    # Get the message
                    msg = conn.recv(2048).decode()
                    if not msg or len(msg) <= 0:
                        continue
                    if is_internal:
                        with self.internal_lock:
                            msg_obj = Message.from_string(msg)
                            self.internal_msgs.put(msg_obj)
                    else:
                        with self.client_lock:
                            req_obj = Request.from_string(msg)
                            self.client_requests.put(req_obj)
                except socket.timeout:
                    if not self.alive:
                        conn.close()
                        return
        except Exception:
            conn.close()

    def handle_connections(self):
        """
        Handles the connections to other machines
        """
        # Connect to the machines in the connection list
        for name in self.identity.connections:
            connected = False
            while not connected:
                try:
                    self.connect(name)
                    connected = True
                except Exception:
                    print_error(
                        f"Failed to connect to {name}, retrying in 1 second")
                    time.sleep(1)

    def handle_client(self, conn):
        """
        Handles a client connection
        """
        while True:
            if not self.alive:
                break
            break

    def send(self, to_machine: str, clock: int):
        """
        Sends a message to the machine with the given name
        """
        if to_machine not in self.internal_sockets:
            print_error(f"Machine {to_machine} is not connected")
            return
        msg = Message(self.identity.name, clock)
        self.internal_sockets[to_machine].send(str(msg).encode())

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
