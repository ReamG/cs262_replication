import time
import socket
import threading
from typing import Mapping
from queue import Queue
from threading import Thread
import connections.consts as consts
import connections.errors as errors
from connections.schema import Machine, Message, Request, Response
from utils import print_error

LEXOGRAPHIC = [consts.MACHINE_A, consts.MACHINE_B, consts.MACHINE_C]


class ClientConnector():
    """
    On the client side, handles the dirty work of connecting to the server and
    doing things like sending/receiving requests, sending keep alives, and
    adapting when the primary goes down.
    """

    def __init__(self):
        self.iconn = None
        self.wconn = None
        self.primary_identity = None

        # Loop through the servers in lexographic order and try to connect
        ix = 0
        while not self.iconn:
            self.primary_identity = LEXOGRAPHIC[ix]
            self.attempt_connection()
            ix = (ix + 1) % len(LEXOGRAPHIC)

    def attempt_connection(self):
        """
        Attempts to connect to the server at the given host and port.
        """
        try:
            self.iconn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.iconn.connect((self.primary_identity.host_ip,
                                self.primary_identity.client_port))
        except Exception as e:
            self.iconn = None

    def send_request(self, req: Request):
        """
        Sends a request to the server.
        NOTE: Hangs, does not return until a response has been sent
        """
        try:
            print(req.marshal())
            self.iconn.send(req.marshal().encode())
            data = self.iconn.recv(2048)
            if not data:
                raise Exception("Server closed connection")
            response = Response.unmarshal(data.decode())
            return response
        except Exception as e:
            print(e.args)
            print("Bad stuff")
            return None

    def kill(self):
        if self.iconn:
            self.iconn.close()
        if self.wconn:
            self.wconn.close()

    """
    def watch_messages(self):
        A function that will be run in a separate thread to watch for messages
        NOTE: Takes advantage of the ThreadPoolExecutor to run this function
        while True:
            message = coding.marshal_get_request(schema.Request(self.user_id))
            self.wsocket.sendall(message)
            data = self.wsocket.recv(1024)
            if not data:
                raise Exception("Server closed connection")
            message = coding.unmarshal_response(data)
            if message.success:
                utils.print_msg_box(message)
            time.sleep(1)
    """

    """
    def subscribe(self):
        Subscribe to the server to receive messages
        if not self.is_logged_in() or not self.executor or not self.isocket:
            utils.print_error(
                "Error: Something has gone wrong. You may need to restart your client")
            return
        self.wsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.wsocket.connect((self.host, self.port))
        self.executor.submit(self.watch_messages)
    """
