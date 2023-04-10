# Implementation

This document explains how to run the various files, as well as what commands are available to the client

## Table of Contents

1. [Banned Tokens and the Like](#banned-tokens-and-the-like)
2. [Setting Up Servers](#setting-up-servers)
3. [Running the Servers](#running-the-servers)
4. [Running the Clients](#running-the-clients)
5. [Client Commands](#client-commands)

## Banned Tokens and the Like

Because of the specifics of our wire protocol, the substrings "@@", "##", and "||" are not allowed anywhere (names, messages, etc). This goes for both servers and clients and the interactions between the two.

We've also implemented the following limitations:

- `user_id`s can be at most 8 characters
- Messages themselves can be at most 280 bytes
- When fetching things that can have variable length (i.e. accounts, logs), you must use pagination with a page size of 4 items

## Setting Up Servers

- All logic for the system configuration should live in `connections/consts.py`. Here you may specify as many machines as you like providing the following information (it feeds into the `Machine` class from `connections/schema.py`):

  - `name`: Must be unique per server, and not contain banned tokens.
  - `host_ip`: The machine's IP. For local development, `localhost` should be fine. NOTE: All of the below ports should be unique.
  - `internal_port`: The port where the machine will listen to messages from other servers.
  - `client_port`: The port where the machine will listen for client commands and connections.
  - `health_port`: The port where both servers and client can ping to get health checks and status updates.
  - `notif_port`: The port where clients should initiate a connection in order to subscribe to real-time messages.
  - `num_listens`: The number of internal listens this machine should perform during setup. See the picture below for more context.
  - `connections`: A list of machines (by name) that this machine is responsible for connecting to.

![Setup](images/SetupArch.png)
A diagram showing how to setup connection configuration between servers. A ring-like architecture tends to work well.

## Running the Servers

If you'd like granularity, you can run the servers in separate terminals. You can also use the `runner.py` file to run all the servers in separate processes.

## Running the Servers

You can simply run `client.py`. If you've used `consts` correctly, it should automatically connect.

## Client Commands

Here's a list of all the commands available to a client:

- `create`: Creates a new user. Will prompt for a username.
- `login`: Logs in to an existing user. Will prompt for a username.
- `delete`: Must be logged in. Deletes the current users account. Does not deliver any undelivered messages that might exist.
- `list`: Must be logged in. List accounts. Will prompt for text to filter by, and then a page to return.
- `send`: Must be logged in. Sends a message to an account. Will prompt for recipient, message.
- `logs`: Must be logged in. Gets all messages for this user. Will prompt for text to filter, and a page.
- `fallover`: Instructs the system to shut down. Will propogate the shutdown throughout the system.
