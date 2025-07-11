import typing
from dataclasses import dataclass

from event_pipeline.typing import ConfigState, ConfigurableValue


@dataclass
class ExecutorInitializerConfig:
    """
    Configuration for executor initialization.

    For each field:
    - UNSET: Use system defaults
    - None: Explicitly disable feature
    - Value: Use provided configuration
    """

    max_workers: ConfigurableValue[int] = ConfigState.UNSET
    max_tasks_per_child: ConfigurableValue[int] = ConfigState.UNSET
    thread_name_prefix: ConfigurableValue[str] = ConfigState.UNSET
    host: ConfigurableValue[str] = ConfigState.UNSET
    port: ConfigurableValue[int] = ConfigState.UNSET
    timeout: ConfigurableValue[int] = 30
    use_encryption: bool = False
    client_cert_path: typing.Optional[str] = None
    client_key_path: typing.Optional[str] = None
    ca_cert_path: typing.Optional[str] = None

    def resolve_max_workers(self, system_default: int = 4) -> typing.Optional[int]:
        if self.max_workers is ConfigState.UNSET:
            return system_default
        return self.max_workers

    def is_configured(self, field_name: str) -> bool:
        value = getattr(self, field_name)
        return value is not ConfigState.UNSET

    @classmethod
    def from_dict(cls, config_dict: dict) -> "ExecutorInitializerConfig":
        kwargs = {}
        for field_name, field_type in cls.__annotations__.items():
            if field_name in config_dict:
                kwargs[field_name] = config_dict[field_name]
            # Leave as default (UNSET) if not in dict
        return cls(**kwargs)
