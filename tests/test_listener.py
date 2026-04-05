from threading import Timer
from typing import Iterator, Union, TypeVar
import pytest
from postgresql_notification_listener import NotificationListener
import psycopg
from psycopg import Connection, sql
from psycopg.rows import TupleRow
from unittest.mock import MagicMock
import time
from postgresql_notification_listener.types import Callback

T = TypeVar("T")
Fixture = Union[Iterator[T], T]


@pytest.mark.timeout(1)  # Fail if we hang
class ListenerBase:
    @pytest.fixture
    def database(self) -> Fixture[None]:  # type: ignore[return]
        with psycopg.connect(
            "dbname=template1 user=postgres password=postgres host=localhost port=5432",
            autocommit=True,
        ) as connection:
            # Clean after unclean exit
            connection.execute("DROP DATABASE IF EXISTS notification_listener_test")
            connection.execute("CREATE DATABASE notification_listener_test")
            yield None
            connection.execute("DROP DATABASE notification_listener_test")

    @pytest.fixture
    def connection(self, database: None) -> Fixture[Connection[TupleRow]]:  # type: ignore[return]
        with psycopg.connect(
            "dbname=notification_listener_test user=postgres password=postgres host=localhost port=5432",
            autocommit=True,
        ) as connection:
            yield connection

    @pytest.fixture
    def listener(self, database: None) -> Fixture[NotificationListener]:  # type: ignore[return]
        with NotificationListener(
            "dbname=notification_listener_test user=postgres password=postgres host=localhost port=5432"
        ) as listener:
            yield listener

    def done_after_timeout(self, connection: Connection[TupleRow]) -> Timer:
        timer = Timer(interval=0.1, function=lambda: connection.execute(sql.SQL("NOTIFY done")))
        timer.start()
        return timer


class TestIniliazation(ListenerBase):
    def test_connection(self, listener: NotificationListener) -> None:
        assert isinstance(listener.connection, Connection)

    def test_callbacks(self, listener: NotificationListener) -> None:
        assert listener.callbacks == {}


class TestCleanup(ListenerBase):
    def test_closes_connection_on_exit(self, listener: NotificationListener) -> None:
        assert not listener.connection.closed
        with listener:
            pass
        assert listener.connection.closed

    def test_closing_the_connection_stops_event_loop(self, listener: NotificationListener) -> None:
        assert not listener.connection.closed
        listener.close()
        listener.start()
        # Wait for the event loop to stop running
        while listener.is_running.is_set():
            time.sleep(0.01)


class Done(Exception):
    pass


class NotificationsBase(ListenerBase):
    @pytest.fixture(autouse=True)
    def done_callback(self, listener: NotificationListener) -> Fixture[Callback]:
        # Statement "NOTIFY done" will stop listener.start() by raising Done exception.
        def done() -> None:
            if listener.is_running.is_set():
                raise Done()

        listener.subscribe_to_channel("done", done)
        return done

    @pytest.fixture
    def callback(self) -> Fixture[MagicMock]:
        return MagicMock()

    @pytest.fixture
    def callback2(self) -> Fixture[MagicMock]:
        return MagicMock()


