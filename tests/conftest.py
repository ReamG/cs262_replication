from mocks.mock_socket import socket
import sys
sys.path.append("../..")


###### SOCKET MODULE ######
sock_module = type(sys)("socket")


class timeout(Exception):
    pass


sock_module.timeout = timeout
SOL_SOCKET = 0
SO_REUSEADDR = 0
AF_INET = 0
SOCK_STREAM = 0
sock_module.SOL_SOCKET = SOL_SOCKET
sock_module.SO_REUSEADDR = SO_REUSEADDR
sock_module.AF_INET = AF_INET
sock_module.SOCK_STREAM = SOCK_STREAM
sock_module.socket = socket
sys.modules["socket"] = sock_module
