import types
import typing
from typing_extensions import Annotated
from .constants import UNKNOWN
from .exceptions import ValidationError

__all__ = (
    "Annotated",
    "PipelineAnnotated",
    "Query",
    "get_type",
    "is_optional_type",
    "is_type",
    "is_pipeline_annotated",
    "NoneType"
)


# backward compatibility
NoneType = getattr(types, "NoneType", type(None))


class Query:
    __slots__ = (
        "default",
        "default_factory",
        "required",
        "gt",
        "ge",
        "lt",
        "le",
        "min_length",
        "max_length",
        "pattern",
    )

    def __init__(
        self,
        default: typing.Optional[str] = UNKNOWN,
        default_factory: typing.Optional[typing.Callable[[], typing.Any]] = UNKNOWN,
        required: bool = False,
        gt: typing.Optional[float] = None,
        ge: typing.Optional[float] = None,
        lt: typing.Optional[float] = None,
        le: typing.Optional[float] = None,
        min_length: typing.Optional[int] = None,
        max_length: typing.Optional[int] = None,
        pattern: typing.Optional[typing.Union[str, typing.Pattern]] = None,
    ):
        self.default = default
        self.default_factory = default_factory
        self.required = required
        self.gt = gt
        self.ge = ge
        self.lt = lt
        self.le = le
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern

    def __repr__(self):
        return (
            "Query("
            f"default={self.default!r},"
            f"default_factory={self.default_factory!r},"
            ")"
        )

    def has_default(self):
        return self.default is not UNKNOWN or self.default_factory is not UNKNOWN

    def _get_default(self) -> typing.Any:
        if self.default is not UNKNOWN:
            return self.default
        elif self.default_factory is not UNKNOWN:
            return self.default_factory()

    def validate(self, value: typing.Any, field_name: str) -> typing.Optional[bool]:
        value = value or self._get_default()

        if self.required and value is None:
            raise ValidationError(
                f"Field '{field_name}' is required but not provided (value is None).",
                params={"field_name": field_name},
            )

        for name in ("gt", "ge", "lt", "le", "min_length", "max_length", "pattern"):
            validation_factor = getattr(self, name, None)
            if validation_factor is None:
                continue

            validator = getattr(self, f"_validate_{name}")
            validator(value)
        return True

    def _validate_gt(self, value: typing.Any):
        try:
            if not (value > self.gt):
                raise ValidationError("greater_than", {"gt": _safe_repr(gt)})
            return value
        except TypeError:
            raise TypeError(
                f"Unable to apply constraint 'gt' to supplied value {value!r}"
            )

    def _validate_ge(self, value: typing.Any):
        try:
            if not (value >= self.ge):
                raise ValidationError("greater_than_equal", {"ge": _safe_repr(ge)})
            return value
        except TypeError:
            raise TypeError(
                f"Unable to apply constraint 'ge' to supplied value {value!r}"
            )

    def _validate_lt(self, value: typing.Any):
        try:
            if not (value < self.lt):
                raise ValidationError("less_than", {"lt": _safe_repr(lt)})
            return value
        except TypeError:
            raise TypeError(
                f"Unable to apply constraint 'lt' to supplied value {value!r}"
            )

    def _validate_le(self, value: typing.Any):
        try:
            if not (value <= self.le):
                raise ValidationError("less_than_equal", {"le": _safe_repr(le)})
            return value
        except TypeError:
            raise TypeError(
                f"Unable to apply constraint 'le' to supplied value {value!r}"
            )

    def _validate_min_length(self, value: typing.Any):
        try:
            if not (len(value) >= self.min_length):
                raise ValidationError(
                    "too_short",
                    {
                        "field_type": "Value",
                        "min_length": self.min_length,
                        "actual_length": len(value),
                    },
                )
            return value
        except TypeError:
            raise TypeError(
                f"Unable to apply constraint 'min_length' to supplied value {value!r}"
            )

    def _validate_max_length(self, value: typing.Any):
        try:
            if len(value) > self.max_length:
                raise ValidationError(
                    "too_long",
                    {
                        "field_type": "Value",
                        "max_length": self.max_length,
                        "actual_length": len(value),
                    },
                )
            return value
        except TypeError:
            raise TypeError(
                f"Unable to apply constraint 'max_length' to supplied value {value!r}"
            )

    def _validate_pattern(self, value: typing.Any):
        pass


def is_pipeline_annotated(typ) -> bool:
    origin = typing.get_origin(typ)
    return (
        origin
        and origin is Annotated
        and hasattr(typ, "__args__")
        and Query in typ.__args__
    )


def is_type(typ):
    try:
        is_typ = isinstance(typ, type)
    except TypeError:
        is_typ = False
    return is_typ


def get_type(typ):
    if is_type(typ):
        return typ

    if is_optional_type(typ):
        type_args = typing.get_args(typ)
        if type_args:
            return get_type(type_args[0])
        else:
            return

    origin = typing.get_origin(typ)
    if is_type(origin):
        return origin

    type_args = typing.get_args(typ)
    if len(type_args) > 0:
        return get_type(type_args[0])


def is_optional_type(typ):
    if hasattr(typ, "__origin__") and typ.__origin__ is typing.Union:
        return NoneType in typ.__args__
    elif typ is typing.Optional:
        return True
    return False


class PipelineAnnotated:
    __slots__ = ()

    def __init_subclass__(cls, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.PipelineAnnotated")

    def __new__(cls, *args, **kwargs):
        raise TypeError("Type PipelineAnnotated cannot be instantiated.")

    @typing._tp_cache
    def __class_getitem__(cls, params):
        if not isinstance(params, tuple):
            params = (params, Query())

        if len(params) != 2:
            raise TypeError(
                "PipelineAnnotated[...] should be used with exactly two arguments (a type and a Query)."
            )

        typ = params[0]

        actual_typ = get_type(typ)
        if actual_typ is None:
            raise ValueError("'{}' is not a type".format(params[0]))

        query = params[1]
        if not isinstance(query, Query):
            raise TypeError("Parameter '{}' must be instance of Query".format(1))
        return Annotated[typ, query]
