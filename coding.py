from schema import Message, Request, ListRequest, SendRequest, Response, ListResponse

VERSION = "0"

ERROR_MESSAGE_LENGTH = 64
MAX_MESSAGE_LENGTH = 280

OP_TO_CODE_MAP = {
    "create": "1",
    "login": "2",
    "delete": "3",
    "get": "4",
    "send": "5",
    "list": "6",
    "logs": "7",
}

CODE_TO_OP_MAP = {
    "1": "create",
    "2": "login",
    "3": "delete",
    "4": "get",
    "5": "send",
    "6": "list",
    "7": "logs",
}

def pad_to_length(s, length):
    """
    Pads a string to a given length
    NOTE: if len(s) > length, this will truncate the string
    """
    if len(s) > length:
        return s[:length]
    return s + (length - len(s)) * "\0"

def unpad(s):
    """
    Removes padding from a string
    """
    return s.strip("\0")

def prep_accounts(accounts):
    """
    Turns a list of accounts into a string
    """
    as_strings = [account.user_id for account in accounts]
    return ",".join(as_strings)

def prep_messages(messages):
    """
    Turns a list of messages into a string
    """
    as_strings = [message.author_id + ": " + message.text for message in messages]
    return ",".join(as_strings)


def post_accounts(str):
    """
    Turns a string of accounts into a list
    """
    if str == "":
        return []
    
    return str.split(",")

def marshal_create_request(req: Request):
    """
    Marshals a create Request into a byte string
    """
    return "{}{}{}".format(
        VERSION,
        pad_to_length(req.user_id, 8),
        OP_TO_CODE_MAP["create"],
    ).encode()

def marshal_login_request(req: Request):
    """
    Marshals a login Request into a byte string
    """
    return "{}{}{}".format(
        VERSION,
        pad_to_length(req.user_id, 8),
        OP_TO_CODE_MAP["login"],
    ).encode()

def marshal_delete_request(req: Request):
    """
    Marshals a delete Request into a byte string
    """
    return "{}{}{}".format(
        VERSION,
        pad_to_length(req.user_id, 8),
        OP_TO_CODE_MAP["delete"],
    ).encode()

def marshal_list_request(req: ListRequest):
    """
    Marshals a list Request into a byte string
    """
    return "{}{}{}{}{}".format(
        VERSION,
        pad_to_length(req.user_id, 8),
        OP_TO_CODE_MAP["list"],
        pad_to_length(req.wildcard, 8),
        pad_to_length(str(req.page), 8),
    ).encode()

def marshal_logs_request(req: ListRequest):
    """
    Marshals a list Request into a byte string
    """
    return "{}{}{}{}{}".format(
        VERSION,
        pad_to_length(req.user_id, 8),
        OP_TO_CODE_MAP["logs"],
        pad_to_length(req.wildcard, 8),
        pad_to_length(str(req.page), 8),
    ).encode()
    
def marshal_subscribe_request(req: Request):
    """
    Marshals a subscribe Request into a byte string
    """
    return "{}{}{}".format(
        VERSION,
        pad_to_length(req.user_id, 8),
        OP_TO_CODE_MAP["subscribe"],
    ).encode()

def marshal_get_request(req: Request):
    """
    Marshals a subscribe Request into a byte string
    """
    return "{}{}{}".format(
        VERSION,
        pad_to_length(req.user_id, 8),
        OP_TO_CODE_MAP["get"],
    ).encode()

def marshal_send_request(req: SendRequest):
    """
    Marshals a send Request into a byte string
    """
    return "{}{}{}{}{}".format(
        VERSION,
        pad_to_length(req.user_id, 8),
        OP_TO_CODE_MAP["send"],
        pad_to_length(req.recipient_id, 8),
        pad_to_length(req.text, MAX_MESSAGE_LENGTH),
    ).encode()

