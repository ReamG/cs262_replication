# Architecture

This document outlines the structure of our system and explains how we guarantee both persistence and 2-fault tolerance.

## Table of Contents

1. [Fault Tolerance](#fault-tolerance)
2. [Persistence](#persistance)

## Fault Tolerance

For simplicity, we decided to support fault-tolerance using a primary-backup model. Our architecture supports any number of servers (see `implementation.md` for how to configure `consts` for the system) but to achieve 2 fault tolerance at least three servers should be used.

As per the spec, killing any two of the servers in any order will not disturb the system. The faults will be invisible to any clients, who perform reconnection and identification of new primary automatically on connection failure. Three faults are not supported.

As per the spec, we do not provide ways to integrate a new server on the fly into the system. However, by using the `fallover` command, followed by rebooting all the servers (in any order) we support resetting the server to a state with three servers without losing any information.

### Setting up connections

When servers boot, they go through the following steps:

- Read local logs and boot system up to match logs.
- Establish connections to all other servers. See `implementation.md` for more details.
- Let each server know how much progress it's made (size of log). The servers all get the same information, so they can all agree on who is furthest. They send updates to all lagging servers. After this stage, each server is connected, with the progress matching the furthest server.
- Open the health port to get ready for health checks.
- Open the client port to accept new connections.
- Open the notif port to accept new real-time subscriptions.

Internal servers ping each other every second to make sure they are still alive. By assumption, when a server fails this ping, we are safe to assume it has died and will not come back.

### Who gets to be primary?

Note that each server has complete information about all other servers in the system. Hence, the predicate for `is_primary` is whether the server has a name that is lexographically before all other servers. "All other servers" in this context means all servers still with healthy connections. Given that we can assume these checks will pass until a server dies, it's clear to see that at any given time at most one server will satisfy `is_primary`.

### Requests as state machine updates

The way we implemented requests, each request is simply a state machine update. Requests that just retrieve information (logs, list) as well as transient requests (login) are not recorded in the history of the state.

The upside of this approach is that everything is the same. The primary can simply apply the state machine update, turn it into a string, send that string to the backups, then write that string to its log. Backups see state updates the same way as if they were primaries, but never respond to clients. When rehydrating state, we can think of loading a request string as receiving it over the wire, and can reuse _all_ of our logic for handling it.

### Backup failures

When a backup fails, it presumably fails its next health checks and is removed from all other machines list of living siblings. It receives no more state updates.

### Primary failures

When the primary fails, each backup will detect it. There will then be a unique new machine that satisfies the `is_primary` predicate. It will finish processing any requests it needed to process as the backup, and then begin working as the primary. No broadcasts are needed because all the servers that are alive at any time have complete system information and can uniquely determine who is the primary.

### Client Illusions

The client has the vision of a single uninterupted system. This is achieved simply by putting specific error checking on requests made to the primary, so that when a primary dies it automatically blocks while it finds the next primary, and then sends the request to the new primary. We also do health checks from the client to the server so that in practice such a failure can be detected for preemptively so there is truly no interruption. The client handles automatically remembering your username and calling login in the background to resubscribe.

## Persistance

We achieve persistent progress using standard logging in a primary-backup as outlined by the basic paper we read for class.

### Logs

The order of processing is as follows:

1. Primary receives request
2. Primary updates own state to match request
3. Primary broadcasts request to backups.
4. Primary updates it's own log.

Note that the primary can die at/between any of these steps and the global state of logs will still be consistent.

Backups simply perform the requests they get as state machine updates and then write them to their log. If they ever become primary, they first process any requests that had received before that from the primary.

### Rehydration

When a server boots up, it performs state machine updates on stuff in it's own log until it's up to date with itself. Then, all of the machines share the size of their log. Because of the simplicity of the problem, plus the fact that we are doing primary backup, the longest log is always the one with the most progress, and a superset of other logs. (This can be shown using induction.)

Hence, the machines share how much progress they've mad with all other machines, and then they identify a leader (can be determined individually by looking for max) and then listen for as many updates as they need to from the leader to catch up. Then the system may begin. Notice that the leader during catchup is allowed to be different from the first server who will serve as primary once the system starts.
