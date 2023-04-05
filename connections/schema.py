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
        host_port: int,
        num_listens: int,
        connections: List[str],
    ) -> None:
        # The name of the machine (in our experiments "A" | "B" | "C")
        self.name = name
        # The ip address the machine should listen on for new connections
        self.host_ip = host_ip
        # The port the machine should listen on for new connections
        self.host_port = host_port
        # The number of connections the machine should listen for
        self.num_listens = num_listens
        # The names of the machines that this machine should connect to
        self.connections = connections


class Message:
    """
    A class that represents a message passed between two machines
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