def unmarshal_request(data: bytes):
    """
    Unmarshals a byte string into a Request
    """
    data = data.decode()
    version = data[0]
    user_id = unpad(data[1:9])
    op_code = data[9]
    op = CODE_TO_OP_MAP[op_code]
    if op == "create":
        return Request(user_id), op
    elif op == "login":
        return Request(user_id), op
    elif op == "delete":
        return Request(user_id), op
    elif op == "list":
        wildcard = unpad(data[10:18])
        page = unpad(data[18:26])
        page_num = int(page)
        return ListRequest(user_id, wildcard, page_num), op
    elif op == "logs":
        wildcard = unpad(data[10:18])
        page = unpad(data[18:26])
        page_num = int(page)
        return ListRequest(user_id, wildcard, page_num), op
    elif op == "get":
        return Request(user_id), op
    elif op == "send":
        recipient_id = unpad(data[10:18])
        text = unpad(data[18:18+MAX_MESSAGE_LENGTH])
        return SendRequest(user_id, recipient_id=recipient_id, text=text), op
    else:
        raise Exception("Unknown op code: {}".format(op_code))
    
RESP_TO_CODE_MAP = {
    "basic": "1",
    "list": "2",
    "message": "3",
}

CODE_TO_RESP_MAP = {
    "1": "basic",
    "2": "list",
    "3": "message",
}

def marshal_response(resp: Response):
    """
    Marshals a Response into a byte string
    """
    return "{}{}{}{}{}".format(
        VERSION,
        pad_to_length(resp.user_id, 8),
        RESP_TO_CODE_MAP[resp.type],
        1 if resp.success else 0,
        pad_to_length(resp.error_message, ERROR_MESSAGE_LENGTH),
    ).encode()

def marshal_list_response(resp: ListResponse):
    """
    Marshals a ListResponse into a byte string
    """
    return "{}{}{}{}{}{}".format(
        VERSION,
        pad_to_length(resp.user_id, 8),
        RESP_TO_CODE_MAP[resp.type],
        1 if resp.success else 0,
        pad_to_length(resp.error_message, ERROR_MESSAGE_LENGTH),
        prep_accounts(resp.accounts)
    ).encode()

def marshal_logs_response(resp: ListResponse):
    """
    Marshals a ListResponse into a byte string
    """
    return "{}{}{}{}{}{}".format(
        VERSION,
        pad_to_length(resp.user_id, 8),
        RESP_TO_CODE_MAP[resp.type],
        1 if resp.success else 0,
        pad_to_length(resp.error_message, ERROR_MESSAGE_LENGTH),
        prep_messages(resp.accounts)
    ).encode()

def marshal_message_response(msg: Message):
    """
    Marshals a Message into a byte string
    """
    return "{}{}{}{}{}{}{}".format(
        VERSION,
        pad_to_length(msg.recipient_id, 8),
        RESP_TO_CODE_MAP["message"],
        1 if msg.success else 0,
        pad_to_length("", ERROR_MESSAGE_LENGTH),
        pad_to_length(msg.author_id, 8),
        pad_to_length(msg.text, 280),
    ).encode()

def unmarshal_response(data):
    """
    Unmarshals a byte string into a Response
    """
    data = data.decode()
    version = data[0]
    user_id = unpad(data[1:9])
    resp_code = data[9]
    resp_type = CODE_TO_RESP_MAP[resp_code]
    success = data[10] == "1"
    error_message = unpad(data[11:11+ERROR_MESSAGE_LENGTH])
    if resp_type == "basic":
        return Response(user_id=user_id, success=success, error_message=error_message)
    elif resp_type == "list":
        accounts = post_accounts(data[11+ERROR_MESSAGE_LENGTH:])
        return ListResponse(user_id=user_id, success=success, error_message=error_message, accounts=accounts)
    elif resp_type == "message":
        author_id = unpad(data[11+ERROR_MESSAGE_LENGTH:11+ERROR_MESSAGE_LENGTH+8])
        text = unpad(data[11+ERROR_MESSAGE_LENGTH+8:])
        return Message(recipient_id=user_id, author_id=author_id, text=text, success=success)
    else:
        raise Exception("Unknown response type: {}".format(resp_type))