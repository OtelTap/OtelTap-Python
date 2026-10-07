
class OtelTapError(Exception):
    """Base exception class for OtelTap errors.""" 

class OtelTapInitializationError(OtelTapError):
    """Thrown if OtelTap fails to initialize."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code

class OtelTapPollingError(OtelTapError):
    """Thrown if OtelTap fails to poll data."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code
