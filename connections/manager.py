import time
import socket
import threading
import pdb
from typing import Mapping
from queue import Queue
from threading import Thread
import connections.consts as consts
import connections.errors as errors
from connections.schema import UNIMPORTANT_REQUEST_TYPES, Machine, Request, Response, TakeoverRequest, NotifResponse, PingResponse
from utils import print_error, print_info


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
            name = conn.recv(2048).decode()
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
        Listens for incoming health checks, responds with PingResponse
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.identity.host_ip, self.identity.health_port))
        sock.listen()
        while self.alive:
            conn, _ = sock.accept()
            conn.recv(2048)
            resp = PingResponse()
            conn.send(resp.marshal().encode())
            conn.close()

    def probe_health(self):
        """
        Sends a health check to every sibling regularly
        """
        FREQUENCY = 2  # seconds
        time.sleep(FREQUENCY)
        while self.alive:
            for sibling in self.living_siblings:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(FREQUENCY)
                try:
                    sock.connect((sibling.host_ip, sibling.health_port))
                    ping = PingResponse()
                    sock.send(ping.marshal().encode())
                    sock.recv(2048)
                    sock.close()
                except:
                    print_error(f"Machine {sibling.name} is dead")
                    self.living_siblings.remove(sibling)
            old_primary_status = self.is_primary
            self.is_primary = consts.should_i_be_primary(
                self.identity.name, self.living_siblings)
            if self.is_primary and not old_primary_status:
                print_info(f"Machine {self.identity.name} is now primary!")
                # Self-trigger an internal request to free control
                takeover_req = TakeoverRequest()
                self.internal_requests.put(takeover_req)
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
                    raise Exception("Connection closed")
                req_obj = Request.unmarshal(msg)
                # If this machine is not the primary, respond with an appropriate error
                if not self.is_primary:
                    resp = Response("", False, "Error: Not primary")
                    conn.send(resp.marshal().encode())
                    continue
                self.client_requests.put((True, name, req_obj))
            except socket.timeout:
                continue
            except Exception as e:
                conn.close()
                with self.client_lock:
                    del self.client_sockets[name]
                return

        """
    def handle_notif(self, user_id):
        Handles a clients subscription to notifications (login state)
        with self.notif_lock:
            conn = self.notif_sockets[user_id]
        while True:
            try:
                msg = conn.recv(2048).decode()
                if not msg or len(msg) <= 0:
                    raise Exception("Connection closed")
                req_obj = Request.unmarshal(msg)
                # Make sure it's a notif request
                if req_obj.type != "notif":
                    resp = Response("", False, "Error: Not a notif request")
                # Make sure this machine is the primary
                if not self.is_primary:
                    resp = Response("", False, "Error: Not primary")
                    conn.send(resp.marshal().encode())
                    continue
                # Blocks until a new message
                chat = self.msg_cache[user_id].get()
                # Try to send the chat
                # if it succeeds, great
                # if not, add it back to the beginning of the queue
                resp = NotifResponse(user_id, True, "", chat)
                conn.send(resp.marshal().encode())
            except socket.timeout:
                continue
            except Exception as e:
                conn.close()
                with self.notif_lock:
                    del self.notif_sockets[user_id]
                return
        """

    def broadcast_to_backups(self, req: Request):
        """
        Takes care of state-updates.
        NOTE: We let this be called on any kind of request, but notice
        that we only have to actually do stuff on account changes or messages
        NOTE: If this machine does not have `is_primary` we'll do nothing
        """
        if not self.is_primary:
            return
        if req.type in UNIMPORTANT_REQUEST_TYPES:
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

    def be_the_primary(self):
        """
        Function to continuously get requests from client and yield them
        """
        req = self.client_requests.get()
        return req

    def be_a_backup(self):
        """
        Function to return state-updates from the primary until it becomes
        the primary, at which point it returns None
        """
        req = self.internal_requests.get()
        if req.type == "takeover":
            return None
        # Represents (was_primary=False, client_name="", request=req)
        return (False, "", req)

    def request_generator(self):
        """
        Every client starts being a backup. Once the health check determines
        that they should be the new primary, a "dummy" takeover request is
        triggered which causes be_a_backup to yield None, at which point we
        switch to be_the_primary and operate as normal until we die
        """
        while True:
            req = self.be_a_backup()
            if req is None:
                break
            yield req
        while True:
            yield self.be_the_primary()

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
