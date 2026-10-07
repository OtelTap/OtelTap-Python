"""Settings for OtelTapHttpProtobufReceiver."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OtelTapHttpProtobufReceiverSettings:
    """Settings for OtelTapHttpProtobufReceiver.

    Logging is not configurable here: use the standard `logging` module
    (e.g. `logging.getLogger("oteltap")`) to observe receiver activity.
    """

    http_port: int
    """HTTP port number to listen on."""

    listen_on_all_interfaces: bool = False
    """Should the receiver listen on all network interfaces. When False (default), listens only on loopback interface (127.0.0.1)."""

    print_traces_as_ndjson: bool = False
    """Should traces be printed into standard output (as NDJSON)."""

    print_logs_as_ndjson: bool = False
    """Should logs be printed into standard output (as NDJSON)."""

    print_metrics_as_ndjson: bool = False
    """Should metrics be printed into standard output (as NDJSON)."""

    reemit_traces_to_url: str | None = None
    """URL to re-emit traces to, e.g. http://localhost:4318/v1/traces."""

    reemit_logs_to_url: str | None = None
    """URL to re-emit logs to, e.g. http://localhost:4318/v1/logs."""

    reemit_metrics_to_url: str | None = None
    """URL to re-emit metrics to, e.g. http://localhost:4318/v1/metrics."""
