# Project One - Chat

NOTE: In order to prevent this file from getting _too_ big we split a lot of the documentation into the `docs` subfolder. This is referenced in some places below, so please feel free to dive into the `docs` folder for more specific info and design justification.

## Table of Contents:

- [Overview](#overview)
  - [Files](#files)
  - [Architecture](#architecture)
- [Wire Protocol](#wire-protocol)
- [Part One](#part-one)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
  - [Usage](#usage)
  - [IMPORTANT NOTES](#important-notes)
- [Part Two](#part-two)
  - [Setup](#setup2)
  - [Usage](#usage2)
- [Testing](#testing)
- [gRPC Reflections](#grpc-reflections)
- [Engineering Notebook](#engineering-notebook)

## Overview

### Files

The files used for part one are stored in this directory, aptly named `server.py` (implements server functions and creates a server when run), `client.py` (implements client functions and creates a client when run), `schema.py` (classes and data types for our server and client implementations), and `coding.py` (marshalling). The code for part two is stored in the `part2` folder and are similarly named.

### Architecture

Please consult `docs/architecture.md` for more information. IMPORTANT: This has pretty pictures.

## Wire Protocol:

Please check out `docs/wire_protocol.md`.

## Part One

### Prerequisites

Before attempting to run the client/server, please go to `docs/installation` and make sure you installed all the modules required.

### Setup

#### Running the server

First, you'll need to identify the LAN ip address.

- For windows run `ipconfig /all` and under section `Wireless LAN adapter Wi-Fi:` copy the `IPv4 Addresss`.
- For Mac, run `ifconfig` and copy the `inet` address under the `en0` section.

Save this value for later.

Run `python server.py`.

#### Running the client

Run `python client.py`. This will prompt your for the host address, which is the value that you copied while running the server.

### Usage

This is a high-level overview of how to use the client. For more information about the adherence to the specs please check out `docs/implementation.md`.

In general, the program works by asking you for a command, and then asking you for inputs to that command. For instance

```
> Enter a command: login
> Enter a username: test
```

Here are the valid commands you can run from the client:

- `create` - Creates an account. Will prompt you for a username, which must be at least one character and no more than eight characters. It will return an error from the server if the username you supply is not unique.
- `login` - Logs into an existing account. Will prompt you for a username under the same length constraints.
- `list` - Will first prompt you a text wildcard. Leave this blank to get everything. Searching will return all users that have usernames that contain the wildcard you provide. It then asks you for a page. **NOTE: PAGES START AT ZERO**. The page size is 4. I.e., if there were 6 users in the system and you wanted to list all of them, you'd do:

```
> Enter a command: list
> Enter a text filter:
> Enter a page: 0
4 users on page 0 matching ''
user1
user2
user3
user4
> Enter a command: list
> Enter a text filter:
> Enter a page: 1
2 users on page 1 matching ''
user5
user6
```

- `send` - Will first prompt you for a recipient id, and then a message. The recipient id is subject to the same length constraints as above, and the message can be at most 280 characters. It will return an error from the server if something goes wrong (like a non-existent user). If all is good, you'll see a success message printed to the terminal.
- `delete` - Deletes the account of the currently logged in user. If there were any remaining messages, they are deleted, never to be seen again.

### IMPORTANT NOTES

- You must be logged in to run `list`, `send` or `delete`.
- There is no way to log out. If you would like to log out, simply kill your client and log back in.
- Our interpretation of "list accounts" simply uses Python's built-in "in" function. The empty string matches everything.
- Our interpretation of "deliver on demand" is "deliver immediately if the user is logged in. If the user is not logged in, put it in a queue, and deliver it to them as soon as they log in again".
- Our interpretation of "deliver undelivered messages" is "As soon as a user has undelivered messages, deliver them." This means if a user exists but is logged out and gets messages, when they log back in they get all their unread messages delivered at once. _There is no need for them to call this explicitly_. Building this in as a natural feature of logging in felt like the cleanest and most natural way to handle this.
- Our interpretation of "delete an account" only allows people to delete their own account. **No one is allowed to delete other peoples accounts**. When an account is deleted, that person is logged out, and any messages they might have had are deleted, never to be seen. NOTE: based on how we implemented the above with messages always being delivered ASAP, it's very unlikely a person actually has unread messages when they delete their account. But again, this was (in out opinion) by far the cleanest way to do this and fulfils the specs.

## Part Two

### Setup2

Go ahead and `cd part2`. You'll use the same ip address as in part one.

Run `python server.py`.

Run `python client.py`.

### Usage2

The valid commands you can run in part two are the exact same, with the following differences in behavior:

- Usernames can now be 16 bytes instead of 8.
- You can run the `list` command without being logged in.
- `list` no longer requires a page. It returns all satisfying requests in one value always.
- You might have noticed that sometimes it takes half a second to deliver messages in part one. This is because part one uses polling to detect new messages, whereas part two uses blocking.

## Testing

Please consult `docs/testing.md` to learn more about the automated tests we wrote for the client and server.

## gRPC Reflections

Included at the end of the engineering notebook below. ([Direct Link](https://berry-sugar-a23.notion.site/gRPC-reflections-faacb484548c40318c38709f61e392bf))

## Engineering Notebook

[Link](https://berry-sugar-a23.notion.site/Engineering-Notebook-6519389b51434222b4f2abb640df4036)
