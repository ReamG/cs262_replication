# Helper function found here:
# https://stackoverflow.com/questions/39969064/how-to-print-a-message-box-in-python
def print_msg_box(msg, indent=1, width=None, title=None):
    """
    Print message-box with optional title.
    """
    chunk_size = 64
    msg.text = "Message: " + msg.text
    lines = [ "From: " + msg.author_id ] + [ msg.text[i:i+chunk_size] for i in range(0, len(msg.text), chunk_size) ]
    space = " " * indent
    if not width:
        width = max(map(len, lines))
    box = f'╔{"═" * (width + indent * 2)}╗\n'  # upper_border
    if title:
        box += f'║{space}{title:<{width}}{space}║\n'  # title
        box += f'║{space}{"-" * len(title):<{width}}{space}║\n'  # underscore
    box += ''.join([f'║{space}{line:<{width}}{space}║\n' for line in lines])
    box += f'╚{"═" * (width + indent * 2)}╝'  # lower_border
    print("\n" + box)

def print_error(msg):
    """
    Print an error string in red color
    """
    print("\033[91m{}\033[00m".format(msg))

def print_success(msg):
    """
    Print a success string in green color
    """
    print("\033[92m{}\033[00m".format(msg))

def print_info(msg):
    """
    Print an info string in a blue color
    """
    print("\033[94m{}\033[00m".format(msg))