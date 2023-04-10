import sys
sys.path.append("..")
import connections.schema as conn_schema
import connections.consts as consts
import schema as data_schema
from tests.mocks.mock_socket import socket
from connections.manager import ConnectionManager


A = consts.MACHINE_A
B = consts.MACHINE_B
C = consts.MACHINE_C


def test_init():
    """
    Right stuff gets set
    """
    conman = ConnectionManager(A)

    assert conman.identity == A
    assert conman.is_primary == False
    assert [sib.name for sib in conman.living_siblings] == ["B", "C"]
