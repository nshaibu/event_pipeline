import os
import json
import typing
from datetime import datetime
from collections.abc import MutableSet
from dataclasses import asdict
from pydantic_mini.typing import is_builtin_type
from pydantic_mini import BaseModel, MiniAnnotated, Attrib
from .import_utils import import_string
from .exceptions import MultiValueError
from .mixins import ObjectIdentityMixin
from event_pipeline.mixins import BackendIntegrationMixin
from event_pipeline.utils import get_obj_klass_import_str, get_obj_state

__all__ = ["EventResult", "ResultSet"]

T = typing.TypeVar("T", bound="ResultSet")

Result = typing.TypeVar("Result", bound="ObjectIdentityMixin")


class EventResult(BackendIntegrationMixin, BaseModel):
    error: bool
    event_name: str
    content: typing.Any
    task_id: typing.Optional[str]
    init_params: typing.Optional[typing.Dict[str, typing.Any]]
    call_params: typing.Optional[typing.Dict[str, typing.Any]]
    process_id: MiniAnnotated[int, Attrib(default_factory=lambda: os.getpid())]
    creation_time: MiniAnnotated[
        float, Attrib(default_factory=lambda: datetime.now().timestamp())
    ]

    class Config:
        unsafe_hash = False
        frozen = False
        eq = True

    def __hash__(self):
        return hash(self.id)

    def get_state(self) -> typing.Dict[str, typing.Any]:
        state = self.__dict__.copy()
        init_params: typing.Optional[typing.Dict[str, typing.Any]] = state.pop(
            "init_params", None
        )

        if init_params:
            execution_context = init_params.get("execution_context")
            if execution_context and not isinstance(execution_context, str):
                init_params["execution_context"] = execution_context.id
        else:
            init_params = {"execution_context": {}}

        if self.content is not None:
            content_type = type(self.content)
            if not is_builtin_type(content_type):
                state["content"] = {
                    "content_type_import_str": get_obj_klass_import_str(self.content),
                    "state": get_obj_state(self.content),
                }
        state["init_params"] = init_params
        return state

    def set_state(self, state: typing.Dict[str, typing.Any]):
        # TODO handle the init and call params
        init_params = state.pop("init_params", None)
        call_params = state.pop("call_params", None)

        content = state.get("content")
        if isinstance(content, dict) and "content_type_import_str" in content:
            import_str = content["content_type_import_str"]
            content_state = content["state"]
            klass = import_string(import_str)
            instance = klass.__new__(klass)
            instance.__setstate__(content_state)
            state["content"] = instance

        if call_params:
            pass

        if init_params:
            pass

        self.__dict__.update(state)

    def is_error(self) -> bool:
        return self.error

    def as_dict(self):
        return asdict(self)


class EntityContentType:
    """Represents the content type information for an entity."""

    def __init__(
        self,
        backend_import_str: typing.Optional[str] = None,
        entity_content_type: typing.Optional[str] = None,
    ):
        self.backend_import_str = backend_import_str
        self.entity_content_type = entity_content_type

    @classmethod
    def add_entity_content_type(
        cls, entity: ObjectIdentityMixin
    ) -> typing.Optional["EntityContentType"]:
        """Create an EntityContentType from an ObjectIdentityMixin instance."""
        if not entity or not getattr(entity, "id", None):
            return None

        connector = getattr(entity, "_connector", None)
        backend_import_str = None

        if connector:
            backend_import_str = get_obj_klass_import_str(connector)

        return cls(
            backend_import_str=backend_import_str,
            entity_content_type=entity.__object_import_str__,
        )

    def get_backend(self) -> typing.Any:
        """Import and return the backend class."""
        if not self.backend_import_str:
            raise ValueError("No backend import string specified")
        return import_string(self.backend_import_str)

    def get_content_type(self) -> typing.Any:
        """Import and return the content type class."""
        if not self.entity_content_type:
            raise ValueError("No entity content type specified")
        return import_string(self.entity_content_type)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, EntityContentType):
            return False
        return (
            self.backend_import_str == other.backend_import_str
            and self.entity_content_type == other.entity_content_type
        )

    def __hash__(self) -> int:
        return hash((self.backend_import_str, self.entity_content_type))

    def __repr__(self) -> str:
        return f"<EntityContentType: backend={self.backend_import_str}, type={self.entity_content_type}>"


