from typing import List


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
        # The number of connections the machine should listen for
        self.num_listens = num_listens
        # The names of the machines that this machine should connect to
        self.connections = connections


class Message:
    """
    A class that represents a message passed between two internal machines
    """

    def __init__(self, author: str, payload: str):
        self.author = author
        self.payload = payload

    @staticmethod
    def from_string(rep: str):
        """
        Parses a string into a Message object. Used for unmarshalling after
        receiving data over the socket.
        NOTE: Given the simplicity of messages, it really is as simple as just
        splitting at the first :: and requiring that machine names not include
        the string "@@"
        """
        parts = rep.split("@@")
        return Message(author=parts[0], payload=parts[1])

    def __str__(self):
        """
        Turns a message object into a string. Used for marshalling before
        sending data over the socket.
        """
        return f"{self.author}@@{self.payload}"

    def __eq__(self, obj: object) -> bool:
        """
        Helper function for testing to determine whether messages are
        equivalent.
        """
        return isinstance(obj, Message) and self.author == obj.author and self.payload == obj.payload


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
        if req_type == "list":
            wildcard = parts[2]
            page = int(parts[3])
            return ListRequest(user_id, wildcard, page)
        elif req_type == "send":
            recipient_id = parts[2]
            text = parts[3]
            return SendRequest(user_id, recipient_id, text)
        else:
            return Request(user_id)


class ListRequest(Request):
    """
    A request to list all messages that match a wildcard
    """

    def __init__(self, user_id, wildcard, page):
        super().__init__(user_id)
        self.type = "list"
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
            accounts = parts[4:]
            accounts = ListResponse.unmarshal_accounts(accounts)
            return ListResponse(user_id, success, error_message, accounts)
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
        return "##".join(accounts)

    @staticmethod
    def unmarshal_accounts(accounts):
        return accounts.split("##")

    def marshal(self):
        return f"{self.user_id}@@{self.type}@@{self.success}@@{self.error_message}@@{ListResponse.marshal_accounts(self.accounts)}"
