class CleanerException(Exception):
    """Base exception for all cleaner errors."""
    pass


class AuthRequiredException(CleanerException):
    """Raised when Telegram user session is not authenticated or expired."""
    pass


class FloodWaitTimeoutException(CleanerException):
    """Raised when Telegram FloodWait exceeds acceptable automated sleep limit."""
    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(f"Telegram FloodWait requires waiting for {seconds} seconds.")


class PermissionDeniedException(CleanerException):
    """Raised when current user does not have permission to leave/delete a chat."""
    pass


class SessionCorruptedError(CleanerException):
    """Raised when an encrypted session file cannot be decrypted or opened."""
    pass


class ConcurrentJobError(CleanerException):
    """Raised when another cleanup or scan job is already active for this account."""
    pass


class UserCancelledException(CleanerException):
    """Raised when an operation is cancelled by the user cooperative event."""
    pass
