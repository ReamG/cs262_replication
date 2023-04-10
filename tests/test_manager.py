import sys
sys.path.append("..")
import connections.schema as conn_schema
import connections.consts as consts
import schema as data_schema
from tests.mocks.mock_socket import socket
from connections.manager import ConnectionManager
from queue import Queue


A = consts.MACHINE_A
B = consts.MACHINE_B
C = consts.MACHINE_C

def DUMMY_FUNC(*args):
    pass

def QUEUE_FUNC():
    queue = Queue()
    def func(*args):
        queue.put(args)
    return (queue, func)

def test_init():
    """
    Right stuff gets set
    """
    conman = ConnectionManager(A)

    assert conman.identity == A
    assert conman.is_primary == False
    assert [sib.name for sib in conman.living_siblings] == ["B", "C"]
    assert conman.alive

def test_initialize():
    """
    Ensure that it does the right things to connect to the other machines
    """
    progress = 3
    
    conman = ConnectionManager(A)
    conman.listen_internally = DUMMY_FUNC
    conman.handle_internal_connections = DUMMY_FUNC
    (catchup_queue, catchup_func) = QUEUE_FUNC()
    conman.play_catchup = catchup_func
    conman.connect_internally = DUMMY_FUNC
    conman.listen_health = DUMMY_FUNC
    conman.probe_health = DUMMY_FUNC
    conman.listen_externally = DUMMY_FUNC
    conman.initialize(progress, DUMMY_FUNC)
    
    assert conman.internal_progress["A"] == progress
    assert catchup_queue.get()[0] == DUMMY_FUNC

def test_listen_internally():
    """
    Ensure that it starts a thread that listens for connections.
    Also ensure that on connection it gets a name and a progress.
    """
    conman = ConnectionManager(A)
    dummy_sock = socket(0, 0) # Will be mocked by conftest.py
    dummy_sock.set_fake_accepts(["B@@1", "C@@6"])
    conman.internal_progress = { "A": 100 }
    conman.listen_internally(dummy_sock)

    assert dummy_sock.binded_to == (A.host_ip, A.internal_port)
    assert dummy_sock.has_listened
    assert dummy_sock.has_closed
    assert conman.internal_progress["B"] == 1
    assert conman.internal_progress["C"] == 6
    assert conman.internal_sockets["B"] != None
    assert conman.internal_sockets["C"] != None

def test_listen_externally():
    """
    Tests that a machine successfully listens for external connections
    """
    conman = ConnectionManager(A)
    dummy_sock = socket(0, 0)
    dummy_sock.set_fake_accepts(["A@@1"])
    conman.is_primary = True
    conman.handle_client = DUMMY_FUNC
    conman.listen_externally(dummy_sock)

    assert dummy_sock.binded_to == (A.host_ip, A.client_port)
    assert dummy_sock.has_listened
    assert len(conman.client_sockets) == 1

    dummy_sock.set_fake_accepts(["B@@1"])
    conman.is_primary = False
    conman.listen_externally(dummy_sock)
    assert len(conman.client_sockets) == 1

    
def test_listen_health():
    """
    Tests the heartbeat listener
    """
    conman = ConnectionManager(A)
    dummy_sock = socket(0, 0)
    dummy_sock.set_fake_accepts(["A@@1"])
    conman.is_primary = True
    conman.probe_health = DUMMY_FUNC
    conman.listen_health(dummy_sock)

    assert dummy_sock.binded_to == (A.host_ip, A.health_port)
    assert dummy_sock.has_listened

def test_probe_health():
    """
    Tests that machines ping each other and correctly adapt
    """
    conman = ConnectionManager(A)
    dummy_sock = socket(0, 0)
    conman.living_siblings = [B]
    
    # Without config, B should appear dead and be removed
    conman.probe_health(dummy_sock)
    assert conman.is_primary
    assert conman.living_siblings == []
    
    # From B's perspective, it should also claim primary
    conmanB = ConnectionManager(B)
    duummy_sock = socket(0, 0)
    conmanB.living_siblings = [A]
    conmanB.probe_health(dummy_sock)
    assert conmanB.is_primary
    assert conmanB.living_siblings == []

def test_connect_internally():
    """
    Makes sure that a machine connects to another machine
    """
    conman = ConnectionManager(B)
    dummy_sock = socket(0, 0)
    dummy_sock.add_fake_send("1")
    conman.connect_internally("A", 5, dummy_sock)

    assert dummy_sock.connected_to == (A.host_ip, A.internal_port)
    assert "A" in conman.internal_sockets
    assert conman.internal_progress["A"] == 1

def test_consumer_internally():
    """
    Tests that the internal consumer thread correctly receives messages
    """
    conman = ConnectionManager(A)
    dummy_sock = socket(0, 0)
    dummy_req = conn_schema.Request("user_id")
    dummy_sock.add_fake_send(dummy_req.marshal())
    conman.consume_internally(dummy_sock)

    assert dummy_sock.has_closed
    assert conman.internal_requests.get().marshal() == dummy_req.marshal()

