from typing import Any, Callable, Sequence, TypedDict

from ..registry import Registry
from .entities import (
    AllOfDataType,
    AnyOfDataType,
    ArrayDataType,
    BooleanDataType,
    Content,
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

parsers = Registry()


def parse_enumerators[V](schema: dict, type_parser: Callable[[V], V] | None = None) -> Sequence[Enumerator] | None:
    if enum_member_values := schema.get("enum"):
        enum_member_names = schema.get("x-enum-varnames", (None,) * len(enum_member_values))

        if len(enum_member_names) != len(enum_member_values):
            raise ValueError(
                f"{enum_member_values}: enum values count do not match the number of `x-enum-varnames` names",
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

    for path, operations in schema.get("paths", {}).items():
        for method, operation in operations.items():
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

            endpoints.append(
                Endpoint(
                    path=Path(path=path, parameters=parameters),
                    method=method,
                    operation_id=operation.get("operationId"),
                    summary=operation.get("summary"),
                    request_body=request_body,
                    responses=tuple(responses),
                ),
            )

    return Specification(
        endpoints=endpoints,
    )
