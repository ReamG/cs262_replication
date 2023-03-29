
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

class Request:
    """
    A base class for all requests from client -> server
    """
    def __init__(self, user_id):
        self.user_id = user_id

class ListRequest(Request):
    """
    A request to list all messages that match a wildcard
    """
    def __init__(self, user_id, wildcard, page):
        super().__init__(user_id)
        self.wildcard = wildcard
        self.page = page

class SendRequest(Request):
    """
    A request to send a message to a user
    """
    def __init__(self, user_id, recipient_id, text):
        super().__init__(user_id)
        self.recipient_id = recipient_id
        self.text = text

class Response:
    """
    A base class for all responses from server -> client
    """
    def __init__(self, user_id, success, error_message):
        self.user_id = user_id
        self.success = success
        self.error_message = error_message
        self.type = "basic"

class ListResponse(Response):
    """
    A response to a ListRequest
    """
    def __init__(self, user_id, success, error_message, accounts):
        super().__init__(user_id, success, error_message)
        self.accounts = accounts
        self.type = "list"
