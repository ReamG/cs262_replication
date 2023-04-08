# echo-server.py

import socket
from concurrent import futures
import os
import sys
import time
import pdb
from threading import Lock, Event
from typing import List, Mapping
from queue import Queue
from schema import Account, Chat
import utils
import connections.consts as consts
import connections.schema as conn_schema
from connections.manager import ConnectionManager

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
        self.users = {}
        self.msg_log: Mapping[str, List[Chat]] = {}
        self.msg_cache: "Mapping[str, Queue[Chat]]" = {}
        self.alive = True
        self.rehydrate()

    def rehydrate(self):
        """
        Run when a server boots, it should read it's log and construct
        the state of the server (accounts and messages)
        """
        filename = f"logs/{self.name}_log.out"
        if not os.path.exists(filename):
            # No log file exists
            return
        with open(filename, "r") as file:
            for l in file.readlines():
                line = l.split("||")

                if line[0] == "account":
                    account = Account(user_id=line[1], is_logged_in=False)
                    self.users[account.user_id] = account
                elif line[0] == "chat":
                    chat = Chat(
                        author_id=line[1], recipient_id=line[2], text=line[3], success=(line[4][:-1] == "True"))
                    if chat.recipient_id not in self.users:
                        self.users[chat.recipient_id] = Account(
                            user_id=chat.recipient_id, is_logged_in=False)
                    if chat.recipient_id not in self.msg_log:
                        self.msg_log[chat.recipient_id] = []
                    self.users[chat.recipient_id].msg_log.append(chat)
                elif line[0] == "delete":
                    del self.users[line[1][:-1]]

    def update_log(self, item):
        """
        Add items to server log file
        """
        if not os.path.exists("logs"):
            os.mkdir("logs")
        fout = open(f"logs/{self.name}_log.out", "a")
        if type(item) == Account:
            fout.write(
                f"account||{item.user_id}||{item.is_logged_in}||{item.msg_log}\n")
        elif type(item) == Chat:
            fout.write(
                f"chat||{item.author_id}||{item.recipient_id}||{item.text}||{item.success}\n")
        elif type(item) == conn_schema.DeleteRequest:
            print("delete request")
            fout.write(f"delete||{item.user_id}\n")
        else:
            utils.print_error("Error: Invalid log item")
        fout.close()
        fout.close()

    def handle_create(self, request: conn_schema.CreateRequest):
        """
        Creates a new account. Fails if the user_id already exists.
        NOTE: Requires the user_lock to be held
        """
        if request.user_id in self.users:
            return conn_schema.Response(user_id=request.user_id, success=False, error_message="User already exists")
        new_account = Account(
            user_id=request.user_id, is_logged_in=True)
        self.update_log(new_account)
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
        if self.users[request.user_id].is_logged_in:
            return conn_schema.Response(user_id=request.user_id, success=False, error_message="User already logged in")
        self.users[request.user_id].is_logged_in = True
        return conn_schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_delete(self, request: conn_schema.DeleteRequest):
        """
        Deletes an existing account. Fails if the user_id does not exist.
        NOTE: Requires the user_lock to be held
        """
        if not request.user_id in self.users:
            return conn_schema.Response(user_id=request.user_id, success=False, error_message="User does not exist")
        # self.update_log(conn_schema.DeleteRequest(user_id=request.user_id))
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
            author_id=request.user_id, recipient_id=request.recipient_id, text=request.text, success=True)
        if not request.recipient_id in self.msg_cache:
            self.msg_cache[request.recipient_id] = Queue()
        self.msg_cache[request.recipient_id].put(chat)
        self.users[request.recipient_id].msg_log.insert(0, chat)
        self.update_log(chat)
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

    def start(self):
        request_iter = self.conman.request_generator()
        while True:
            (client_name, req) = next(request_iter)
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
            self.conman.broadcast_to_backups(req)
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