def test_handle_internal_connections():
    """
    Tests that the machine will initiate all connections it is responsible for
    """
    conman = ConnectionManager(C)
    (internal_queue, internal_func) = QUEUE_FUNC()
    conman.connect_internally = internal_func
    conman.handle_internal_connections(6)

    assert internal_queue.get() == ("A", 6)
    assert internal_queue.get() == ("B", 6)
    assert internal_queue.empty()

def test_play_catchup():
    """
    Tests that machines will make the right requests to catch up
    and agree on persistent progress
    """
    conmanA = ConnectionManager(A)
    conmanB = ConnectionManager(B)
    conmanC = ConnectionManager(C)
    progress_map = {
        "A": 1,
        "B": 2,
        "C": 3
    }
    conmanA.internal_progress = progress_map
    conmanB.internal_progress = progress_map
    conmanC.internal_progress = progress_map

    (get_reqs_Q, get_reqs_F) = QUEUE_FUNC()
    def get_reqs_star(*args):
        get_reqs_F(*args)
        return []

    # C is the leader, it should call get_requests in right ways
    conmanC.internal_sockets = {
        "A": socket(0, 0),
        "B": socket(0, 0)
    }
    conmanC.play_catchup(get_reqs_star)
    assert get_reqs_Q.get() == (1, 3)
    assert get_reqs_Q.get() == (2, 3)

    # A should catch up and receive 2 requests
    Csock = socket(0, 0)
    conmanA.internal_sockets = {
        "C": Csock
    }
    dummy_req1 = conn_schema.Request("user_id")
    dummy_req2 = conn_schema.Request("user_id")
    Csock.add_fake_send(dummy_req1.marshal())
    Csock.add_fake_send(dummy_req2.marshal())
    conmanA.play_catchup(get_reqs_star)
    assert conmanA.internal_requests.get().marshal() == dummy_req1.marshal()
    assert conmanA.internal_requests.get().marshal() == dummy_req2.marshal()
    assert len(Csock.sent) == 2

def test_handle_client():
    """
    Tests that client connection is correctly used, both when primary
    and when not.
    """
    conman = ConnectionManager(A)

    # As primary
    conman.is_primary = True
    dummy_sock = socket(0, 0)
    conman.client_sockets["client_id"] = dummy_sock
    dummy_req = conn_schema.Request("client_id")
    dummy_sock.add_fake_send(dummy_req.marshal())
    conman.handle_client("client_id")
    assert conman.client_requests.get()[2].marshal() == dummy_req.marshal()

    # As backup
    conman.is_primary = False
    dummy_sock = socket(0, 0)
    conman.client_sockets["client_id"] = dummy_sock
    dummy_sock.add_fake_send(dummy_req.marshal())
    conman.handle_client("client_id")
    assert b"Not primary" in dummy_sock.sent[0]

def test_broadcast_to_backups():
    """
    Tests that requests get sent to backups
    """
    conman = ConnectionManager(A)
    conman.is_primary = True
    conman.living_siblings = [B, C]
    dummy_sock1 = socket(0, 0)
    dummy_sock2 = socket(0, 0)
    conman.internal_sockets = {
        "B": dummy_sock1,
        "C": dummy_sock2
    }
    dummy_req = conn_schema.Request("user_id")
    conman.broadcast_to_backups(dummy_req)
    assert dummy_sock1.sent[0].decode() == dummy_req.marshal()
    assert dummy_sock2.sent[0].decode() == dummy_req.marshal()

def test_send_response():
    """
    Tests that responses get sent to the right client
    """
    conman = ConnectionManager(A)
    dummy_sock = socket(0, 0)
    conman.client_sockets["client_id"] = dummy_sock
    dummy_resp = conn_schema.Response("client_id", True, "")
    conman.send_response("client_id", dummy_resp)
    assert dummy_sock.sent[0].decode() == dummy_resp.marshal()

def test_be_the_primary():
    """
    Tests that the machine serves out of client requests when
    it is the primary
    """
    conman = ConnectionManager(A)
    conman.is_primary = True
    dummy_req = conn_schema.Request("user_id")
    conman.client_requests.put(dummy_req)
    assert conman.be_the_primary() == dummy_req

def test_be_a_backup():
    """
    Tests that as a backup the machine will process until takeover,
    then return None
    """
    conman = ConnectionManager(B)
    conman.is_primary = False
    dummy_req = conn_schema.Request("user_id")
    takeover_req = conn_schema.TakeoverRequest()
    never_req = conn_schema.Request("nope")
    conman.internal_requests.put(dummy_req)
    conman.internal_requests.put(takeover_req)
    conman.client_requests.put(never_req)
    assert conman.be_a_backup() == (False, "", dummy_req)
    assert conman.be_a_backup() == None

def test_kill():
    """
    Tests that the machine will close all sockets and terminate
    """
    conman = ConnectionManager(A)
    dummy_sock1 = socket(0, 0)
    dummy_sock2 = socket(0, 0)
    conman.client_sockets["client_id"] = dummy_sock1
    conman.internal_sockets["B"] = dummy_sock2
    conman.kill()
    assert dummy_sock1.has_closed
    assert dummy_sock2.has_closed
    assert not conman.alive

