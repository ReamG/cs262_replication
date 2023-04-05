
# An exception type for non-existent machines
class MachineNotFoundException(Exception):
    def __init__(self, name: str):
        self.name = name
        self.message = f"Machine {name} is not in the identity map"
        super().__init__(self.message)
