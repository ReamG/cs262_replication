# echo-client.py

import socket
import utils
import schema
import coding

from concurrent import futures

import pdb
import time

HOST = input("Enter Server Host Address: ")  # The server's hostname or IP address
PORT = 65432  # The port used by the server

class Client:
    """
    A bare-bones client that connects to a given host and port
    """
    def __init__(self, host, port, executor):
        self.host = host
        self.port = port
        self.executor = executor
        self.isocket = None # Interactive socket, used for sending requests and receiving responses
        self.wsocket = None # Watch socket, used for watching for messages ONLY
        self.user_id = ""

    def is_logged_in(self):
        """
        Helper function to check if the user is logged in
        NOTE: Intentionally simple application with no password,
        so this is indeed a correct proxy to status
        """
        return len(self.user_id) > 0
    
    def clear(self):
        """
        Clear the screen
        """
        if self.isocket:
            self.isocket.close()
            self.isocket = None
        if self.wsocket:
            self.wsocket.close()
            self.wsocket = None
        self.user_id = ""
    
    def watch_messages(self):
        """
        A function that will be run in a separate thread to watch for messages
        NOTE: Takes advantage of the ThreadPoolExecutor to run this function
        """
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

    def subscribe(self):
        """
        Subscribe to the server to receive messages
        """
        if not self.is_logged_in() or not self.executor or not self.isocket:
            utils.print_error("Error: Something has gone wrong. You may need to restart your client")
            return
        self.wsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.wsocket.connect((self.host, self.port))
        self.executor.submit(self.watch_messages)

    def handle_create(self):
        """
        Fails if the user is already logged in, they submit an empty username,
        or if the creation fails in expected way.
        NOTE: Expected to be run inside a safety_wrap
        """
        if self.is_logged_in():
            utils.print_error("You're already logged in as {}.".format(self.user_id))
            utils.print_error("Restart the client to create a different account")
            return
        username = input("> Enter a username: ")
        if len(username) <= 0:
            utils.print_error("Error: username cannot be empty")
            return
        if len(username) > 8:
            utils.print_error("Error: username cannot be longer than 8 characters")
            return
        if "," in username:
            utils.print_error("Error: username cannot contain commas")
            return
        message = coding.marshal_create_request(schema.Request(username))
        self.isocket.sendall(message)
        data = self.isocket.recv(1024)
        if not data:
            raise Exception("Error: Server closed connection")
        resp = coding.unmarshal_response(data)

        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        
        utils.print_success("Success! Account created")
        self.user_id = username
        self.subscribe()
    
    def handle_login(self):
        """
        Fails if the user is already logged in, they submit an empty username,
        or if the login fails in expected way.
        NOTE: Expected to be run inside a safety_wrap
        """
        if self.is_logged_in():
            utils.print_error("You're already logged in as {}.".format(self.user_id))
            utils.print_error("Restart the client to login to a different account")
            return
        username = input("> Enter a username: ")
        if len(username) <= 0:
            utils.print_error("Error: username cannot be empty")
            return
        message = coding.marshal_login_request(schema.Request(username))
        self.isocket.sendall(message)
        data = self.isocket.recv(1024)
        if not data:
            raise Exception("Error: Server closed connection")
        resp = coding.unmarshal_response(data)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_success("Success! Logged in as {}".format(username))
        self.user_id = username
        self.subscribe()
    
    def handle_delete(self):
        """
        Deletes the account of the currently logged in user
        """
        if not self.is_logged_in():
            utils.print_error("You must be logged in to delete an account.".format(self.user_id))
            return
        confirm = input("> Are you sure you want to delete your account? (y/n): ")
        if confirm != "y":
            utils.print_error("Aborting delete")
            return
        message = coding.marshal_delete_request(schema.Request(self.user_id))
        self.isocket.sendall(message)
        data = self.isocket.recv(1024)
        if not data:
            raise Exception("Error: Server closed connection")
        resp = coding.unmarshal_response(data)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_success("Success! Account deleted")
        self.user_id = ""
    
    def handle_list(self):
        """
        Takes a <= 8 character wildcard and a page number and returns a list of users
        NOTE: Must be logged in to list users
        """
        if not self.is_logged_in():
            utils.print_error("Error: You must be logged in to list users")
            return
        wildcard = input("> Input a text filter: ")
        if len(wildcard) > 8:
            utils.print_error("Error: wildcard cannot be longer than 8 characters")
            return
        page = input("> Input a page to return: ")
        page_int = None
        try:
            page_int = int(page)
        except:
            utils.print_error("Error: page must be an integer")
            return
        message = coding.marshal_list_request(schema.ListRequest(user_id=self.user_id, wildcard=wildcard, page=page_int))
        self.isocket.sendall(message)
        data = self.isocket.recv(1024)
        if not data:
            raise Exception("Error: Server closed connection")
        resp = coding.unmarshal_response(data)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_info("{} users on page {} matching '{}'".format(len(resp.accounts), page_int, wildcard))
        for user_id in resp.accounts:
            print(user_id)
    
    def handle_send(self):
        if not self.is_logged_in():
            utils.print_error("Error: You must be logged in to send a message")
            return
        recipient = input("> Recipient id: ")
        if len(recipient) <= 0:
            utils.print_error("Error: Recipient cannot be empty")
            return
        text = input("> What would you like to say?\n")
        if len(text) > 280:
            utils.print_error("Error: Message cannot be longer than 280 characters")
            return
        message = coding.marshal_send_request(schema.SendRequest(user_id=self.user_id, recipient_id=recipient, text=text))
        self.isocket.sendall(message)
        data = self.isocket.recv(1024)
        if not data:
            raise Exception("Error: Server closed connection")
        resp = coding.unmarshal_response(data)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_success("Success! Message sent")
    
    def handle_logs(self):
        if not self.is_logged_in():
            utils.print_error("Error: You must be logged in to list users")
            return
        wildcard = input("> Input a text filter: ")
        if len(wildcard) > 8:
            utils.print_error("Error: wildcard cannot be longer than 8 characters")
            return
        page = input("> Input a page to return: ")
        page_int = None
        try:
            page_int = int(page)
        except:
            utils.print_error("Error: page must be an integer")
            return
        message = coding.marshal_logs_request(schema.ListRequest(user_id=self.user_id, wildcard=wildcard, page=page_int))
        self.isocket.sendall(message)
        data = self.isocket.recv(1024)
        if not data:
            raise Exception("Error: Server closed connection")
        resp = coding.unmarshal_response(data)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_info("{} users on page {} matching '{}'".format(len(resp.accounts), page_int, wildcard))
        for user_id in resp.accounts:
            print(user_id)
        

    def parse_input(self, input_str):
        if input_str == "create":
            return self.handle_create
        elif input_str == "login":
            return self.handle_login
        elif input_str == "delete":
            return self.handle_delete
        elif input_str == "list":
            return self.handle_list
        elif input_str == "send":
            return self.handle_send
        elif input_str == "logs":
            return self.handle_logs
        else:
            utils.print_error("Error: Invalid command")
        return None

    def reconnect(self, initial=False):
        """
        Reconnects the socket to the server
        NOTE: Whenever we detect that the server has failed in an unexpected way,
        (i.e. not by sending a response with success=False) we will call this function.
        It resets all the sockets and logs the user out, not allowing them to do
        anything until they reconnect.
        """
        if not initial:
            utils.print_error("Error: Lost connection to server.")
            utils.print_error("You have been logged out. When/if connection is re-established, you will need to manually log back in.")
        multiplier = 1
        while True:
            try:
                self.isocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.isocket.connect((self.host, self.port))
                break
            except Exception:
                utils.print_error("Error: Unable to connect socket to server.")
                utils.print_error("Retrying in {} seconds".format(multiplier))
                time.sleep(multiplier)
                multiplier *= 2
        utils.print_success("Connected to server!")
    
    def is_in_good_health(self):
        if not self.isocket:
            return False
        if self.is_logged_in() and not self.wsocket:
            return False
        return True

    def start(self):
        self.reconnect(initial=True)
        while True:
            try:
                if not self.is_in_good_health():
                    self.reconnect()
                    continue
                raw_input = input("> Enter a command: ")
                if raw_input[:5] == "sleep":
                    # NOTE: Special logic to help with testing
                    time.sleep(int(raw_input[6:]))
                    continue
                handler = self.parse_input(raw_input)
                if handler:
                    handler()
            except Exception as e:
                if e.args[0] == "Error: Server closed connection":
                    self.clear()
                    continue
                if self.isocket:
                    self.isocket.close()
                    self.isocket = None
                if self.wsocket:
                    self.wsocket.close()
                    self.wsocket = None
                break

if __name__ == "__main__":
    executor = futures.ThreadPoolExecutor()
    client = Client(host=HOST, port=PORT, executor=executor)
    client.start()
