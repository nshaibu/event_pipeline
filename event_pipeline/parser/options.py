import typing
import dataclasses
from enum import Enum, StrEnum
from pydantic_mini import BaseModel, MiniAnnotated, Attrib


class StopCondition(Enum):
    """Defines when task execution should stop."""

    NEVER = "never"
    ON_ERROR = "on_error"
    ON_SUCCESS = "on_success"
    ON_EXCEPTION = "on_exception"
    ON_ANY = "on_any"


class ResultEvaluationStrategy(StrEnum):
    pass


class Options(BaseModel):
    """
    Task execution configuration options that can be passed to a task or
    task groups in pointy scripts e.g A[retry_attempts=3], {A->B}[retry_attempts=3].
    """

    # Core execution options with validation
    retry_attempts: MiniAnnotated[int, Attrib(default=0, ge=0)]
    executor: MiniAnnotated[typing.Optional[str], Attrib(default=None)]

    # Configuration dictionaries
    executor_config: MiniAnnotated[dict, Attrib(default_factory=dict)]
    extras: MiniAnnotated[dict, Attrib(default_factory=dict)]

    # Execution state and control
    result_evaluation_strategy: MiniAnnotated[
        typing.Union[ResultEvaluationStrategy, str], Attrib(default="default")
    ]
    stop_condition: typing.Optional[StopCondition]
    bypass_event_checks: typing.Optional[bool]

    class Config:
        disable_typecheck = False
        disable_all_validation = False

    @classmethod
    def from_dict(cls, options_dict: typing.Dict[str, typing.Any]) -> "Options":
        """
        Create Options instance from dictionary, placing unknown fields in extras.

        Args:
            options_dict: Dictionary containing option values

        Returns:
            Options instance with known fields populated and unknown fields in extras
        """
        known_fields = {field.name for field in dataclasses.fields(cls)}

        option = {}
        for field_name, value in options_dict.items():
            if field_name in known_fields:
                option[field_name] = value
            else:
                # Place unknown fields in extras
                if "extras" not in option:
                    option["extras"] = {}
                option["extras"][field_name] = value

        return cls.loads(option, _format="dict")

    def has_retry_policy(self) -> bool:
        """Check if retry policy is configured."""
        return self.retry_attempts is not None and self.retry_attempts > 0

    def should_stop_on(self, condition: str) -> bool:
        """
        Check if execution should stop on given condition.

        Args:
            condition: Condition to check ("error", "success", "exception")

        Returns:
            True if should stop on this condition
        """
        if self.stop_condition is None:
            return False

        condition_map = {
            "error": StopCondition.ON_ERROR,
            "success": StopCondition.ON_SUCCESS,
            "exception": StopCondition.ON_EXCEPTION,
        }

        target_condition = condition_map.get(condition.lower())
        if target_condition is None:
            return False

        return self.stop_condition in [target_condition, StopCondition.ON_ANY]

    def merge_with(self, other: typing.Union["Options", dict]) -> "Options":
        """
        Merge this Options with another, with other taking precedence.

        Args:
            other: Other Options instance to merge with

        Returns:
            New Options instance with merged values
        """
        # Convert both to dicts
        self_dict = self.dump(_format="dict")
        other_dict = other.dump(_format="dict") if isinstance(other, Options) else other

        # Merge extras separately to avoid overwriting
        merged_extras = {**self_dict.get("extras", {}), **other_dict.get("extras", {})}

        # Merge main options (other takes precedence for non-None values)
        merged = self_dict.copy()
        for key, value in other_dict.items():
            if key == "extras":
                continue
            if value is not None:
                merged[key] = value

        merged["extras"] = merged_extras
        return self.from_dict(merged)
