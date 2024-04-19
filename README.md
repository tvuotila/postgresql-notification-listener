# PostgreSQL Notification Listener

This project is a Python library that listens to notifications from a PostgreSQL database.
It provides a simple way to execute functions when specific events happen in the database.

## How it works

The listener connects to the PostgreSQL database and sets up a notification channel. You can then attach callbacks to this channel, which will be executed whenever a notification is received.

## Installation

To install the library, run:
pip install postgresql-notification-listener

### Usage

To use this library, follow these steps:

* Import the library in your Python script: `from postgresql_notification_listener import NotificationListener`
* Create instance of the listener `listener = NotificationListener("host=your_host port=your_port dbname=your_database user=your_username password=your_password")`
* Define a callback function that will be executed when a notification is received.
* Use the `subscribe_to_channel` method to attach your callback function to the notification channel: `listener.subscribe_to_channel("channel_to_listen", callback_function)`
* Start listening for notifications by calling the `start` method: `listener.start()`
* You can trigger a notification from PostgreSQL by `NOTIFY channel_to_listen` statement.
* The `start` method will call all attached callbacks once when called. If you don't want this behaviour, pass the `initial_run=False` argument to the start method: `listener.start(initial_run=False)`
* You can get the notification that caused the callback from the `last_notification` attribute on the listener instance `listener.last_notification`


### API
* **NotificationListener**: The main class of this library. It is responsible for setting up a notification channel and managing callbacks.
	+ **subscribe_to_channel** : Attaches a callback function to a specific channel.  The `subscribe_to_channel` method takes two required parameters: the name of the channel to listen to and the callback function to execute when a notification is received.
	+ **start** : Starts listening for notifications. If you don't want all attached callbacks to be called once when called, pass `initial_run=False` as an argument.
	+ **last_notification**: Returns the latest notification that caused a callback.

