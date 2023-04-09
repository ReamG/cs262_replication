import socket
import os
import sys
from threading import Lock
from typing import List, Mapping
from queue import Queue, Empty
from schema import Account, Chat
import connections.consts as consts
import connections.schema as conn_schema
from connections.manager import ConnectionManager
from threading import Thread

ACCOUNT_PAGE_SIZE = 4
LOG_PAGE_SIZE = 4


class Server:
    """
    A bare-bones server that listens for connections on a given host and port
    """

    def __init__(self, name):
        """
        Initialize the server
        """
        self.name = name
        if name not in consts.MACHINE_MAP:
            raise ValueError("Invalid machine name")
        self.identity = consts.MACHINE_MAP[name]  # Hosting info
        self.conman = ConnectionManager(self.identity)  # Connection manager
        self.conman.initialize()  # Connects to all other internal machines
        self.users = {}  # Users of the system NOTE: Also contains all chats that have ever happened
        # Chats that are undelivered
        self.msg_cache: "Mapping[str, Queue[Chat]]" = {}
        self.notif_lock = Lock()  # Make sure only one thread is changing notif_sockets
        self.notif_sockets: Mapping[str, any] = {}  # Sockets for notif threads
        self.alive = True
        self.rehydrate()
        notif_listen_thread = Thread(target=self.notif_listener)
        notif_listen_thread.start()  # Listen for clients that want notifications

    def get_logfile(self):
        return f"logs/{self.name}_log.out"

    def rehydrate(self):
        """
        Run when a server boots, it should read it's log and construct
        the state of the server (accounts and messages)
        """
        if not os.path.exists("logs"):
            os.mkdir("logs")
        filename = self.get_logfile()
        if not os.path.exists(filename):
            # If the file doesn't exist make a blank one
            with open(filename, "w") as file:
                file.write("")
        with open(filename, "r") as file:
            for l in file.readlines():
                req = conn_schema.Request.unmarshal(l[:-1])
                self.handle_req(req)

    def update_log(self, req: conn_schema.Request):
        """
        Add items to server log file
        """
        if req.type in conn_schema.UNIMPORTANT_REQUEST_TYPES:
            return
        filename = self.get_logfile()
        fout = open(filename, "a")
        fout.write(req.marshal() + "\n")
        fout.flush()
        fout.close()

    def notif_listener(self):
        """
        Handles connections from clients that have logged in and want
        immediate delivery of notifications
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.identity.host_ip, self.identity.notif_port))
        sock.listen()
        while self.alive:
            conn, _ = sock.accept()
            user_id = conn.recv(2048).decode()
            with self.notif_lock:
                if user_id in self.notif_sockets:
                    resp = conn_schema.Response(
                        user_id, False, "Already logged in")
                else:
                    resp = conn_schema.Response(user_id, True, "")
                    self.notif_sockets[user_id] = conn
            conn.send(resp.marshal().encode())
            handler = Thread(target=self.notif_thread, args=(user_id,))
            handler.start()

    def notif_thread(self, user_id: str):
        """
        A thread that is for a specific logged in user and does the
        instant delivery shenanigans
        """
        CHECK_IN_RATE = 3
        with self.notif_lock:
            if user_id not in self.notif_sockets:
                return
            conn = self.notif_sockets[user_id]
        try:
            while True:
                # NOTE: It can take up to 3 seconds for a logout to propogate
                # This is probably fine
                try:
                    msg = self.msg_cache[user_id].get(
                        block=True, timeout=CHECK_IN_RATE)
                except Empty:
                    # Send a ping regularly to see that client is still there
                    ping = conn_schema.PingResponse()
                    conn.send(ping.marshal().encode())
                    data = conn.recv(2048)
                    if not data or len(data) <= 0:
                        # If the ping fails we assume the client has died and we stop
                        raise Exception("Client not there")
                    resp = conn_schema.Response.unmarshal(data.decode())
                    if not resp.success:
                        # If the ping fails we assume the client has died and we stop
                        raise Exception("Client not there")
                    # If the ping succeeds go back to listening
                    continue
                req = conn_schema.NotifRequest(user_id)
                # Marks in the system that a message has been delivered
                self.update_log(req)
                # Lets the backups know about this so they have the same view of undelivered messages
                self.conman.broadcast_to_backups(req)
                # Gives the client the notif
                resp = conn_schema.NotifResponse(user_id, True, "", msg)
                conn.send(resp.marshal().encode())
        except Exception as e:
            print(f"got {user_id}s notif thread dying")
            print("notif thread died", e.args)
            # Error means the client has stopped listening on this thread
            # Clean up by deliting the socket from the map so that otehr clients
            # can connect using this username
            conn.close()
            with self.notif_lock:
                if user_id in self.notif_sockets:
                    del self.notif_sockets[user_id]

    def handle_create(self, request: conn_schema.CreateRequest):
        """
        Creates a new account. Fails if the user_id already exists.
        NOTE: Requires the user_lock to be held
        """
        if request.user_id in self.users:
            return conn_schema.Response(user_id=request.user_id, success=False, error_message="User already exists")
        new_account = Account(user_id=request.user_id)
        self.users[new_account.user_id] = new_account
        self.msg_cache[new_account.user_id] = Queue()
        return conn_schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_login(self, request: conn_schema.LoginRequest):
        """
        Logs in an existing account. Fails if the user_id does not exist or
        if the user is already logged in.
        NOTE: Requires the user_lock to be held
        """
        if not request.user_id in self.users:
            return conn_schema.Response(user_id=request.user_id, success=False, error_message="User does not exist")
        return conn_schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_delete(self, request: conn_schema.DeleteRequest):
        """
        Deletes an existing account. Fails if the user_id does not exist.
        NOTE: Requires the user_lock to be held
        """
        if not request.user_id in self.users:
            return conn_schema.Response(user_id=request.user_id, success=False, error_message="User does not exist")
        del self.users[request.user_id]
        del self.msg_cache[request.user_id]
        return conn_schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_list(self, request: conn_schema.ListRequest):
        """
        Lists all accounts that match the given wildcard.
        NOTE: "" will match all accounts. Other strings will simply use
        Python's built-in "in" operator.
        NOTE: Requires the user_lock to be held
        """
        satisfying = filter(
            lambda user: request.wildcard in user.user_id, self.users.values())
        limited_to_page = list(satisfying)[
            request.page * ACCOUNT_PAGE_SIZE: (request.page + 1) * ACCOUNT_PAGE_SIZE]
        return conn_schema.ListResponse(user_id=request.user_id, success=True, error_message="", accounts=limited_to_page)

    def handle_send(self, request):
        """
        Sends a message to the given user. If the user does not exist, return
        an error.
        """
        if not request.recipient_id in self.users:
            return conn_schema.Response(user_id=request.user_id, success=False, error_message="User does not exist")
        chat = Chat(
            author_id=request.user_id, recipient_id=request.recipient_id, text=request.text)
        if not request.recipient_id in self.msg_cache:
            self.msg_cache[request.recipient_id] = Queue()
        self.users[request.recipient_id].msg_log.insert(0, chat)
        return conn_schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_logs(self, request):
        """
        Returns a users message logs
        """
        with self.user_lock:
            msg_hist = self.users[request.user_id].msg_log
            satisfying = filter(
                lambda msg: request.wildcard in msg.author_id, msg_hist)
            limited_to_page = list(satisfying)[
                request.page * LOG_PAGE_SIZE: (request.page + 1) * LOG_PAGE_SIZE]
            return conn_schema.LogsResponse(user_id=request.user_id, success=True, error_message="", msgs=limited_to_page)

    def handle_req(self, req):
        if req.type == "create":
            resp = self.handle_create(req)
        elif req.type == "login":
            resp = self.handle_login(req)
        elif req.type == "list":
            resp = self.handle_list(req)
        elif req.type == "logs":
            resp = self.handle_logs(req)
        elif req.type == "send":
            resp = self.handle_send(req)
        elif req.type == "delete":
            resp = self.handle_delete(req)
        else:
            resp = conn_schema.Response(
                user_id=req.user_id, success=False, error_message="Invalid request type")
        return resp

    def start(self):
        request_iter = self.conman.request_generator()
        while True:
            (was_primary, client_name, req) = next(request_iter)
            resp = self.handle_req(req)
            # First, we update our own log
            if resp.success:
                self.update_log(req)
            # Then do primary specific stuff
            if was_primary:
                # Broadcast to backups
                if resp.success:
                    self.conman.broadcast_to_backups(req)
                    # Kind of hacky, but prevents a race condition that occurs
                    # because we are using built-in queues to do blocking
                    if req.type == "send":
                        chat = Chat(
                            author_id=req.user_id, recipient_id=req.recipient_id, text=req.text)
                        self.msg_cache[req.recipient_id].put(chat)
                self.conman.send_response(client_name, resp)

    def kill(self):
        self.alive = False
        self.conman.kill()


def create_server(name):
    server = Server(name=name)
    server.start()
    print("Server started")
    return server


if __name__ == "__main__":
    try:
        server = create_server(sys.argv[1])
    except KeyboardInterrupt:
        print("Shutting down server...")
