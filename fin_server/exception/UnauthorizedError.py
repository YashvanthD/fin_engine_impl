class UnauthorizedError(Exception):
    """Raised when authentication fails due to invalid, expired, or malformed token."""
    def __init__(self, message):
        super().__init__(message)

