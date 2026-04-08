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

### Usage

To use this library, follow these steps:

* Import the library in your Python script: `from postgresql_notification_listener import NotificationListener`
* Create instance of the listener `listener = NotificationListener("postgresql://localhost/postgres")`
* Define a callback function that will be executed when a notification is received.
* Use the `subscribe_to_channel` method to attach your callback function to the notification channel: `listener.subscribe_to_channel("channel_to_listen", callback_function)`
* You must register all callback functions before calling the `start` method.
* You cannot unregister callback functions after calling the `start` method.
* Start listening for notifications by calling the `start` method: `listener.start()`
* You can trigger a notification from PostgreSQL by `NOTIFY channel_to_listen` statement.
* The `start` method will call all attached callbacks once when called. If you don't want this behaviour, pass the `initial_run=False` argument to the start method: `listener.start(initial_run=False)`
* `NotificationListener` can be used as a context manager: `with NotificationListener("connection string") as listener:`. The database connection automatically closes when exiting the `with` block.


### API
* **NotificationListener**: The main class of this library. It is responsible for setting up a notification channel and managing callbacks.
	+ **subscribe_to_channel** : Attaches a callback function to a specific channel.  The `subscribe_to_channel` method takes two required parameters: the name of the channel to listen to and the callback function to execute when a notification is received.
	+ **start** : Starts listening for notifications. If you don't want all attached callbacks to be called once when called, pass `initial_run=False` as an argument.
	If you want to call all callback after X seconds if no notification is received,
	pass `poll_interval=X`.

