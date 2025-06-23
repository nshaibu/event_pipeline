class ApiException(Exception):
    """Base class for API exceptions."""

    def __init__(self, status_code, message=None):
        self.status_code = status_code
        self.message = message or f"API returned status code {status_code}"
        super().__init__(self.message)


class BadRequestException(ApiException):
    """Exception for HTTP 400 Bad Request errors."""

    def __init__(self, message=None):
        super().__init__(400, message or "Bad Request")


class InternalServerErrorException(ApiException):
    """Exception for HTTP 500 Internal Server Error errors."""

    def __init__(self, message=None):
        super().__init__(500, message or "Internal Server Error")


class NotFoundException(ApiException):
    """Exception for HTTP 404 Not Found errors."""

    def __init__(self, message=None):
        super().__init__(404, message or "Not Found")
