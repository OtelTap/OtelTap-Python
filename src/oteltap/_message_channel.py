from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
Predicate = Callable[[T], bool]


@dataclass(slots=True)
class _Awaiter(Generic[T]):
    predicate: Predicate[T]
    future: asyncio.Future[T]


# Streams messages and allows awaiting specific messages based on predicates
class _MessageChannel(Generic[T]):

    def __init__(self) -> None:
        self._awaiters: list[_Awaiter[T]] = []
        self._subscribers: set[asyncio.Queue[T | None]] = set()

    # Awaits a message that satisfies the given predicate
    def wait_for(self, predicate: Predicate[T]) -> asyncio.Future[T]:

        # Adding awaiter to the list
        result_future = asyncio.get_running_loop().create_future()
        awaiter = _Awaiter(predicate=predicate, future=result_future)
        self._awaiters.append(awaiter)

        # Removing it from the list, once the matching message has been received
        def remove_awaiter(_):
            if awaiter in self._awaiters:
                self._awaiters.remove(awaiter)
        result_future.add_done_callback(remove_awaiter)

        return result_future

    # Writes a message to the channel, notifying all subscribers and awaiters
    def write(self, message: T) -> None:

        # Notify all subscribers
        for subscriber in self._subscribers:
            subscriber.put_nowait(message)

        # Notify all awaiters whose predicate matches the message
        for i, awaiter in enumerate(self._awaiters):

            # Just in case it already got cancelled
            if awaiter.future.done():
                continue

            try:

                # If predicate matches, set the result and remove the awaiter from the list
                if awaiter.predicate(message):
                    awaiter.future.set_result(message)
                    self._awaiters.pop(i)

            except Exception as err:
                # If predicate itself throws, re-throwing it in the future, so that the caller sees it
                awaiter.future.set_exception(err)
                # No sense keeping this broken awaiter in the list anyway
                self._awaiters.pop(i)

    # Returns all messages in the channel as an asynchronous iterator
    async def stream(self) -> AsyncIterator[T]:
        queue: asyncio.Queue[T | None] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            while True:
                message = await queue.get()
                if message is None:
                    break
                yield message
        finally:
            self._subscribers.discard(queue)

    # Closes the channel, notifying all subscribers with None and clearing the subscriber list
    def close(self) -> None:

        for subscriber in self._subscribers:
            subscriber.put_nowait(None)
        self._subscribers.clear()