class TestExecuteAllCallbacks(NotificationsBase):
    def test_calls_registered_callbacks(
        self,
        listener: NotificationListener,
        callback: MagicMock,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        listener.execute_all_callbacks()
        callback.assert_called_once_with()


class TestExecuteCallback(NotificationsBase):
    def test_calls_registered_callback(
        self,
        listener: NotificationListener,
        callback: MagicMock,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        listener.execute_callbacks(channel="channel1")
        callback.assert_called_once_with()

    def test_not_calls_callback_from_another_channel(
        self,
        listener: NotificationListener,
        callback: MagicMock,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        listener.execute_callbacks(channel="channel2")
        callback.assert_not_called()


class TestStartArguments(NotificationsBase):
    def test_calls_registered_callbacks_on_start(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start()
        callback.assert_called_once_with()

    def test_skip_running_callbacks_on_start(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_not_called()


class TestSubscribe(NotificationsBase):
    def test_call_on_notification(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        assert listener.callbacks == {
            "channel1": {callback},
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_called_once_with()


    def test_no_call_on_unrelated_notification(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        assert listener.callbacks == {
            "channel1": {callback},
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY cahnnel2"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_not_called()

    def test_calls_on_multiple_notifications(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        assert listener.callbacks == {
            "channel1": {callback},
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        connection.execute(sql.SQL("NOTIFY channel1"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        assert callback.call_count == 1

    def test_multiple_callbacks(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        callback2: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        listener.subscribe_to_channel("channel1", callback2)
        assert listener.callbacks == {
            "channel1": {callback, callback2},
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_called_once_with()
        callback2.assert_called_once_with()

    def test_multiple_channels(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        callback2: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        listener.subscribe_to_channel("channel2", callback2)
        assert listener.callbacks == {
            "channel1": {callback},
            "channel2": {callback2},
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel2"))
        connection.execute(sql.SQL("NOTIFY channel1"))
        connection.execute(sql.SQL("NOTIFY channel2"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_called_once_with()
        assert callback2.call_count == 1


class TestUnsubscribeFromChannel(NotificationsBase):
    def test_unsubscribe_without_subscription(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        self.done_after_timeout(connection)
        with pytest.raises(KeyError):
            listener.unsubscribe_from_channel("channel1", callback)
        assert listener.callbacks == {
            "done": {done_callback},
        }
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_not_called()

    def test_unsubscribe_with_subscription(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        listener.unsubscribe_from_channel("channel1", callback)
        assert listener.callbacks == {
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_not_called()

    def test_unsubscribe_from_different_channel(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        with pytest.raises(KeyError):
            listener.unsubscribe_from_channel("channel2", callback)
        assert listener.callbacks == {
            "channel1": {callback},
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        connection.execute(sql.SQL("NOTIFY channel2"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_called_once_with()

    def test_unsubscribe_from_different_callback(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        callback2: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        with pytest.raises(KeyError):
            listener.unsubscribe_from_channel("channel1", callback2)
        assert listener.callbacks == {
            "channel1": {callback},
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_called_once_with()


class TestUnsubscribeChannel(NotificationsBase):
    def test_unsubscribe_without_subscription(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        self.done_after_timeout(connection)
        with pytest.raises(KeyError):
            listener.unsubscribe_channel("channel1")
        assert listener.callbacks == {
            "done": {done_callback},
        }
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_not_called()

    def test_unsubscribe_with_subscription(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        listener.unsubscribe_channel("channel1")
        assert listener.callbacks == {
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_not_called()

    def test_unsubscribe_from_different_channel(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        with pytest.raises(KeyError):
            listener.unsubscribe_channel("channel2")
        assert listener.callbacks == {
            "channel1": {callback},
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        connection.execute(sql.SQL("NOTIFY channel2"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_called_once_with()


class TestUnsubscribeAll(NotificationsBase):
    def test_unsubscribe_without_subscription(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.unsubscribe_all()
        assert listener.callbacks == {}
        listener.subscribe_to_channel("done", done_callback)
        assert listener.callbacks == {
            "done": {done_callback},
        }
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_not_called()

    def test_unsubscribe_with_subscription(
        self,
        connection: Connection[TupleRow],
        listener: NotificationListener,
        callback: MagicMock,
        done_callback: Callback,
    ) -> None:
        listener.subscribe_to_channel("channel1", callback)
        listener.unsubscribe_all()
        assert listener.callbacks == {}
        listener.subscribe_to_channel("done", done_callback)
        assert listener.callbacks == {
            "done": {done_callback},
        }
        connection.execute(sql.SQL("NOTIFY channel1"))
        self.done_after_timeout(connection)
        with pytest.raises(Done):
            with listener:
                listener.start(initial_run=False)
        callback.assert_not_called()
