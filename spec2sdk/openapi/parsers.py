from http import HTTPMethod
from typing import Any, Callable, Final, Sequence, TypedDict

from ..registry import Registry
from .entities import (
    AllOfDataType,
    AnyOfDataType,
    ArrayDataType,
    BooleanDataType,
    Content,
    DataType,
    Endpoint,
    Enumerator,
    IntegerDataType,
    NumberDataType,
    ObjectDataType,
    ObjectProperty,
    OneOfDataType,
    Parameter,
    Path,
    RequestBody,
    Response,
    Specification,
    StringDataType,
)
from .exceptions import ParserError
from .predicates import contains, type_equals
from .resolver import SCHEMA_NAME_FIELD

ENUM_VARNAMES_FIELD: Final[str] = "x-enum-varnames"

parsers = Registry()


def parse_enumerators[I, O](schema: dict, type_parser: Callable[[I], O] | None = None) -> Sequence[Enumerator] | None:
    if enum_member_values := schema.get("enum"):
        enum_member_names = schema.get(ENUM_VARNAMES_FIELD, (None,) * len(enum_member_values))

        if len(enum_member_names) != len(enum_member_values):
            raise ParserError(
                f"Number of enum values does not match the number of '{ENUM_VARNAMES_FIELD}' names: "
                f"{enum_member_values=}, {enum_member_names=}",
            )

        return tuple(
            Enumerator(name=name, value=value if (value is None) or (type_parser is None) else type_parser(value))
            for name, value in zip(enum_member_names, enum_member_values)
        )
    else:
        return None


def parse_default_value[I, O](schema: dict, type_parser: Callable[[I], O] | None = None) -> Any | None:
    if "default" in schema:
        value = schema["default"]
        if (value is not None) and (type_parser is not None):
            value = type_parser(value)

        return value
    else:
        return None


class CommonFields(TypedDict):
    name: str | None
    description: str | None
    default_value: Any | None
    enumerators: Sequence[Enumerator] | None
    is_nullable: bool


def parse_common_fields[I, O](
    schema: dict,
    type_parser: Callable[[I], O] | None = None,
) -> CommonFields:
    return CommonFields(
        name=schema.get(SCHEMA_NAME_FIELD),
        description=schema.get("description"),
        default_value=parse_default_value(schema, type_parser),
        enumerators=parse_enumerators(schema, type_parser),
        is_nullable=schema.get("nullable") == "true",
    )


@parsers.register(predicate=type_equals("string"))
def parse_string(schema: dict) -> StringDataType:
    return StringDataType(
        **parse_common_fields(schema=schema, type_parser=str),
        format=schema.get("format"),
        pattern=schema.get("pattern"),
    )


@parsers.register(predicate=type_equals("number"))
def parse_number(schema: dict) -> NumberDataType:
    return NumberDataType(
        **parse_common_fields(schema=schema, type_parser=float),
        format=schema.get("format"),
    )


@parsers.register(predicate=type_equals("integer"))
def parse_integer(schema: dict) -> IntegerDataType:
    return IntegerDataType(
        **parse_common_fields(schema=schema, type_parser=int),
        format=schema.get("format"),
    )


@parsers.register(predicate=type_equals("boolean"))
def parse_boolean(schema: dict) -> BooleanDataType:
    return BooleanDataType(
        **parse_common_fields(schema=schema, type_parser=bool),
    )


@parsers.register(predicate=type_equals("object"))
def parse_object(schema: dict) -> ObjectDataType:
    additional_properties: bool = ("properties" not in schema) and schema.get("additionalProperties") in (
        None,
        True,
        {},
    )

    return ObjectDataType(
        **parse_common_fields(schema=schema),
        properties=tuple(
            ObjectProperty(
                data_type=parsers.convert(property_schema),
                name=property_name,
                is_required=property_name in schema.get("required", ()),
            )
            for property_name, property_schema in schema.get("properties", {}).items()
        ),
        additional_properties=additional_properties,
    )


