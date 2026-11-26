[![image](https://img.shields.io/pypi/v/postgresql-notification-listener)](https://pypi.python.org/pypi/postgresql-notification-listener)
[![image](https://img.shields.io/pypi/l/postgresql-notification-listener)](https://pypi.python.org/pypi/postgresql-notification-listener)
[![image](https://img.shields.io/pypi/pyversions/postgresql-notification-listener)](https://pypi.python.org/pypi/postgresql-notification-listener)
[![image](https://img.shields.io/pypi/types/postgresql-notification-listener)](https://pypi.python.org/pypi/postgresql-notification-listener)
[![image](https://img.shields.io/pypi/format/postgresql-notification-listener)](https://pypi.python.org/pypi/postgresql-notification-listener)
[![image](https://img.shields.io/pypi/status/postgresql-notification-listener)](https://pypi.python.org/pypi/postgresql-notification-listener)
[![Actions status](https://github.com/tvuotila/postgresql-notification-listener/actions/workflows/ci.yml/badge.svg)](https://github.com/tvuotila/postgresql-notification-listener/actions)

# PostgreSQL Notification Listener

This project is a Python library that listens to notifications from a PostgreSQL database.
It provides a simple way to execute functions when specific events happen in the database.

## How it works

The listener connects to the PostgreSQL database and sets up a notification channel. You can then attach callbacks to this channel, which will be executed whenever a notification is received. The listener tries to minimize the times callbacks are called. When there are multiple pending notifications on the same channel, the callback is called only once. This means that the notification payload and PID are ignored.

## Installation

To install the library, run:
`pip install postgresql-notification-listener`

### Example

```python
from postgresql_notification_listener import NotificationListener


def process_new_orders() -> None:
    # Callbacks take no arguments. Fetch the pending work from the database here.
    print("Orders table changed, processing new orders...")


def refresh_cache() -> None:
    print("Refreshing cache...")


with NotificationListener("postgresql://localhost/postgres") as listener:
    listener.subscribe_to_channel("new_orders", process_new_orders)
    listener.subscribe_to_channel("cache_invalidated", refresh_cache)
    # Runs every callback once on startup, then whenever a notification arrives.
    # If no notification arrives within 60 seconds, all callbacks are run anyway.
    # This call blocks forever.
    listener.start(poll_interval=60)
```

Trigger the callbacks from PostgreSQL, for example with `psql` or from a trigger function:

```sql
NOTIFY new_orders;
-- or
SELECT pg_notify('cache_invalidated', '');
```


### API
* **NotificationListener**: The main class of this library. It is responsible for setting up a notification channel and managing callbacks.
	+ **subscribe_to_channel** : Attaches a callback function to a specific channel.  The `subscribe_to_channel` method takes two required parameters: the name of the channel to listen to and the callback function to execute when a notification is received.
	+ **start** : Starts listening for notifications. If you don't want all attached callbacks to be called once when called, pass `initial_run=False` as an argument.
	If you want to call all callback after X seconds if no notification is received,
	pass `poll_interval=X`.

