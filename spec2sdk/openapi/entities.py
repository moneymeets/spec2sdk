from enum import StrEnum, auto
from types import NoneType
from typing import Any, Sequence

from spec2sdk.base import Model


class Enumerator[T](Model):
    name: str | None
    value: T


class DataType[T](Model):
    name: str | None
    enumerators: Sequence[Enumerator[T]] | None


class NumericDataType[T](DataType[T]):
    format: str | None

    # https://json-schema.org/draft/2020-12/json-schema-validation#name-validation-keywords-for-num
    minimum: T | None
    maximum: T | None
    exclusive_minimum: T | None
    exclusive_maximum: T | None
    multiple_of: T | None


class IntegerDataType(NumericDataType[int]):
    pass


class NumberDataType(NumericDataType[float]):
    pass


class StringDataType(DataType[str]):
    format: str | None

    # https://json-schema.org/draft/2020-12/json-schema-validation#name-validation-keywords-for-str
    pattern: str | None
    min_length: int | None
    max_length: int | None


class BooleanDataType(DataType[bool]):
    pass


class NullDataType(DataType[NoneType]):
    pass


class ObjectProperty(Model):
    data_type: DataType
    name: str
    description: str | None
    default_value: Any
    is_required: bool


class ObjectDataType(DataType):
    description: str | None
    properties: Sequence[ObjectProperty]
    additional_properties: bool


class ArrayDataType(DataType):
    item_type: DataType

    # https://json-schema.org/draft/2020-12/json-schema-validation#name-validation-keywords-for-arr
    min_items: int | None
    max_items: int | None


class MultiDataType(DataType):
    data_types: Sequence[DataType]


class OneOfDataType(MultiDataType):
    pass


class AnyOfDataType(MultiDataType):
    pass


class AllOfDataType(MultiDataType):
    pass


class ParameterLocation(StrEnum):
    QUERY = auto()
    HEADER = auto()
    PATH = auto()
    COOKIE = auto()


class Parameter(Model):
    name: str
    location: ParameterLocation
    description: str | None
    required: bool
    data_type: DataType
    default_value: Any | None


class Path(Model):
    path: str
    parameters: Sequence[Parameter]


class Content(Model):
    media_type: str
    data_type: DataType


class RequestBody(Model):
    description: str | None
    required: bool
    content: Content


class Response(Model):
    status_code: str
    description: str
    content: Content | None


class Endpoint(Model):
    path: Path
    method: str
    operation_id: str
    summary: str | None
    request_body: RequestBody | None
    responses: Sequence[Response]


class Specification(Model):
    endpoints: Sequence[Endpoint]
