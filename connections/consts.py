from connections.schema import Machine

# Create the three identities that the machines can assume
MACHINE_A = Machine(
    name="A",
    host_ip="localhost",
    internal_port=50051,
    client_port=50052,
    health_port=50053,
    num_listens=2,
    connections=[]
)

MACHINE_B = Machine(
    name="B",
    host_ip="localhost",
    internal_port=50061,
    client_port=50062,
    health_port=50063,
    num_listens=1,
    connections=["A"]
)

MACHINE_C = Machine(
    name="C",
    host_ip="localhost",
    internal_port=50071,
    client_port=50072,
    health_port=50073,
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
    return [MACHINE_MAP[key] for key in MACHINE_MAP if key != name]


def should_i_be_primary(name: str, living_siblings) -> bool:
    """
    A helper function that determines whether or not a machine should be
    the primary machine for a given set of siblings
    NOTE: This basically just enforces lexicographically ordering, i.e.
    at any given time the machine with the earliest name will see itself
    as the primary machine. (correctly)
    """
    if name == "A":
        return True
    elif name == "B":
        return len(living_siblings) == 1
    else:
        return len(living_siblings) == 0