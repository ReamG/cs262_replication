import time
import socket
import threading
from typing import Mapping
from queue import Queue
from threading import Thread
import connections.consts as consts
import connections.errors as errors
from connections.schema import Machine, Request, Response, PingResponse
from utils import print_msg_box

LEXOGRAPHIC = [consts.MACHINE_A, consts.MACHINE_B, consts.MACHINE_C]


class ClientConnector():
    """
    On the client side, handles the dirty work of connecting to the server and
    doing things like sending/receiving requests, sending keep alives, and
    adapting when the primary goes down.
    """

    def __init__(self):
        self.iconn = None  # Interactive connection, for sending requests and getting responses
        self.sconn = None  # Subscription connection, for receiving notifs only
        self.primary_identity = None
        self.ix = 0

        # Loop through the servers in lexographic order and try to connect
        self.attempt_connection()

    def attempt_connection(self):
        """
        Attempts to connect to the server at the given host and port.
        """

        while not self.iconn:
            self.primary_identity = LEXOGRAPHIC[self.ix]
            try:
                self.iconn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.iconn.connect((self.primary_identity.host_ip,
                                    self.primary_identity.client_port))
                data = self.iconn.recv(2048)
                resp = Response.unmarshal(data.decode())
                if not resp.success:
                    raise ValueError("Server is not primary")
                    self.iconn = None
            except Exception as e:
                self.iconn = None
            self.ix = (self.ix + 1) % len(LEXOGRAPHIC)

    def ping_server(self):
        """
        Makes sure the server is still there
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.connect((self.primary_identity.host_ip,
                         self.primary_identity.health_port))
            ping = PingResponse()
            sock.send(ping.marshal().encode())
            sock.recv(2048)
            sock.close()
            return True
        except:
            return False

    def send_request(self, req: Request):
        """
        Sends a request to the server.
        NOTE: Hangs, does not return until a response has been sent
        """
        try:
            self.iconn.send(req.marshal().encode())
            data = self.iconn.recv(2048)
            if not data:
                raise Exception("Server closed connection")
            response = Response.unmarshal(data.decode())
            if response == None:
                raise Exception("Bad response")
            return response
        except Exception as e:
            self.iconn.close()
            self.iconn = None
            self.attempt_connection()
            return self.send_request(req)

    def watch_chats(self, conn):
        """
        Will do receives on this connection until it dies, expecting
        all data received to be of the form of NotifResponse
        """
        try:
            while True:
                data = conn.recv(2048)
                if not data or len(data) <= 0:
                    raise Exception("Server closed connection")
                resp = Response.unmarshal(data.decode())
                if resp.type not in ["notif", "ping"] or not resp.success:
                    raise Exception("Bad response")
                if resp.type == "notif":
                    print_msg_box(resp.chat)
                ping = PingResponse()
                conn.send(ping.marshal().encode())
        except Exception as e:
            conn.close()

    def subscribe(self, user_id):
        """
        Spins up a tread in the background to listen for notifs
        NOTE: If the user is already logged in, will return False
        and not listen to messages (client should show this)
        NOTE: Returns True on success
        """
        if not self.primary_identity:
            return False
        try:
            self.sconn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sconn.connect((self.primary_identity.host_ip,
                                self.primary_identity.notif_port))
            self.sconn.send(user_id.encode())
            data = self.sconn.recv(2048)
            resp = Response.unmarshal(data.decode())
            if not resp.success:
                raise Exception("Subscription failed")
            watcher = Thread(target=self.watch_chats, args=(self.sconn,))
            watcher.start()
            return True
        except Exception as e:
            return False

    def kill(self):
        if self.iconn:
            self.iconn.close()
        if self.sconn:
            self.sconn.close()
