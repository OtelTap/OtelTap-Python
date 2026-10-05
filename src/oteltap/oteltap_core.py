"""P/Invoke-style wrapper around the native oteltap_core lib."""

import ctypes
import os
import platform
from enum import IntFlag


class OtelTapFlags(IntFlag):
    """Bitwise flags for oteltap_start_receiving_http_protobuf, mirroring ffi_functions_flags.rs."""

    NONE = 0
    PRINT_TRACES_AS_NDJSON = 1 << 0
    PRINT_LOGS_AS_NDJSON = 1 << 1
    PRINT_METRICS_AS_NDJSON = 1 << 2

    LISTEN_ON_ALL_INTERFACES = 1 << 8


def _resolve_library_path() -> str:
    """Cross-platform resolver for the native oteltap_core lib."""

    system = platform.system()
    if system == "Windows":
        file_name = "oteltap_core.dll"
    elif system == "Darwin":
        file_name = "liboteltap_core.dylib"
    else:
        file_name = "liboteltap_core.so"

    native_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "native")
    return os.path.join(native_dir, file_name)


class OtelTapCore:
    """P/Invoke-style wrapper around the native oteltap_core lib."""

    _lib = ctypes.CDLL(_resolve_library_path())

    # int oteltap_start_receiving_http_protobuf(
    #     ushort port,
    #     OtelTapFlags flags,
    #     string? reemitTracesTo,
    #     string? reemitLogsTo,
    #     string? reemitMetricsTo,
    #     out ulong outHandle)
    _lib.oteltap_start_receiving_http_protobuf.argtypes = [
        ctypes.c_uint16,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint64),
    ]
    _lib.oteltap_start_receiving_http_protobuf.restype = ctypes.c_int32

    # int oteltap_stop_receiving(ulong handle)
    _lib.oteltap_stop_receiving.argtypes = [ctypes.c_uint64]
    _lib.oteltap_stop_receiving.restype = ctypes.c_int32

    # int oteltap_poll_trace(ulong handle, ulong timeoutMs, out nint outBuf, out nuint outLen)
    _lib.oteltap_poll_trace.argtypes = [
        ctypes.c_uint64,
        ctypes.c_uint64,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    _lib.oteltap_poll_trace.restype = ctypes.c_int32

    # int oteltap_poll_log(ulong handle, ulong timeoutMs, out nint outBuf, out nuint outLen)
    _lib.oteltap_poll_log.argtypes = [
        ctypes.c_uint64,
        ctypes.c_uint64,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    _lib.oteltap_poll_log.restype = ctypes.c_int32

    # int oteltap_poll_metric(ulong handle, ulong timeoutMs, out nint outBuf, out nuint outLen)
    _lib.oteltap_poll_metric.argtypes = [
        ctypes.c_uint64,
        ctypes.c_uint64,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    _lib.oteltap_poll_metric.restype = ctypes.c_int32

    @staticmethod
    def oteltap_start_receiving_http_protobuf(
        port: int,
        flags: OtelTapFlags,
        reemit_traces_to: str | None,
        reemit_logs_to: str | None,
        reemit_metrics_to: str | None,
    ) -> tuple[int, int]:
        """
        Starts OtelTap receiver on the specified port, expecting http/protobuf format,
        with optional re-emission endpoints for traces, logs, and metrics.

        Returns a tuple of (result_code, out_handle).
        """

        out_handle = ctypes.c_uint64(0)
        result = OtelTapCore._lib.oteltap_start_receiving_http_protobuf(
            port,
            int(flags),
            reemit_traces_to.encode("utf-8") if reemit_traces_to is not None else None,
            reemit_logs_to.encode("utf-8") if reemit_logs_to is not None else None,
            reemit_metrics_to.encode("utf-8") if reemit_metrics_to is not None else None,
            ctypes.byref(out_handle),
        )
        return result, out_handle.value

    @staticmethod
    def oteltap_stop_receiving(handle: int) -> int:
        """Stops the OtelTap receiver associated with the given handle, cleaning up resources."""

        return OtelTapCore._lib.oteltap_stop_receiving(handle)

    @staticmethod
    def oteltap_poll_trace(handle: int, timeout_ms: int) -> tuple[int, bytes | None]:
        """Polls for a trace span. On success, returns a protobuf-encoded Span."""

        return OtelTapCore._internal_poll(OtelTapCore._lib.oteltap_poll_trace, handle, timeout_ms)

    @staticmethod
    def oteltap_poll_log(handle: int, timeout_ms: int) -> tuple[int, bytes | None]:
        """Polls for a log record. Same buffer ownership rules as oteltap_poll_trace."""

        return OtelTapCore._internal_poll(OtelTapCore._lib.oteltap_poll_log, handle, timeout_ms)

    @staticmethod
    def oteltap_poll_metric(handle: int, timeout_ms: int) -> tuple[int, bytes | None]:
        """Polls for a metric. Same buffer ownership rules as oteltap_poll_trace."""

        return OtelTapCore._internal_poll(OtelTapCore._lib.oteltap_poll_metric, handle, timeout_ms)

    @staticmethod
    def _internal_poll(native_func, handle: int, timeout_ms: int) -> tuple[int, bytes | None]:
        out_buf = ctypes.c_void_p()
        out_len = ctypes.c_size_t()
        result = native_func(handle, timeout_ms, ctypes.byref(out_buf), ctypes.byref(out_len))

        if result != 0 or not out_buf.value or out_len.value == 0:
            return result, None

        data = ctypes.string_at(out_buf.value, out_len.value)
        return result, data
