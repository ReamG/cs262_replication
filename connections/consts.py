from connections.schema import Machine

# Create the three identities that the machines can assume
MACHINE_A = Machine(
    name="A",
    host_ip="localhost",
    host_port=50051,
    num_listens=2,
    connections=[]
)

MACHINE_B = Machine(
    name="B",
    host_ip="localhost",
    host_port=50052,
    num_listens=1,
    connections=["A"]
)

MACHINE_C = Machine(
    name="C",
    host_ip="localhost",
    host_port=50053,
    num_listens=0,
    connections=["A", "B"],
)

# Create a mapping from machine name to information about it
MACHINE_MAP = {
    "A": MACHINE_A,
    "B": MACHINE_B,
    "C": MACHINE_C,
}


def get_other_machines(name: str) -> list[str]:
    """
    Returns a list of the names of all machines except the one specified
    """
    return [key for key in MACHINE_MAP if key != name]
