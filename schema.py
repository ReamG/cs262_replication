
class Account:
    """
    A class for users
    """

    def __init__(self, user_id):
        self.user_id = user_id
        self.msg_log = []

    def marshal(self):
        return f"{self.user_id}"

    @staticmethod
    def unmarshal(a_str):
        return Account(a_str)


class Chat:
    """
    A class for chats sent from user -> user (NOT TO BE CONFUSED WITH INTERNAL MESSAGES)
    """

    def __init__(self, author_id, recipient_id, text):
        self.author_id = author_id
        self.recipient_id = recipient_id
        self.text = text

    def marshal(self):
        return f"{self.author_id}@@{self.recipient_id}@@{self.text}"

    def pretty(self):
        return f"------\nFrom: {self.author_id}\nText: {self.text}\n------"

    @staticmethod
    def unmarshal(message):
        parts = message.split("@@")
        author_id = parts[0]
        recipient_id = parts[1]
        text = parts[2]
        success = parts[3]
        return Chat(author_id, recipient_id, text, success)
