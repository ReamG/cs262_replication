import sys
sys.path.append("..")
import connections.schema as conn_schema
import connections.consts as consts
import schema as data_schema
from tests.mocks.mock_socket import socket
from connections.connector import ClientConnector
from queue import Queue

def DUMMY_FUNC(*args):
    pass

def QUEUE_FUNC():
    queue = Queue()
    def func(*args):
        queue.put(args)
    return (queue, func)

def DUMMY_ATTEMPT(self):
    self.primary_identity = consts.MACHINE_A
    self.iconn = socket(0, 0)
    self.iconn.connect((self.primary_identity.host_ip, self.primary_identity.client_port))

def test_init():
    """
    Right stuff gets set
    """
    connector = ClientConnector(DUMMY_ATTEMPT)
    assert connector.primary_identity == consts.MACHINE_A
    assert connector.iconn
    assert connector.iconn.connected_to == (consts.MACHINE_A.host_ip, consts.MACHINE_A.client_port)
    
def test_attempt_connection():
    """
    Will loop through servers till receiving a true response on initial
    connect.
    """
    connector = ClientConnector(DUMMY_ATTEMPT)
    dummy_sock = socket(0, 0)
    bad_resp = conn_schema.Response("", False, None)
    good_resp = conn_schema.Response("", True, None)
    dummy_sock.add_fake_send(bad_resp.marshal())
    dummy_sock.add_fake_send(good_resp.marshal())
    connector.iconn = None
    connector.attempt_connection(dummy_sock)
    assert connector.ix == 2

def test_send_request():
    """
    Ensure that it sends the request and returns the response
    """
    connector = ClientConnector(DUMMY_ATTEMPT)
    dummy_sock = connector.iconn
    req = conn_schema.Request("test")
    resp = conn_schema.Response("test", True, "")
    dummy_sock.add_fake_send(resp.marshal())
    assert connector.send_request(req).marshal() == resp.marshal()

def test_watch_chats():
    """
    Ensure that it calls the callback on receiving a message
    """
    connector = ClientConnector(DUMMY_ATTEMPT)
    dummy_sock = connector.iconn
    chat = data_schema.Chat("auth", "recp", "mess")
    msg = conn_schema.NotifResponse("resp", True, "", chat)
    dummy_sock.add_fake_send(msg.marshal())
    connector.watch_chats(dummy_sock)
    assert len(dummy_sock.sent) == 1
    assert dummy_sock.has_closed
    
def test_subscribe():
    """
    Ensure that subscription works as expected, even when server isn't there/ready/primary
    """
    connector = ClientConnector(DUMMY_ATTEMPT)
    dummy_sock = connector.iconn
    req = conn_schema.Request("subscribe")
    resp = conn_schema.Response("subscribe", True, "")
    dummy_sock.add_fake_send(resp.marshal())
    assert not connector.subscribe("client_id")

def test_kill():
    """
    Ensure that it closes the connection
    """
    connector = ClientConnector(DUMMY_ATTEMPT)
    connector.kill()
    assert connector.iconn.has_closed