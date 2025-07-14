from pathlib import Path


class DataFileError(Exception):
    """Custom exception for handling data file issues."""

    def __init__(self, message: str, file_path=None):
        self.message = message
        self.file_path = file_path
        super().__init__(self.message)

    def __str__(self):
        if self.file_path:
            return f"{self.message} (File: {self.file_path})"
        return self.message


class JsonDataError(Exception):
    """Raised when sending an email notification fails."""

    def __init__(
        self, message: str, original_exception: Exception = None, file_path: Path = None
    ):
        self.message = message
        self.original_exception = original_exception
        full_message = f"{message}  {file_path}"
        if original_exception:
            self.message += f" | Cause: {str(original_exception)}"
        super().__init__(full_message)


class EmailNotificationError(Exception):
    """Raised when sending an email notification fails."""

    def __init__(
        self, message: str, recipient: str = "", original_exception: Exception = None
    ):
        self.message = message
        self.recipient = recipient
        self.original_exception = original_exception
        full_message = f"{message} (Recipient: {recipient})"
        if original_exception:
            full_message += f" | Cause: {str(original_exception)}"
        super().__init__(full_message)
