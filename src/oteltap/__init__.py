"""OtelTap: an embeddable OTLP receiver for streaming and asserting on telemetry in tests."""

from importlib.metadata import PackageNotFoundError, version

from .exceptions import OtelTapError, OtelTapInitializationError, OtelTapPollingError
from .oteltap_http_protobuf_receiver import OtelTapHttpProtobufReceiver
from .oteltap_http_protobuf_receiver_settings import OtelTapHttpProtobufReceiverSettings

try:
    __version__ = version("oteltap")
except PackageNotFoundError:
    # Package isn't installed (e.g. running from a source checkout without `pip install -e .`).
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    "OtelTapError",
    "OtelTapInitializationError",
    "OtelTapPollingError",
    "OtelTapHttpProtobufReceiver",
    "OtelTapHttpProtobufReceiverSettings",
]