class ResultSet(MutableSet[Result]):
    """A collection of Result objects with filtering and query capabilities."""

    def __init__(self, results: typing.List[Result]) -> None:
        self._content: typing.Dict[str, Result] = {}
        self._context_types: typing.Set[EntityContentType] = set()

        for result in results:
            self._content[result.id] = result
            self._insert_entity(result)

    def __contains__(self, item: Result) -> bool:
        if not getattr(item, "id", None):
            return False
        return item.id in self._content

    def __iter__(self) -> typing.Iterator[Result]:
        return iter(self._content.values())

    def __len__(self) -> int:
        return len(self._content)

    def __getitem__(self, index: int) -> Result:
        """Access a result by index."""
        return list(self._content.values())[index]

    def _insert_entity(self, record: Result) -> None:
        """Insert an entity and track its content type."""
        self._content[record.id] = typing.cast(Result, record)
        content_type = EntityContentType.add_entity_content_type(record)
        if content_type and content_type not in self._context_types:
            self._context_types.add(content_type)

    def add(self, result: typing.Union[Result, "ResultSet"]) -> None:
        """Add a result or merge another ResultSet."""
        if isinstance(result, ResultSet):
            self._content.update(result._content)
            self._context_types.update(result._context_types)
        elif hasattr(result, "id"):
            self._content[result.id] = result
            self._insert_entity(result)
        else:
            raise TypeError(
                f"Expected Result or ResultSet, got {type(result).__name__}"
            )

    def clear(self) -> None:
        """Remove all results."""
        self._content.clear()
        self._context_types.clear()

    def discard(self, result: typing.Union[Result, "ResultSet"]) -> None:
        """Remove a result or results from another ResultSet."""
        if isinstance(result, ResultSet):
            for res in result:
                self._content.pop(res.id, None)
        elif hasattr(result, "id"):  # Changed from EventResult to Result
            self._content.pop(result.id, None)
        else:
            raise TypeError(
                f"Expected Result or ResultSet, got {type(result).__name__}"
            )

    def copy(self) -> "ResultSet":
        """Create a shallow copy of this ResultSet."""
        new = ResultSet([])
        new._content = self._content.copy()
        new._context_types = self._context_types.copy()
        return new

    def get(self, **filters) -> Result:
        """
        Get a single result matching the filters.
        Raises MultiValueError if more than one result is found.
        """
        qs = self.filter(**filters)
        if len(qs) == 0:
            raise KeyError(f"No result found matching filters: {filters}")
        if len(qs) > 1:
            raise MultiValueError(f"More than one result found: {len(qs)}!=1")
        return qs[0]

    # def filter(self, **filter_params) -> "ResultSet":
    #     """Filter results by attribute values."""
    #     # Fast path for ID lookups
    #     if "id" in filter_params:
    #         pk = filter_params["id"]
    #         try:
    #             return ResultSet([self._content[pk]])
    #         except KeyError:
    #             return ResultSet([])
    #
    #     def match_conditions(result: Result) -> bool:
    #         """
    #         Check if a result matches all filter conditions.
    #         TODO: Implement filtering for nested dict and list
    #         """
    #         return all(
    #             getattr(result, key, None) == value
    #             for key, value in filter_params.items()
    #             if hasattr(result, key)
    #         )
    #
    #     filtered_results = list(filter(match_conditions, self._content.values()))
    #     return ResultSet(filtered_results)

    def filter(self, **filter_params) -> "ResultSet":
        """
        Filter results by attribute values with support for nested fields.

        Features:
        - Basic attribute matching (user=x)
        - Nested dictionary lookups (profile__name=y)
        - List/iterable searching (tags__contains=z)
        - Special lookup operators:
            - __contains: Check if value is in a list/iterable
            - __startswith: String starts with value
            - __endswith: String ends with value
            - __icontains: Case-insensitive contains
            - __gt, __gte, __lt, __lte: Comparisons
            - __in: Check if field value is in provided list
            - __exact: Exact matching (default behavior)
            - __isnull: Check if field is None

        Examples:
        - rs.filter(name="Alice") - Basic field matching
        - rs.filter(user__profile__city="New York") - Nested dict lookup
        - rs.filter(tags__contains="urgent") - Check if list contains value
        - rs.filter(name__startswith="A") - String prefix matching
        """
        # Fast path for ID lookups
        if len(filter_params) == 1 and "id" in filter_params:
            pk = filter_params["id"]
            try:
                return ResultSet([self._content[pk]])
            except KeyError:
                return ResultSet([])

        filtered_results = []

        for result in self._content.values():
            if self._matches_filters(result, filter_params):
                filtered_results.append(result)

        return ResultSet(filtered_results)

    def _matches_filters(
        self, result: Result, filters: typing.Dict[str, typing.Any]
    ) -> bool:
        """
        Check if a result matches all filters, supporting nested lookups and operators.

        Args:
            result: The result object to check
            filters: Dictionary of filter parameters

        Returns:
            True if the result matches all filters, False otherwise
        """
        for key, value in filters.items():
            # Check if this is a special lookup with operator
            if "__" in key:
                parts = key.split("__")
                if parts[-1] in self._FILTER_OPERATORS:
                    field_path, operator = parts[:-1], parts[-1]
                    field_path = "__".join(field_path)
                    if not self._check_operator(result, field_path, operator, value):
                        return False
                else:
                    # This is a nested lookup without operator
                    if not self._check_nested_field(result, key.split("__"), value):
                        return False
            else:
                # Simple field comparison
                try:
                    field_value = getattr(result, key, None)
                    if field_value != value:
                        return False
                except (TypeError, ValueError):
                    return False

        return True

    # Dictionary of filter operators and their implementation
    _FILTER_OPERATORS = {
        "contains",
        "startswith",
        "endswith",
        "icontains",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "exact",
        "isnull",
    }

    def _get_field_value(
        self, obj: typing.Any, field_path: typing.List[str]
    ) -> typing.Any:
        """
        Get a value from potentially nested objects.

        Args:
            obj: The object to extract value from
            field_path: List of field names to traverse

        Returns:
            The value at the end of the path or None if not found
        """
        current = obj

        for field in field_path:
            # Handle dictionary access
            if hasattr(current, "__getitem__") and isinstance(current, dict):
                try:
                    current = current[field]
                    continue
                except (KeyError, TypeError):
                    pass

            # Handle object attribute access
            if hasattr(current, field):
                current = getattr(current, field)
                continue

            # Nothing found
            return None

        return current

    def _check_nested_field(
        self, obj: typing.Any, field_path: typing.List[str], expected_value: typing.Any
    ) -> bool:
        """
        Check if a nested field matches the expected value.

        Args:
            obj: The object to check
            field_path: Path to the field
            expected_value: Value to compare against

        Returns:
            True if the field exists and matches the value
        """
        actual_value = self._get_field_value(obj, field_path)
        return actual_value == expected_value

    def _check_operator(
        self, obj: typing.Any, field_path: str, operator: str, filter_value: typing.Any
    ) -> bool:
        """
        Apply a filter operator to a field.

        Args:
            obj: The object to check
            field_path: Path to the field (as string with __ separators)
            operator: The operator to apply
            filter_value: Value to compare against

        Returns:
            True if the condition is met, False otherwise
        """
        actual_value = self._get_field_value(obj, field_path.split("__"))

        # Handle None case for all operators except isnull
        if actual_value is None and operator != "isnull":
            return False

        # Apply the appropriate operator
        if operator == "contains":
            # Check if actual_value contains filter_value
            if hasattr(actual_value, "__contains__"):
                return filter_value in actual_value
            return False

        elif operator == "startswith":
            return isinstance(actual_value, str) and actual_value.startswith(
                filter_value
            )

        elif operator == "endswith":
            return isinstance(actual_value, str) and actual_value.endswith(filter_value)

        elif operator == "icontains":
            if not isinstance(actual_value, str) or not isinstance(filter_value, str):
                return False
            return filter_value.lower() in actual_value.lower()

        elif operator == "gt":
            return actual_value > filter_value

        elif operator == "gte":
            return actual_value >= filter_value

        elif operator == "lt":
            return actual_value < filter_value

        elif operator == "lte":
            return actual_value <= filter_value

        elif operator == "in":
            return actual_value in filter_value

        elif operator == "exact":
            return actual_value == filter_value

        elif operator == "isnull":
            return (actual_value is None) == filter_value

        # Unknown operator
        return False

    def first(self) -> typing.Optional[Result]:
        """Return the first result or None if empty."""
        try:
            return self[0]
        except IndexError:
            return None

    def __str__(self) -> str:
        return str(list(self._content.values()))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {len(self)}>"
