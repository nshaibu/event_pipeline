import threading
import typing

from nexus.telemetry.logger import AbstractTelemetryLogger, StandardTelemetryLogger


class TelemetryLoggerFactory:
    _instance = None
    _logger_class = StandardTelemetryLogger

    @classmethod
    def set_logger_class(
        cls, logger_class: typing.Type[AbstractTelemetryLogger]
    ) -> None:
        """Configure which logger implementation to use"""
        if not issubclass(logger_class, AbstractTelemetryLogger):
            raise ValueError("Logger class must implement AbstractTelemetryLogger")
        cls._logger_class = logger_class
        cls._instance = logger_class()

    @classmethod
    def get_logger(cls) -> AbstractTelemetryLogger:
        """Get or create the singleton logger instance"""
        if cls._instance is None:
            if cls._instance is None:
                cls._instance = cls._logger_class()
        return cls._instance
