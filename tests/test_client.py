
import unittest
import builtins as __builtin__
import io
import sys
sys.path.insert(0, "..")
import client

# Make client class init indepedent of connecting to server for testing
class Client_dummy(client.Client):
    def __init__(self):
        self.user_id = ""

class Test_server(unittest.TestCase):
    """Test class for our server code"""

    def test_is_logged_in(self):
        """Test is_logged_in"""
        # Create test client
        c = Client_dummy()

        # Test is_logged_in on nonexistant user
        ret = c.is_logged_in()
        assert not ret

        # Assert that logged in user returns true
        c.user_id = "ream"
        assert c.is_logged_in()

    def test_handle_create(self):

        # Create test client
        c = Client_dummy()

        # Test handle_create when logged in
        c.user_id = "ream"
        sys.stdout = io.StringIO()
        c.handle_create()
        assert "You're already logged in" in sys.stdout.getvalue()

        # Test handle_create when not logged in
        c.user_id = ""

        # Test user trying to create an account with an empty username
        client.input = lambda _: ""
        c.handle_create()
        assert "username cannot be empty" in sys.stdout.getvalue()

        # Test user trying to create an account with a username that is too long
        client.input = lambda _: "a" * 21
        c.handle_create()
        assert "username cannot be longer than 8 characters" in sys.stdout.getvalue()

        # Test user trying to create name with invalid characters
        client.input = lambda _: "a,b"
        c.handle_create()
        assert "username cannot contain commas" in sys.stdout.getvalue()
        client.input = lambda _: "a||b"
        c.handle_create()
        assert "username cannot contain \"||\"" in sys.stdout.getvalue()

        sys.stdout = sys.__stdout__

    def test_handle_login(self):

        # Create test client
        c = Client_dummy()

        # Test handle_login when logged in
        c.user_id = "ream"
        sys.stdout = io.StringIO()
        c.handle_login()
        assert "You're already logged " in sys.stdout.getvalue()

        # Test handle_login on empty username
        c.user_id = ""
        client.input = lambda _: ""
        c.handle_create()
        assert "username cannot be empty" in sys.stdout.getvalue()

    def test_handle_delete(self):

        # Create test client
        c = Client_dummy()

        # Test handle_delete when not logged in
        c.user_id = ""
        sys.stdout = io.StringIO()
        c.handle_delete()
        assert "You must be logged in to delete" in sys.stdout.getvalue()

        # Test aborting handle_delete
        c.user_id = "ream"
        client.input = lambda _: "n"
        c.handle_delete()
        assert "Aborting delete" in sys.stdout.getvalue()
    
    def test_handle_list(self):
            
        # Create test client
        c = Client_dummy()

        # Test handle_list when not logged in
        c.user_id = ""
        sys.stdout = io.StringIO()
        c.handle_list()
        assert "You must be logged in to list" in sys.stdout.getvalue()

        # Test handle_list when logged in
        c.user_id = "ream"
        client.input = lambda _: "a"*9
        c.handle_list()
        assert "wildcard cannot be longer than 8 characters" in sys.stdout.getvalue()
    
    def test_handle_logs(self):
            
        # Create test client
        c = Client_dummy()

        # Test handle_list when not logged in
        c.user_id = ""
        sys.stdout = io.StringIO()
        c.handle_logs()
        assert "You must be logged in to list logs" in sys.stdout.getvalue()

        # Test handle_list when logged in
        c.user_id = "ream"
        client.input = lambda _: "a"*9
        c.handle_logs()
        assert "wildcard cannot be longer than 8 characters" in sys.stdout.getvalue()
    
    def test_handle_send(self):
        # Create test client
        c = Client_dummy()

        # Test handle_list when not logged in
        c.user_id = ""
        sys.stdout = io.StringIO()
        c.handle_send()
        assert "You must be logged in to send" in sys.stdout.getvalue()

        # Test handle_send when logged in
        c.user_id = "ream"
        client.input = lambda _: ""
        c.handle_send()
        assert "Recipient cannot be empty" in sys.stdout.getvalue()
    
    def test_parse_input(self):
        # Create test client
        c = Client_dummy()
        
        # Test parse_input returns correct function
        functions = [c.handle_create, c.handle_login, c.handle_delete, c.handle_list, c.handle_send, c.handle_logs, c.handle_fallover]
        for ix, command in enumerate(["create", "login", "delete", "list", "send", "logs", "fallover"]):
            ret = c.parse_input(command)
            assert ret == functions[ix]

        # Test parse_input returns None on invalid command
        ret = c.parse_input("invalid")
        assert ret == None