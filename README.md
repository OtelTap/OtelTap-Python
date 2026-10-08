# OtelTap-Python

**OtelTap** is a Python client library that wraps [OtelTap-Rust](https://github.com/OtelTap/OtelTap-Rust)'s embeddable OTLP (OpenTelemetry Protocol) receiver, giving Python tests an idiomatic, `async`/`async for`-based API to **await and assert on real telemetry** (traces, logs, metrics) emitted by the system under test — instead of guessing timing or mocking the OTel SDK.

[![Python package](https://github.com/OtelTap/OtelTap-Python/actions/workflows/python-package.yml/badge.svg)](https://github.com/OtelTap/OtelTap-Python/actions/workflows/python-package.yml)
[![PyPI](https://img.shields.io/pypi/v/oteltap.svg)](https://pypi.org/project/oteltap/)

## Built for agentic AI development

OtelTap is designed with **AI coding agents ("copilots") as first-class users**, not just an afterthought. Telemetry is one of the richest sources of ground truth about what a system actually did — far more reliable than logs alone or guessing from source code — and OtelTap is built so an agent can close the loop on its own, without a human relaying data back and forth:

1. **Run** an integration/e2e test (or the CLI) that exercises the system under test.
2. **See telemetry instantly** in the console as NDJSON, right in the same tool-call output the agent already reads — no separate viewer, no polling a dashboard, no screenshots.
3. **Infer** what actually happened — which spans fired, what attributes/status/errors show up, what got logged, what metrics moved — directly from that structured output.
4. **Apply code changes** based on that evidence, immediately, and re-run to verify — all within the same agentic loop, with re-emission ensuring humans watching the normal observability stack still see the exact same picture.

## Why

When testing a service that emits OpenTelemetry data, you usually want to:

1. Spin up a lightweight OTLP endpoint the service can point at.
2. Wait for a specific span/log/metric to show up, then assert on its contents.
3. Still let the data flow through to your normal observability stack, so you don't lose visibility while testing.
4. See what's coming through, right in the test/CI console, without attaching a separate viewer.

`OtelTapHttpProtobufReceiver` does all of this from plain Python:

- **Receives** OTLP/HTTP (protobuf) traces, logs, and metrics on a local port.
- Lets you **await** a specific span/log/metric matching a predicate, or **stream** everything as an `AsyncIterator`.
- **Prints incoming telemetry to the console as NDJSON**, one compact JSON object per line — handy for humans, CI logs, and AI coding agents ("copilots") tailing test output.
- **Re-emits** everything it receives to another OTLP/HTTP endpoint, so your usual pipelines/visualizers keep working unmodified while the tap is attached.

## How it works

`OtelTapHttpProtobufReceiver` is a thin, safe Python wrapper around the native `oteltap_core` library (built from [OtelTap-Rust](https://github.com/OtelTap/OtelTap-Rust)), which it calls via `ctypes` (see `src/oteltap/oteltap_core.py`). Under the hood, `oteltap_core` listens on `127.0.0.1:<port>` for standard OTLP/HTTP protobuf requests (`/v1/traces`, `/v1/logs`, `/v1/metrics`), decodes them, and hands each item back to Python, which:

- Parses it into the corresponding generated OTLP protobuf message (`Span`, `LogRecord`, `Metric` — from the [`opentelemetry-proto`](https://pypi.org/project/opentelemetry-proto/) package).
- Fans it out to any active `stream_traces`/`stream_logs`/`stream_metrics` subscribers and any matching `await_trace`/`await_log`/`await_metric` predicates.
- Optionally prints it to the console as NDJSON and/or re-emits it to another OTLP/HTTP endpoint, both handled natively by `oteltap_core`.

Background polling tasks (one per signal type, run via `asyncio.to_thread`) continuously pull decoded items from the native library and dispatch them; `stop()` (or exiting the `async with` block) stops the receiver, cancels the polling tasks, and releases the native handle.

> **Note:** only the **OTLP/HTTP protobuf** transport is supported (`Content-Type: application/x-protobuf`) — this is the recommended encoding for OTLP over HTTP (the OTLP spec treats HTTP/JSON as debug-only). OTLP/gRPC is not implemented.

## Installation

OtelTap is published on [PyPI](https://pypi.org/project/oteltap/) as the [`oteltap`](https://pypi.org/project/oteltap/) package, with a native `oteltap_core` binary bundled for Windows, Linux, and macOS (x64) — no separate Rust toolchain or build step required for consumers.

```sh
pip install oteltap
```

## Usage

```python
import asyncio
from oteltap import OtelTapHttpProtobufReceiver, OtelTapHttpProtobufReceiverSettings

async def main():
    settings = OtelTapHttpProtobufReceiverSettings(
        http_port=4318,
        listen_on_all_interfaces=False,
        print_traces_as_ndjson=True,
        print_logs_as_ndjson=True,
        print_metrics_as_ndjson=True,
        reemit_traces_to_url="http://localhost:14318/v1/traces",
        reemit_logs_to_url="http://localhost:14318/v1/logs",
        reemit_metrics_to_url="http://localhost:14318/v1/metrics",
    )

    async with OtelTapHttpProtobufReceiver(settings) as receiver:
        # ... exercise the system under test, which sends OTLP to http://localhost:4318 ...

        # Await a specific span matching a predicate:
        span = await receiver.await_trace(lambda s: s.name == "checkout")

        # ...or stream everything as it arrives:
        async for log in receiver.stream_logs():
            print(log.body)

asyncio.run(main())
```

| Member | Purpose |
|---|---|
| `OtelTapHttpProtobufReceiver(settings)` + `start()` / `async with ...` | Starts a receiver on `settings.http_port`. Raises `OtelTapInitializationError` on failure. |
| `stream_traces()` / `stream_logs()` / `stream_metrics()` | Returns an `AsyncIterator[T]` yielding every received item of that signal type. |
| `await_trace(predicate, timeout=None)` / `await_log(...)` / `await_metric(...)` | Returns a coroutine that completes as soon as a received item matches `predicate`. |
| `stop()` / `__aexit__` | Stops the receiver, cancels background polling, and releases the native handle. |

`Span`, `LogRecord`, and `Metric` are the standard `opentelemetry-proto` generated types, so all the usual fields (attributes, status, resource, etc.) are available directly on the objects you await or stream.

## Command-line interface

For quick manual checks (or shell scripts/CI steps) that don't need the full Python API, OtelTap also ships a CLI:

```sh
# Listen on the default OTLP/HTTP port (4318), printing all telemetry as NDJSON until Ctrl+C:
oteltap

# Listen on a specific port, and exit 0 as soon as a matching span/log/metric is seen:
oteltap --port 4318 --await-span "(checkout|payment)"
oteltap --await-log "user .* logged in"
oteltap --await-metric "request_count"
```

`--await-span`/`--await-log`/`--await-metric` each take a regex; if several are given, the CLI exits as soon as *any one* of them matches. With none given, it runs until manually interrupted.

## Prerequisites & building from source

- Python 3.10+.
- [Rust toolchain](https://rustup.rs/) — edition 2024, so **Rust 1.85 or newer** — only required to build the native `oteltap_core` dependency yourself (the published package already bundles prebuilt binaries).
- A checkout of **[OtelTap-Rust](https://github.com/OtelTap/OtelTap-Rust) as a sibling directory** to this repo — i.e. both `OtelTap-Rust/` and `OtelTap-Python/` under the same parent folder — if you need to rebuild `oteltap_core` from source.

```
some-parent-folder/
├── OtelTap-Rust/       <-- clone here
└── OtelTap-Python/     <-- this repo
```

Build the native library and drop it into place:

```sh
cd ../OtelTap-Rust/oteltap-core
cargo build --release
```

Then copy the resulting binary (`oteltap_core.dll` / `liboteltap_core.so` / `liboteltap_core.dylib`, depending on OS) into `src/oteltap/native/` in this repo.

Install the Python package in editable mode:

```sh
pip install -e .
```

## Project layout

```
OtelTap-Python/
├── pyproject.toml
└── src/
    └── oteltap/
        ├── oteltap_core.py                          # ctypes P-Invoke surface over the native oteltap_core lib
        ├── oteltap_http_protobuf_receiver.py         # Public API: start/stop, stream_*, await_*
        ├── oteltap_http_protobuf_receiver_settings.py # Settings dataclass passed to the receiver
        ├── exceptions.py                              # OtelTapError, OtelTapInitializationError, OtelTapPollingError
        ├── _message_channel.py                        # Internal pub/sub + predicate-await mechanism
        ├── __main__.py                                # `python -m oteltap` / `oteltap` CLI entry point
        └── native/                                    # Bundled prebuilt oteltap_core binary (per OS)
```

## Status

This is an early-stage project; the public API and error codes may still change.

## Contributing

Is very much welcomed.