import pdb
import utils
from connections.connector import ClientConnector
import connections.schema as conn_schema
from concurrent import futures
import time
from threading import Thread


class Client:
    """
    A bare-bones client that connects to a given host and port
    """

    def __init__(self):
        self.connector = ClientConnector()
        ping_thread = Thread(target=self.ping_server)
        ping_thread.start()
        self.user_id = ""

    def is_logged_in(self):
        """
        Helper function to check if the user is logged in
        NOTE: Intentionally simple application with no password,
        so this is indeed a correct proxy to status
        """
        return len(self.user_id) > 0

    def ping_server(self):
        """
        Checks the primary regularly and relogs in if needed
        """
        FREQUENCY = 1
        time.sleep(FREQUENCY)
        while True:
            okay = self.connector.ping_server()
            if not okay:
                self.connector.attempt_connection()
                self.relogin()
            time.sleep(FREQUENCY)

    def handle_create(self):
        """
        Fails if the user is already logged in, they submit an empty username,
        or if the creation fails in expected way.
        NOTE: Expected to be run inside a safety_wrap
        """
        if self.is_logged_in():
            utils.print_error(
                "You're already logged in as {}.".format(self.user_id))
            utils.print_error(
                "Restart the client to create a different account")
            return
        username = input("> Enter a username: ")
        if len(username) <= 0:
            utils.print_error("Error: username cannot be empty")
            return
        if len(username) > 8:
            utils.print_error(
                "Error: username cannot be longer than 8 characters")
            return
        if "," in username:
            utils.print_error("Error: username cannot contain commas")
            return
        if "||" in username:
            utils.print_error("Error: username cannot contain \"||\"")
            return
        req = conn_schema.CreateRequest(username)
        resp = self.connector.send_request(req)

        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return

        utils.print_success("Success! Account created")

    def handle_login(self):
        """
        Fails if the user is already logged in, they submit an empty username,
        or if the login fails in expected way.
        NOTE: Expected to be run inside a safety_wrap
        """
        if self.is_logged_in():
            utils.print_error(
                "You're already logged in as {}.".format(self.user_id))
            utils.print_error(
                "Restart the client to login to a different account")
            return
        username = input("> Enter a username: ")
        if len(username) <= 0:
            utils.print_error("Error: username cannot be empty")
            return
        # First issue a login, which checks the user exists
        req = conn_schema.LoginRequest(username)
        resp = self.connector.send_request(req)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        # Then attempt to subscribe, which checks that no one else is logged in as this user
        sub_success = self.connector.subscribe(username)
        if not sub_success:
            utils.print_error(
                "Error: Another client is already logged in as {}".format(username))
            return
        utils.print_success("Success! Logged in as {}".format(username))
        self.user_id = username

    def handle_delete(self):
        """
        Deletes the account of the currently logged in user
        """
        if not self.is_logged_in():
            utils.print_error(
                "You must be logged in to delete an account.".format(self.user_id))
            return
        confirm = input(
            "> Are you sure you want to delete your account? (y/n): ")
        if confirm != "y":
            utils.print_error("Aborting delete")
            return
        req = conn_schema.DeleteRequest(self.user_id)
        self.relogin()
        resp = self.connector.send_request(req)
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
            utils.print_error(
                "Error: wildcard cannot be longer than 8 characters")
            return
        page = input("> Input a page to return: ")
        page_int = None
        try:
            page_int = int(page)
        except:
            utils.print_error("Error: page must be an integer")
            return
        req = conn_schema.ListRequest(self.user_id, wildcard, page_int)
        self.relogin()
        resp = self.connector.send_request(req)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_info("{} users on page {} matching '{}'".format(
            len(resp.accounts), page_int, wildcard))
        for account in resp.accounts:
            print(account.user_id)

    def relogin(self):
        if self.user_id == "":
            return
        username = self.user_id
        self.user_id = ""
        # First issue a login, which checks the user exists
        req = conn_schema.LoginRequest(username)
        resp = self.connector.send_request(req)
        # Then attempt to subscribe, which checks that no one else is logged in as this user
        self.connector.subscribe(username)
        self.user_id = username

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
            utils.print_error(
                "Error: Message cannot be longer than 280 characters")
            return
        if "||" in text:
            utils.print_error("Error: text cannot contain \"||\"")
            return
        if "@@" in text:
            utils.print_error("Error: text cannot contain \"@@\"")
            return
        req = conn_schema.SendRequest(self.user_id, recipient, text)
        self.relogin()
        resp = self.connector.send_request(req)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_success("Success! Message sent")

    def handle_logs(self):
        if not self.is_logged_in():
            utils.print_error("Error: You must be logged in to list logs")
            return
        wildcard = input("> Input a text filter: ")
        if len(wildcard) > 8:
            utils.print_error(
                "Error: wildcard cannot be longer than 8 characters")
            return
        page = input("> Input a page to return: ")
        page_int = None
        try:
            page_int = int(page)
        except:
            utils.print_error("Error: page must be an integer")
            return
        req = conn_schema.LogsRequest(self.user_id, wildcard, page_int)
        self.relogin()
        resp = self.connector.send_request(req)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_info("{} messages on page {} matching '{}'".format(
            len(resp.msgs), page_int, wildcard))
        for msg in resp.msgs:
            print(msg.pretty())

    def handle_fallover(self):
        req = conn_schema.FalloverRequest(self.user_id)
        resp = self.connector.send_request(req)
        if not resp.success:
            utils.print_error("Error: {}".format(resp.error_message))
            return
        utils.print_success("Success! Fallover initiated")

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
        elif input_str == "fallover":
            return self.handle_fallover
        else:
            utils.print_error("Error: Invalid command")
        return None

    def start(self):
        # try:
        while True:
            raw_input = input("> Enter a command: ")
            if raw_input[:5] == "sleep":
                # NOTE: Special logic to help with testing
                time.sleep(int(raw_input[6:]))
                continue
            handler = self.parse_input(raw_input)
            if handler:
                handler()


if __name__ == "__main__":
    executor = futures.ThreadPoolExecutor()
    client = Client()
    client.start()