@parsers.register(predicate=type_equals("array"))
def parse_array(schema: dict) -> ArrayDataType:
    return ArrayDataType(
        **parse_common_fields(schema=schema),
        item_type=parsers.convert(schema["items"]),
    )


@parsers.register(predicate=contains("oneOf"))
def parse_one_of(schema: dict) -> OneOfDataType:
    return OneOfDataType(
        **parse_common_fields(schema=schema),
        data_types=tuple(map(parsers.convert, schema["oneOf"])),
    )


@parsers.register(predicate=contains("anyOf"))
def parse_any_of(schema: dict) -> AnyOfDataType:
    return AnyOfDataType(
        **parse_common_fields(schema=schema),
        data_types=tuple(map(parsers.convert, schema["anyOf"])),
    )


@parsers.register(predicate=contains("allOf"))
def parse_all_of(schema: dict) -> AllOfDataType:
    return AllOfDataType(
        **parse_common_fields(schema=schema),
        data_types=tuple(map(parsers.convert, schema["allOf"])),
    )


def parse_spec(schema: dict) -> Specification:
    endpoints = []

    for path, path_item in schema.get("paths", {}).items():
        # Path item can have different fields, not just HTTP method names
        # https://spec.openapis.org/oas/v3.0.0.html#fixed-fields-6
        operations = tuple(
            (field_name, field_value)
            for field_name, field_value in path_item.items()
            if field_name.upper() in HTTPMethod
        )

        for method, operation in operations:
            parameters = tuple(
                Parameter(
                    name=parameter["name"],
                    location=parameter["in"],
                    description=parameter.get("description"),
                    required=parameter.get("required", False),
                    data_type=parsers.convert(parameter["schema"]),
                    default_value=parameter["schema"].get("default"),
                )
                for parameter in operation.get("parameters", ())
            )

            if body := operation.get("requestBody"):
                if len(body["content"]) != 1:
                    raise ParserError(
                        f"Multiple content items in the request body are not supported: {method=} {path=}",
                    )

                media_type, content = next(iter(body["content"].items()))
                request_body = RequestBody(
                    description=body.get("description"),
                    required=body.get("required", False),
                    content=Content(
                        media_type=media_type,
                        data_type=parsers.convert(content["schema"]),
                    ),
                )
            else:
                request_body = None

            responses = []
            for status_code, response in operation["responses"].items():
                if "content" in response:
                    if len(response["content"]) != 1:
                        raise ParserError(
                            f"Multiple content items in the responses are not supported: "
                            f"{method=} {path=} {status_code=}",
                        )

                    media_type, content = next(iter(response["content"].items()))
                    responses.append(
                        Response(
                            status_code=status_code,
                            description=response["description"],
                            content=Content(
                                media_type=media_type,
                                data_type=parsers.convert(content["schema"]),
                            ),
                        ),
                    )
                else:
                    responses.append(
                        Response(
                            status_code=status_code,
                            description=response["description"],
                            content=None,
                        ),
                    )

            if "operationId" not in operation:
                raise ParserError(f"operationId is missing: {method=} {path=}")

            endpoints.append(
                Endpoint(
                    path=Path(path=path, parameters=parameters),
                    method=method,
                    operation_id=operation["operationId"],
                    summary=operation.get("summary"),
                    request_body=request_body,
                    responses=tuple(responses),
                ),
            )

    return Specification(
        endpoints=endpoints,
    )


def get_root_data_types(spec: Specification) -> Sequence[DataType]:
    """
    Returns the only data types used directly in the parameters, request bodies and responses.
    Duplicates are removed from the result.
    """
    data_types: set[DataType] = set()

    for endpoint in spec.endpoints:
        data_types.update(tuple(parameter.data_type for parameter in endpoint.path.parameters))

        if endpoint.request_body:
            data_types.add(endpoint.request_body.content.data_type)

        data_types.update(tuple(response.content.data_type for response in endpoint.responses if response.content))

    return tuple(data_types)
