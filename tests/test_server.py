import unittest
import sys

try:
    del sys.modules["server"]
except:
    pass
from threading import Lock
from typing import List, Mapping
sys.path.insert(0, "..")
import server
import connections.schema 
import schema
import client
import threading
import ctypes
from concurrent import futures
import os

# Make server class start indepedent of connecting to backup servers
class Server_dummy(server.Server):
    def __init__(self, name):
        ###### CONSTANTS ######
        self.name = name
        MACHINE_A = connections.schema.Machine(
            name="A",
            host_ip="localhost",
            internal_port=50051,
            client_port=50052,
            health_port=50053,
            notif_port=50054,
            num_listens=2,
            connections=[]
        )
        self.identity = MACHINE_A  # Hosting info
        # Bring myself up to date with info I have locally
        self.users = {}  # Users of the system NOTE: Also contains all chats that have ever happened
        # Chats that are undelivered
        self.msg_cache: "Mapping[str, Queue[Chat]]" = {}
        self.notif_lock = Lock()  # Make sure only one thread is changing notif_sockets
        self.notif_sockets: Mapping[str, any] = {}  # Sockets for notif threads
        self.alive = True

        #ACTIONS
        self.rehydrate()

class Test_server(unittest.TestCase):
    """Test class for our server code"""

    def delete_log(self):
        """Deletes log file"""
        try:
            os.remove("logs/A_log.out")
        except:
            pass

    def test_handle_create(self):

        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')

        # Ensure server starts with no users
        assert len(server_a.users) == 0

        # Ensure user is added to user list when receiving create request object
        req = connections.schema.CreateRequest(user_id="ream")
        server_a.handle_create(req, True)
        assert len(server_a.users) == 1

        # Ensure that error message is returned when user tries to create existing username and phantom user is not created
        out = server_a.handle_create(req, True)
        assert not out.success
        assert len(server_a.users) == 1

    
    def test_Login(self):
        
        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')

        
        # Create test user
        req = connections.schema.CreateRequest(user_id="ream")
        server_a.handle_create(req, True)

        # Test Login on user
        req = connections.schema.LoginRequest(user_id="ream")
        ret = server_a.handle_login(req, True)
        assert ret.success == True

        # Test Login on nonexistant user
        bad_req = connections.schema.LoginRequest(user_id="faker")
        ret = server_a.handle_login(bad_req, True)
        assert not ret.success
        assert "does not exist" in ret.error_message

    def test_List(self):

        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')

        # Create test users
        names = ["ream", "mark", "achele", "joe", "bob"]
        for name in names:
            req = connections.schema.CreateRequest(user_id=name)
            server_a.handle_create(req, True)

        # Ensure all match works
        empty_lst_req = connections.schema.ListRequest(user_id='ream',wildcard="", page=0)
        ret = server_a.handle_list(empty_lst_req, True)
        assert len(ret.accounts) == 4

        # Ensure pagination works
        empty_lst_req = connections.schema.ListRequest(user_id='ream',wildcard="", page=1)
        ret = server_a.handle_list(empty_lst_req, True)
        assert len(ret.accounts) == 1

        # Ensure filtering works
        e_lst_req = connections.schema.ListRequest(user_id='ream', wildcard="e", page=0)
        ret = server_a.handle_list(e_lst_req, True)
        assert len(ret.accounts) == 3

        # Ensure none match works
        z_lst_req = connections.schema.ListRequest(user_id='ream', wildcard="z", page=0)
        ret = server_a.handle_list(z_lst_req, True)
        assert len(ret.accounts) == 0

    def test_Delete(self):
        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')

        # Create test users
        names = ["ream", "mark", "achele", "joe", "bob"]
        for name in names:
            req = connections.schema.CreateRequest(user_id=name)
            server_a.handle_create(req, True)
        
        # Ensure no deletion if no such user exists
        req = connections.schema.DeleteRequest(user_id="jimmy")
        ret = server_a.handle_delete(req, True)
        assert not ret.success
        assert len(server_a.users) == 5

        # Ensure deletion for matching user works
        req = connections.schema.DeleteRequest(user_id="ream")
        ret = server_a.handle_delete(req, True)
        assert ret.success
        assert len(server_a.users) == 4
    
    def test_get_logfile(self):
        """"
        Create a test server and test that get_logfile returns the correct log file
        """
        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')

        # Test get_logfile
        ret = server_a.get_logfile()
        assert ret == "logs/A_log.out"
    
    def test_get_progress(self):
        """
        Create a test server and test that get_progress returns the correct progress
        """
        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')

        # Test get_progress
        ret = server_a.get_progress()
        assert ret == 0
    
    def test_rehydrate(self):
        """
        Create a test server and test that rehydrate returns the correct progress
        """
        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')


        # Create test users in log file
        with open("logs/A_log.out", "w") as f:
            f.write("ream@@create\n")
            f.write("mark@@create\n")
            f.write("achele@@create\n")
            f.write("joe@@create\n")
            f.write("bob@@create\n")
        
        # Test rehydrate
        ret = server_a.rehydrate()
        assert len(server_a.users) == 5

        # Test rehydrate works on server initialization
        server_a2 = Server_dummy(name='A')
        assert len(server_a2.users) == 5

    def test_handle_send(self):
        """
        Create a test server and test that handle_send returns the correct progress
        """
        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')

        # Create test users
        names = ["ream", "mark", "achele", "joe", "bob"]
        for name in names:
            req = connections.schema.CreateRequest(user_id=name)
            server_a.handle_create(req, True)

        # Test handle_send
        req = connections.schema.SendRequest(user_id="ream", recipient_id="mark", text="hello")
        ret = server_a.handle_send(req, True)
        assert ret.success
        assert len(server_a.users["mark"].msg_log) == 1
    
    def test_handle_logs(self):
        """
        Create a test server and test that handle_logs returns the correct progress
        """
        # Create test server
        self.delete_log()
        server_a = Server_dummy(name='A')

        # Create test users
        names = ["ream", "mark", "achele", "joe", "bob"]
        for name in names:
            req = connections.schema.CreateRequest(user_id=name)
            server_a.handle_create(req, True)

        # Test handle_logs
        req = connections.schema.LogsRequest(user_id="ream", wildcard='', page=0)
        ret = server_a.handle_logs(req, True)
        assert len(ret.msgs) == 0

        # Test handle_logs with messages
        req = connections.schema.SendRequest(user_id="mark", recipient_id="ream", text="hello")
        ret = server_a.handle_send(req, True)
        req = connections.schema.LogsRequest(user_id="ream", wildcard='', page=0)
        ret = server_a.handle_logs(req, True)
        assert len(ret.msgs) == 1
        
