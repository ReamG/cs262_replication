import pdb
import schema as data_schema
from typing import List
import sys
sys.path.append("..")


class Machine:
    """
    A class that represents the identity of a machine. Most crucially
    this stores information about which ip/port the machine is listening
    on, as well as which other machines it is responsible for connecting
    to.
    """

    def __init__(
        self,
        name: str,
        host_ip: str,
        internal_port: int,
        client_port: int,
        health_port: int,
        notif_port: int,
        num_listens: int,
        connections: List[str],
    ) -> None:
        # The name of the machine (in our experiments "A" | "B" | "C")
        self.name = name
        # The ip address the machine should listen on for new connections
        self.host_ip = host_ip
        # The port the machine should listen on for connections from other machines
        self.internal_port = internal_port
        # The port the machine should listen on for connections to clients
        self.client_port = client_port
        # The port the machine should listen on for health checks
        self.health_port = health_port
        # The port the machine should listen on for notification sub requests
        self.notif_port = notif_port
        # The number of connections the machine should listen for
        self.num_listens = num_listens
        # The names of the machines that this machine should connect to
        self.connections = connections


IMPORTANT_REQUEST_TYPES = ["create", "send", "delete", "notif"]
UNIMPORTANT_REQUEST_TYPES = ["login", "list", "logs", "fallover"]
REQUEST_TYPES = IMPORTANT_REQUEST_TYPES + UNIMPORTANT_REQUEST_TYPES


class Request:
    """
    A base class for all requests from client -> server
    """

    def __init__(self, user_id):
        self.user_id = user_id
        self.type = "blank"

    def marshal(self):
        return f"{self.user_id}@@{self.type}"

    @staticmethod
    def unmarshal(rep):
        parts = rep.split("@@")
        user_id = parts[0]
        req_type = parts[1]
        if req_type == "login":
            return LoginRequest(user_id)
        elif req_type == "create":
            return CreateRequest(user_id)
        elif req_type == "list":
            wildcard = parts[2]
            page = int(parts[3])
            return ListRequest(user_id, wildcard, page)
        elif req_type == "logs":
            wildcard = parts[2]
            page = int(parts[3])
            return LogsRequest(user_id, wildcard, page)
        elif req_type == "send":
            recipient_id = parts[2]
            text = parts[3]
            return SendRequest(user_id, recipient_id, text)
        elif req_type == "notif":
            return NotifRequest(user_id)
        elif req_type == "delete":
            return DeleteRequest(user_id)
        elif req_type == "fallover":
            return FalloverRequest(user_id)
        else:
            return Request(user_id)


class CreateRequest(Request):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.type = "create"

    def marshal(self):
        return f"{self.user_id}@@{self.type}"


class FalloverRequest(Request):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.type = "fallover"

    def marshal(self):
        return f"{self.user_id}@@{self.type}"


class LoginRequest(Request):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.type = "login"

    def marshal(self):
        return f"{self.user_id}@@{self.type}"


class ListRequest(Request):
    """
    A request to list all users that match a wildcard
    """

    def __init__(self, user_id, wildcard, page):
        super().__init__(user_id)
        self.type = "list"
        self.wildcard = wildcard
        self.page = page

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.wildcard}@@{self.page}"


class LogsRequest(Request):
    """
    A request to list all messages that match a wildcard
    """

    def __init__(self, user_id, wildcard, page):
        super().__init__(user_id)
        self.type = "logs"
        self.wildcard = wildcard
        self.page = page

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.wildcard}@@{self.page}"


class SendRequest(Request):
    """
    A request to send a message to a user
    """

    def __init__(self, user_id, recipient_id, text):
        super().__init__(user_id)
        self.type = "send"
        self.recipient_id = recipient_id
        self.text = text

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.recipient_id}@@{self.text}"


class DeleteRequest(Request):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.type = "delete"

    def marshal(self):
        return f"{self.user_id}@@{self.type}"


class TakeoverRequest(Request):
    """
    Not really an actual request, just a class that can be put on the internal
    queue to help a server signal to itself that it should take over the
    primary role
    """

    def __init__(self):
        super().__init__("")
        self.type = "takeover"


class NotifRequest(Request):
    """
    A request by a user to get one message from their cache
    """

    def __init__(self, user_id):
        super().__init__(user_id)
        self.type = "notif"

    def marshal(self):
        return f"{self.user_id}@@{self.type}"


class Response:
    """
    A base class for all responses from server -> client
    """

    def __init__(self, user_id, success, error_message):
        self.user_id = user_id
        self.success = success
        self.error_message = error_message
        self.type = "basic"

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.success}@@{self.error_message}"

    @staticmethod
    def unmarshal(rep):
        parts = rep.split("@@")
        user_id = parts[0]
        resp_type = parts[1]
        success = parts[2] == "True"
        error_message = parts[3]
        if resp_type == "list":
            accounts = parts[4]
            accounts = ListResponse.unmarshal_accounts(accounts)
            return ListResponse(user_id, success, error_message, accounts)
        elif resp_type == "logs":
            if len(parts) < 5 or parts[4] == "":
                msgs = []
            else:
                msgs = LogsResponse.unmarshal_msgs(parts[4])
            return LogsResponse(user_id, success, error_message, msgs)
        elif resp_type == "notif":
            author_id = parts[4]
            recipient_id = parts[5]
            text = parts[6]
            chat = data_schema.Chat(author_id, recipient_id, text)
            return NotifResponse(user_id, success, error_message, chat)
        elif resp_type == "ping":
            return PingResponse()
        else:
            return Response(user_id, success, error_message)


class ListResponse(Response):
    """
    A response to a ListRequest
    """

    def __init__(self, user_id, success, error_message, accounts):
        super().__init__(user_id, success, error_message)
        self.accounts = accounts
        self.type = "list"

    @staticmethod
    def marshal_accounts(accounts):
        as_strs = [a.marshal() for a in accounts]
        return "##".join(as_strs)

    @staticmethod
    def unmarshal_accounts(accounts):
        str_list = accounts.split("##")
        return [data_schema.Account.unmarshal(a) for a in str_list]

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.success}@@{self.error_message}@@{ListResponse.marshal_accounts(self.accounts)}"


class LogsResponse(Response):
    """
    A response to a LogsRequest
    """

    def __init__(self, user_id, success, error_message, msgs):
        super().__init__(user_id, success, error_message)
        self.msgs = msgs
        self.type = "logs"

    @staticmethod
    def marshal_msgs(msgs):
        return "##".join([msg.marshal("||") for msg in msgs])

    @staticmethod
    def unmarshal_msgs(msgs):
        arr = msgs.split("##")
        return [data_schema.Chat.unmarshal(el, "||") for el in arr]

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.success}@@{self.error_message}@@{LogsResponse.marshal_msgs(self.msgs)}"


class NotifResponse(Response):
    """
    A response to a NotifRequest
    """

    def __init__(self, user_id, success, error_message, chat: data_schema.Chat):
        super().__init__(user_id, success, error_message)
        self.type = "notif"
        self.chat = chat

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.success}@@{self.error_message}@@{self.chat.marshal()}"


class PingResponse(Response):
    """
    A response that just lets the server know this client is alive
    """

    def __init__(self, user_id=""):
        super().__init__(user_id, True, "")
        self.type = "ping"

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.success}@@{self.error_message}"
