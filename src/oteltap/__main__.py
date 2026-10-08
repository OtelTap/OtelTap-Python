"""Command-line interface for OtelTap.

Starts OtelTapHttpProtobufReceiver on a given port, printing all
received telemetry (traces, logs, metrics) as NDJSON into stdout. Optionally awaits
a specific span, log record, or metric (matched by a regex against its name/body),
exiting with code 0 as soon as a match is found.

Usage:
    python -m oteltap [--port PORT]
    python -m oteltap --await-span "(MyActivity1|MyActivity2)"
    python -m oteltap --await-log "user .* logged in"
"""

from __future__ import annotations

import argparse
import asyncio
import re

from google.protobuf.json_format import MessageToJson

from .oteltap_http_protobuf_receiver import OtelTapHttpProtobufReceiver
from .oteltap_http_protobuf_receiver_settings import OtelTapHttpProtobufReceiverSettings

DEFAULT_OTLP_HTTP_PORT = 4318
"""Default OTLP HTTP/protobuf port, per the OpenTelemetry spec."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_OTLP_HTTP_PORT,
        help=f"HTTP port to listen on (default: {DEFAULT_OTLP_HTTP_PORT})",
    )
    parser.add_argument("--await-span", metavar="REGEX", help="Exit 0 once a span whose name matches this regex is received")
    parser.add_argument("--await-log", metavar="REGEX", help="Exit 0 once a log record whose body matches this regex is received")
    parser.add_argument("--await-metric", metavar="REGEX", help="Exit 0 once a metric whose name matches this regex is received")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    settings = OtelTapHttpProtobufReceiverSettings(
        http_port=args.port,
        print_traces_as_ndjson=True,
        print_logs_as_ndjson=True,
        print_metrics_as_ndjson=True,
    )

    async with OtelTapHttpProtobufReceiver(settings) as receiver:
        print(f"Listening for OTLP/HTTP telemetry on port {args.port}")

        awaitables = []
        if args.await_span is not None:
            print(f"Awaiting a span whose name matches '{args.await_span}'...")
            span_pattern = re.compile(args.await_span)
            awaitables.append(receiver.await_trace(lambda span: span_pattern.search(span.name) is not None))
        if args.await_log is not None:
            print(f"Awaiting a log record whose body matches '{args.await_log}'...")
            log_pattern = re.compile(args.await_log)
            awaitables.append(receiver.await_log(lambda log: log_pattern.search(log.body.string_value) is not None))
        if args.await_metric is not None:
            print(f"Awaiting a metric whose name matches '{args.await_metric}'...")
            metric_pattern = re.compile(args.await_metric)
            awaitables.append(receiver.await_metric(lambda metric: metric_pattern.search(metric.name) is not None))

        if not awaitables:
            # Nothing to await: just keep receiving (and printing) telemetry until interrupted (Ctrl+C).
            await asyncio.Event().wait()
            return

        # Exit as soon as any one of the requested spans/logs/metrics is matched.
        tasks = [asyncio.ensure_future(awaitable) for awaitable in awaitables]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

        # Print the matched message as nicely formatted JSON, as the very last output before exiting.
        for task in done:
            message = task.result()
            print(f"Received a match:")
            print(MessageToJson(message))


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        pass  # Ctrl+C: exit quietly, OtelTapHttpProtobufReceiver.__aexit__ already stopped the receiver.


if __name__ == "__main__":
    main()
