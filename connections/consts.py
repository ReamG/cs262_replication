from connections.schema import Machine

# Create the three identities that the machines can assume
MACHINE_A = Machine(
    name="A",
    host_ip="10.250.155.180",
    internal_port=50051,
    client_port=50052,
    health_port=50053,
    notif_port=50054,
    num_listens=2,
    connections=[]
)

MACHINE_B = Machine(
    name="B",
    host_ip="10.250.138.58",
    internal_port=50061,
    client_port=50062,
    health_port=50063,
    notif_port=50064,
    num_listens=1,
    connections=["A"]
)

MACHINE_C = Machine(
    name="C",
    host_ip="10.250.155.180",
    internal_port=50071,
    client_port=50072,
    health_port=50073,
    notif_port=50074,
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
    other_names = [sib.name for sib in living_siblings]
    for other in other_names:
        if other < name:
            return False
    return True
