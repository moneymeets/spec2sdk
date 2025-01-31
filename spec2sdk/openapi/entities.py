from enum import StrEnum, auto
from typing import Any, Sequence

from spec2sdk.base import Model


class Enumerator(Model):
    name: str | None
    value: Any


class DataType(Model):
    name: str | None
    description: str | None
    default_value: Any | None
    enumerators: Sequence[Enumerator] | None
    is_nullable: bool


class IntegerDataType(DataType):
    default_value: int | None
    format: str | None


class NumberDataType(DataType):
    default_value: float | None
    format: str | None


class StringDataType(DataType):
    default_value: str | None
    format: str | None
    pattern: str | None


class BooleanDataType(DataType):
    default_value: bool | None


class ObjectProperty(Model):
    data_type: DataType
    name: str
    is_required: bool


class ObjectDataType(DataType):
    properties: Sequence[ObjectProperty]
    additional_properties: bool


class ArrayDataType(DataType):
    item_type: DataType


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
    operation_id: str | None
    summary: str | None
    request_body: RequestBody | None
    responses: Sequence[Response]


class Specification(Model):
    endpoints: Sequence[Endpoint]
