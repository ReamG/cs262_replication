# Project Three - Chat+

## Table of Contents:

## Files

- `docs` - Documentation

  - `architecture.md` - Explains the system architecture at a high level, including the steps we took to ensure persistence and two fault tolerance and justification for why the system is correct.
  - `implementation.md` - An explanation of how to configure the servers to run it locally, as well as a list of the commands available to you as a client.
  - `installation.md` - Installing stuff to run.

- `connections` - All the logic for sending stuff between machines, as well as client-server.

  - `connector.py` - A class used by each client. Has logic for connecting to machines, sending messages to machines, as well as automatically pinging servers to ensure health and find the next primary. Makes it so that in the actual client code we can think of sending responses/requests at a high level.
  - `consts.py` - System configuration. Machine names, port specifications, and connection order to avoid gridlock.
  - `errors.py` - Errors that may be thrown by the system and should be handled.
  - `manager.py` - A class used by each server. Manages connections between them, as well as listening/handling connections to clients.
  - `schema.py` - A class that defines our wire protocol as `Request`s and `Response`s.'

- `tests` - Testing folder. NOTE: since a lot of the functionality was carried over from a combination of the previous two projects, our tests focus heavily on the new functionality relating to persistence and fault tolerance.
  - `conftest.py` - Setup, mocking
  - `test_client.py` - Tests new (and old) client functionality
  - `test_connector.py` - Tests the ClientConnector class
  - `test_manager.py` - Tests the ConnectionManager class (servers)
  - `test_server.py` - Tests the server.

- `.` - Root folder

  - `client.py` - Client program. Run it and have fun.
  - `runner.py` - Handy for running all of the servers at once.
  - `schema.py` - Business logic schema (account, messages).
  - `server.py` - Each machine working as part of our backend.
  - `utils.py` - Mostly pretty printing stuff.

## Engineering Notebook

[Link](https://www.notion.so/Project-Three-b5a6c2aa37344535844b72e84241e81e?pvs=4)
