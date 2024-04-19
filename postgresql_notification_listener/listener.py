from types import TracebackType
from typing import NoReturn, Self

import psycopg
from psycopg import sql, Notify

from .types import Callback


class NotificationListener:
    """
    NotificationListener listens to notifications from a PostgreSQL database.

    Callbacks can be attached to the listener to be called when notification is received.
    """

    def __init__(self, database_url: str) -> None:
        # Stores latest Notify object in case callbacks need it
        self.last_notification: Notify | None = None
        self.connection = psycopg.connect(database_url, autocommit=True)
        self.callbacks: dict[str, set[Callback]] = {}

    ## Context manager methods ##

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    ## Subscription methods ##

    def _get_or_create_listening_channel(self, channel: str) -> set[Callback]:
        if channel not in self.callbacks:
            self.callbacks[channel] = set()
            self.connection.execute(
                sql.SQL("LISTEN {}").format(sql.Identifier(channel))
            )
        return self.callbacks[channel]

    def subscribe_to_channel(
        self,
        channel: str,
        callback: Callback,
    ) -> None:
        """
        Subscribes to a channel and associates a callback function with it.
        If callback is already associated with the channel, old association will be overwritten.

        Args:
            channel (str): The name of the channel to subscribe to.
            callback (Callable): The callback function to be executed when a notification is received.
        """
        self._get_or_create_listening_channel(channel).add(callback)

    ## Unsubscription methods ##

    def unsubscribe_from_channel(self, channel: str, callback: Callback) -> None:
        """
        Unsubscribe the specified callback function from a channel.

        Args:
            channel (str): The channel to unsubscribe from.
            callback (Callable): The callback function to remove.

        Raises: KeyError if channel or callback is not subscribed
        """
        self.callbacks[channel].remove(callback)
        if not self.callbacks[channel]:
            self.unsubscribe_channel(channel)

    def unsubscribe_channel(self, channel: str) -> None:
        """
        Unsubscribe all callback functions from a channel.

        Args:
            channel (str): The channel to unsubscribe from.

        Raises: KeyError if channel is not subscribed
        """
        del self.callbacks[channel]
        self.connection.execute(sql.SQL("UNLISTEN {}").format(sql.Identifier(channel)))

    def unsubscribe_all(self) -> None:
        """
        Unsubscribe all callback functions from all channels.
        """
        for channel in list(self.callbacks):
            self.unsubscribe_channel(channel)

    ## Listening methods ##

    def start(self, initial_run: bool = True) -> NoReturn:  # type: ignore[misc]  # We never return
        """
        Starts the notification listener and executes the callbacks for each received notification.
        Duplicate notifications for a channel are ignored.
        This function will never return.

        Args:
            initial_run (bool): Execute all callbacks before listening starts.
            This makes sure that no notifications are left unporcessed
            while the notification listened was not running.
            (default: True)
        """
        if initial_run:
            self.execute_all_callbacks()
        self._notification_generator = self.connection.notifies()
        for notification in self._notification_generator:
            self.last_notification = notification
            self.execute_callbacks(notification.channel)

    ## Execution methods ##
    def execute_all_callbacks(self) -> None:
        for channel in self.callbacks:
            self.execute_callbacks(channel)

    def execute_callbacks(self, channel: str) -> None:
        if channel not in self.callbacks:
            return
        # Use a copy to allow callbacks to be removed during iteration
        for callback in self.callbacks[channel].copy():
            callback()
