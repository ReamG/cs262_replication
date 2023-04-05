# echo-server.py

import socket
from concurrent import futures
import os
import sys
import time
import pdb
from threading import Lock, Event
import schema
import coding
import utils
import connections.consts as consts
from connections.manager import ConnectionManager

ACCOUNT_PAGE_SIZE = 4


class Server:
    """
    A bare-bones server that listens for connections on a given host and port
    """

    def __init__(self, name, executor):
        """
        Initialize the server
        """
        if name not in consts.MACHINE_MAP:
            raise ValueError("Invalid machine name")
        self.identity = consts.MACHINE_MAP[name]
        self.conman = ConnectionManager(self.identity)
        self.conman.initialize()
        self.others = consts.get_other_machines(name)
        self.executor = executor
        self.log_lock = Lock()
        self.users = {}
        self.msgs_cache = {}
        self.user_events = {}
        self.alive = True

        if os.path.isfile(f"logs/{self.host}_{self.port}_log.out"):
            with open(f"logs/{self.host}_{self.port}_log.out", "r") as file:
                for l in file.readlines():
                    line = l.split("||")

                    if line[0] == "account":
                        account = schema.Account(
                            user_id=line[1], is_logged_in=False)
                        self.users[account.user_id] = account
                    elif line[0] == "message":
                        message = schema.Message(
                            author_id=line[1], recipient_id=line[2], text=line[3], success=(line[4][:-1] == "True"))
                        self.users[message.recipient_id].msg_log.append(
                            message)
                    elif line[0] == "delete":
                        del self.users[line[1][:-1]]

    def update_log(self, item):
        """
        Add items to server log file
        """
        if not os.path.exists("logs"):
            os.mkdir("logs")
        self.fout = open(f"logs/{self.host}_{self.port}_log.out", "a")
        if type(item) == schema.Account:
            self.fout.write(
                f"account||{item.user_id}||{item.is_logged_in}||{item.msg_log}\n")
        elif type(item) == schema.Message:
            self.fout.write(
                f"message||{item.author_id}||{item.recipient_id}||{item.text}||{item.success}\n")
        elif type(item) == schema.DeleteRequest:
            print("delete request")
            self.fout.write(f"delete||{item.user_id}\n")
        else:
            utils.print_error("Error: Invalid log item")

        self.fout.close()

    def handle_create(self, request):
        """
        Creates a new account. Fails if the user_id already exists.
        NOTE: Requires the user_lock to be held
        """
        with self.user_lock:
            if request.user_id in self.users:
                return schema.Response(user_id=request.user_id, success=False, error_message="User already exists")
            new_account = schema.Account(
                user_id=request.user_id, is_logged_in=True)
            self.update_log(new_account)
            self.users[new_account.user_id] = new_account
            self.msgs_cache[new_account.user_id] = []
            self.user_events[new_account.user_id] = Event()
            return schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_login(self, request):
        """
        Logs in an existing account. Fails if the user_id does not exist or
        if the user is already logged in.
        NOTE: Requires the user_lock to be held
        """
        with self.user_lock:
            if not request.user_id in self.users:
                return schema.Response(user_id=request.user_id, success=False, error_message="User does not exist")
            if self.users[request.user_id].is_logged_in:
                return schema.Response(user_id=request.user_id, success=False, error_message="User already logged in")
            self.users[request.user_id].is_logged_in = True
        with self.msgs_lock:
            # On login make sure the event is set to true
            if len(self.msgs_cache[request.user_id]) > 0:
                self.user_events[request.user_id].set()
        return schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_delete(self, request):
        """
        Deletes an existing account. Fails if the user_id does not exist.
        NOTE: Requires the user_lock to be held
        """
        with self.user_lock:
            if not request.user_id in self.users:
                return schema.Response(user_id=request.user_id, success=False, error_message="User does not exist")
            # self.update_log(schema.DeleteRequest(user_id=request.user_id))
            del self.users[request.user_id]
            del self.msgs_cache[request.user_id]
            del self.user_events[request.user_id]
            return schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_list(self, request):
        """
        Lists all accounts that match the given wildcard.
        NOTE: "" will match all accounts. Other strings will simply use
        Python's built-in "in" operator.
        NOTE: Requires the user_lock to be held
        """
        with self.user_lock:
            satisfying = filter(
                lambda user: request.wildcard in user.user_id, self.users.values())
            limited_to_page = list(satisfying)[
                request.page * self.ACCOUNT_PAGE_SIZE: (request.page + 1) * self.ACCOUNT_PAGE_SIZE]
            return schema.ListResponse(user_id=request.user_id, success=True, error_message="", accounts=limited_to_page)

    def handle_get_messages(self, request):
        """
        Gets the messages for a given user
        """
        sending = None
        with self.msgs_lock:
            if len(self.msgs_cache[request.user_id]) > 0:
                sending = self.msgs_cache[request.user_id][0]
                self.msgs_cache[request.user_id] = self.msgs_cache[request.user_id][1:]
        if sending:
            return sending
        else:
            return schema.Message(author_id=request.user_id, recipient_id=request.user_id, text="", success=False)

    def handle_send(self, request):
        """
        Sends a message to the given user. If the user does not exist, return
        an error.
        """
        if not request.recipient_id in self.users:
            return schema.Response(user_id=request.user_id, success=False, error_message="User does not exist")
        message = schema.Message(
            author_id=request.user_id, recipient_id=request.recipient_id, text=request.text, success=True)
        with self.msgs_lock:
            self.msgs_cache[request.recipient_id].append(message)
            self.users[request.recipient_id].msg_log.insert(0, message)
            self.update_log(message)
        self.user_events[request.recipient_id].set()
        return schema.Response(user_id=request.user_id, success=True, error_message="")

    def handle_logs(self, request):
        """
        Returns a users message logs
        """
        with self.user_lock:
            msg_hist = self.users[request.user_id].msg_log
            satisfying = filter(
                lambda msg: request.wildcard in msg.author_id, msg_hist)
            limited_to_page = list(satisfying)[
                request.page * self.ACCOUNT_PAGE_SIZE: (request.page + 1) * self.ACCOUNT_PAGE_SIZE]
            return schema.ListResponse(user_id=request.user_id, success=True, error_message="", accounts=limited_to_page)

    def handle_request_with_op(self, request, op):
        """
        Just does the dirty work of matching the code to the handler func
        """
        if op == "create":
            return self.handle_create(request)
        if op == "login":
            return self.handle_login(request)
        if op == "delete":
            return self.handle_delete(request)
        if op == "get":
            return self.handle_get_messages(request)
        if op == "list":
            return self.handle_list(request)
        if op == "send":
            return self.handle_send(request)
        if op == "health":
            return schema.Response(user_id=request.user_id, success=True, error_message="")
        if op == "logs":
            return self.handle_logs(request)
        return None

    def handle_connection(self, conn, addr):
        print("New connection")
        user_id = ""
        while True:
            if not self.alive:
                break
            # Continue to receive data until the connection is closed
            try:
                data = conn.recv(1024)
                if not self.alive:
                    break
                if not data:
                    raise Exception("Client closed connection")
                try:
                    request, op = coding.unmarshal_request(data)
                except:
                    utils.print_error("Error: Invalid request")
                    continue
                resp = self.handle_request_with_op(request, op)
                if (op == "create" or op == "login") and resp.success:
                    user_id = request.user_id
                # Send back using the right encoding
                if op == "list":
                    data = coding.marshal_list_response(resp)
                if op == "logs":
                    data = coding.marshal_logs_response(resp)
                elif op == "get":
                    data = coding.marshal_message_response(resp)
                else:
                    data = coding.marshal_response(resp)
                try:
                    conn.sendall(data)
                except:
                    raise Exception("Client closed connection")
            except Exception as e:
                print("Error:", e.args[0])
                resp = schema.Response(
                    user_id=user_id, success=False, error_message=str(e.args[0]))
                data = coding.marshal_response(resp)
                if len(user_id) > 0:
                    self.users[user_id].is_logged_in = False
                    self.user_events[user_id].set()
                break
        conn.close()

    def start(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            while True:
                try:
                    if not self.alive:
                        break
                    conn, addr = s.accept()
                    if conn:
                        self.executor.submit(
                            self.handle_connection, conn, addr)
                except KeyboardInterrupt:
                    break
                except Exception:
                    pass


if __name__ == "__main__":
    try:
        executor = futures.ThreadPoolExecutor()
        name = sys.argv[1]
        server = Server(name=name, executor=executor)
        server.start()
    except KeyboardInterrupt:
        server.alive = False
        print("Shutting down server...")
