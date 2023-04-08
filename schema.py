
class Account:
    """
    A class for users
    """

    def __init__(self, user_id, is_logged_in):
        self.user_id = user_id
        self.is_logged_in = is_logged_in
        self.msg_log = []


class Message:
    """
    A class for messages sent from server -> client
    """

    def __init__(self, author_id, recipient_id, text, success):
        self.author_id = author_id
        self.recipient_id = recipient_id
        self.text = text
        self.success = success
