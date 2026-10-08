from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any, TypeVar

from opentelemetry.proto.trace.v1.trace_pb2 import Span
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord
from opentelemetry.proto.metrics.v1.metrics_pb2 import Metric

from ._message_channel import _MessageChannel, Predicate
from .exceptions import OtelTapInitializationError, OtelTapPollingError
from .oteltap_core import (
    OtelTapCore,
    OtelTapFlags
)

from .oteltap_http_protobuf_receiver_settings import OtelTapHttpProtobufReceiverSettings

T = TypeVar("T")

_POLL_INTERVAL_MS = 256
"""Timeout (in milliseconds) used for each native poll call while waiting for new telemetry."""


class OtelTapHttpProtobufReceiver:
    """
    Listens for OTLP telemetry in http/protobuf format on a given port.
    Streams it as IAsyncEnumerable.
    Optionally prints it into standard output and re-emits it to given receiver endpoints.
    """

    def __init__(
        self,
        settings: OtelTapHttpProtobufReceiverSettings,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._logger = logger or logging.getLogger(__name__)
        self._handle: int | None = None
        self._poll_tasks: list[asyncio.Task[None]] = []
        self._traces_channel = _MessageChannel[Span]()
        self._logs_channel = _MessageChannel[LogRecord]()
        self._metrics_channel = _MessageChannel[Metric]()

    async def __aenter__(self) -> OtelTapHttpProtobufReceiver:
        return await self.start()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


    async def start(self) -> OtelTapHttpProtobufReceiver:
        """Starts the HTTP/Protobuf receiver."""

        if self._handle is not None:
            return self

        flags = 0
        if self._settings.print_traces_as_ndjson:
            flags |= OtelTapFlags.PRINT_TRACES_AS_NDJSON
        if self._settings.print_logs_as_ndjson:
            flags |= OtelTapFlags.PRINT_LOGS_AS_NDJSON
        if self._settings.print_metrics_as_ndjson:
            flags |= OtelTapFlags.PRINT_METRICS_AS_NDJSON
        if self._settings.listen_on_all_interfaces:
            flags |= OtelTapFlags.LISTEN_ON_ALL_INTERFACES

        status, handle = await asyncio.to_thread(
            OtelTapCore.oteltap_start_receiving_http_protobuf,
            self._settings.http_port,
            flags,
            self._settings.reemit_traces_to_url,
            self._settings.reemit_logs_to_url,
            self._settings.reemit_metrics_to_url,
        )

        if status < 0:
            raise OtelTapInitializationError(
                message=f"oteltap_start_receiving_http_protobuf() failed. Error code: {status}",
                status_code=status,
            )

        self._handle = handle

        # Start polling tasks for traces, logs, and metrics.
        self._poll_tasks = [
            asyncio.create_task(
                self._poll(
                    OtelTapCore.oteltap_poll_trace,
                    Span,
                    self._traces_channel,
                )
            ),
            asyncio.create_task(
                self._poll(
                    OtelTapCore.oteltap_poll_log,
                    LogRecord,
                    self._logs_channel,
                )
            ),
            asyncio.create_task(
                self._poll(
                    OtelTapCore.oteltap_poll_metric,
                    Metric,
                    self._metrics_channel,
                )
            ),
        ]

        return self


    async def stop(self) -> None:
        """Stops the receiver."""

        handle = self._handle
        if handle is None:
            return
        self._handle = None

        for task in self._poll_tasks:
            task.cancel()
        await asyncio.gather(*self._poll_tasks, return_exceptions=True)
        self._poll_tasks.clear()

        status = await asyncio.to_thread(OtelTapCore.oteltap_stop_receiving, handle)
        if status < 0:
            self._logger.warning(f"oteltap_stop_receiving() failed. Error code:  {status}")

        self._traces_channel.close()
        self._logs_channel.close()
        self._metrics_channel.close()


    def stream_traces(self) -> AsyncIterator[Span]:
        """Enumerates through all received traces"""
        return self._traces_channel.stream()

    def stream_logs(self) -> AsyncIterator[LogRecord]:
        """Enumerates through all received logs"""
        return self._logs_channel.stream()

    def stream_metrics(self) -> AsyncIterator[Metric]:
        """Enumerates through all received metrics"""
        return self._metrics_channel.stream()

    async def await_trace(self, predicate: Predicate[Span], timeout: float | None = None) -> Span:
        """Awaits a trace that matches the given predicate."""
        return await self._await_message(self._traces_channel, predicate, timeout)

    async def await_log(self, predicate: Predicate[LogRecord], timeout: float | None = None) -> LogRecord:
        """Awaits a log that matches the given predicate."""
        return await self._await_message(self._logs_channel, predicate, timeout)

    async def await_metric(self, predicate: Predicate[Metric], timeout: float | None = None) -> Metric:
        """Awaits a metric that matches the given predicate."""
        return await self._await_message(self._metrics_channel, predicate, timeout)


    async def _poll(
        self,
        poll: Callable[[int, int], tuple[int, bytes | None]],
        message_type,
        channel: _MessageChannel,
    ) -> None:
        while True:

            status, data = await asyncio.to_thread(poll, self._handle, _POLL_INTERVAL_MS)

            if status < 0:
                raise OtelTapPollingError(
                    message=f"Polling failed for message type {message_type}. Error code: {status}",
                    status_code=status,
                )
            
            if data is not None:
                # data is a serialized protobuf message, in bytes. FromString() is historically named so, it takes bytes.
                channel.write(message_type.FromString(data))


    async def _await_message(
        self,
        channel: _MessageChannel[T],
        predicate: Predicate[T],
        timeout: float | None = None,
    ) -> T:

        future = channel.wait_for(predicate)

        try:
            if timeout is None:
                return await future
            
            return await asyncio.wait_for(future, timeout)
        
        except BaseException:
            future.cancel()
            raise
