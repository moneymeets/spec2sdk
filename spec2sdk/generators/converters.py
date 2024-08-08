from typing import Any, TypedDict

from spec2sdk.generators.entities import (
    BooleanPythonType,
    EnumMember,
    EnumPythonType,
    FilePythonType,
    FloatPythonType,
    IntegerPythonType,
    ListPythonType,
    LiteralPythonType,
    ModelField,
    ModelPythonType,
    OptionalPythonType,
    StrEnumPythonType,
    StringPythonType,
    UnionPythonType,
)
from spec2sdk.generators.identifiers import make_class_name, make_constant_name, make_variable_name
from spec2sdk.generators.predicates import is_binary_format, is_enum, is_instance, is_literal, is_optional, is_str_enum
from spec2sdk.parsers.entities import (
    AllOfDataType,
    AnyOfDataType,
    ArrayDataType,
    BooleanDataType,
    DataType,
    Enumerator,
    IntegerDataType,
    NumberDataType,
    ObjectDataType,
    OneOfDataType,
    StringDataType,
)
from spec2sdk.registry import Registry

converters = Registry()


class CommonFields(TypedDict):
    name: str | None
    type_hint: str | None
    description: str | None
    default_value: Any


def get_common_fields(data_type: DataType, type_hint: str | None = None) -> CommonFields:
    return CommonFields(
        name=make_class_name(data_type.name) if data_type.name else None,
        type_hint=make_class_name(data_type.name) if data_type.name else type_hint,
        description=data_type.description,
        default_value=data_type.default_value,
    )


@converters.register(predicate=is_instance(StringDataType))
def convert_string(data_type: StringDataType) -> StringPythonType:
    return StringPythonType(
        **get_common_fields(data_type, "str"),
    )


@converters.register(predicate=is_instance(IntegerDataType))
def convert_integer(data_type: IntegerDataType) -> IntegerPythonType:
    return IntegerPythonType(
        **get_common_fields(data_type, "int"),
    )


@converters.register(predicate=is_instance(NumberDataType))
def convert_number(data_type: NumberDataType) -> FloatPythonType:
    return FloatPythonType(
        **get_common_fields(data_type, "float"),
    )


@converters.register(predicate=is_instance(BooleanDataType))
def convert_boolean(data_type: BooleanDataType) -> BooleanPythonType:
    return BooleanPythonType(
        **get_common_fields(data_type, "bool"),
    )


@converters.register(predicate=is_instance(ObjectDataType))
def convert_object(data_type: ObjectDataType) -> ModelPythonType:
    fields = []

    for prop in data_type.properties:
        property_data_type = prop.data_type

        if not prop.is_required:
            property_data_type = property_data_type.model_copy(update={"is_nullable": True})

        inner_py_type = converters.convert(property_data_type)

        fields.append(
            ModelField(
                name=make_variable_name(prop.name),
                alias=prop.name,
                type_hint=inner_py_type.type_hint,
                description=prop.data_type.description,
                default_value=inner_py_type.default_value,
                is_required=prop.is_required,
                inner_py_type=inner_py_type,
            ),
        )

    return ModelPythonType(
        **get_common_fields(data_type),
        base_models=(),
        fields=tuple(fields),
        arbitrary_fields_allowed=data_type.additional_properties,
    )


@converters.register(predicate=is_instance(ArrayDataType))
def convert_array(data_type: ArrayDataType) -> ListPythonType:
    inner_py_type = converters.convert(data_type.item_type)

    return ListPythonType(
        **get_common_fields(data_type, f"list[{inner_py_type.type_hint}]"),
        inner_py_type=inner_py_type,
    )


@converters.register(predicate=is_instance((AnyOfDataType, OneOfDataType)))
def convert_one_of(data_type: OneOfDataType | AnyOfDataType) -> UnionPythonType:
    inner_py_types = tuple(map(converters.convert, data_type.data_types))

    return UnionPythonType(
        **get_common_fields(data_type, " | ".join(py_type.type_hint for py_type in inner_py_types)),
        inner_py_types=inner_py_types,
    )


@converters.register(predicate=is_instance(AllOfDataType))
def convert_all_of(data_type: AllOfDataType) -> ModelPythonType:
    if not all(isinstance(inner_data_type, ObjectDataType) for inner_data_type in data_type.data_types):
        raise TypeError("Non-object data types in allOf is not supported")

    nameless_inner_data_types = tuple(
        inner_data_type for inner_data_type in data_type.data_types if inner_data_type.name is None
    )
    if len(nameless_inner_data_types) > 1:
        raise TypeError("Multiple data types without a name in allOf is not supported")

    model_type = convert_object(
        nameless_inner_data_types[0] if nameless_inner_data_types else data_type.data_types[0],
    )

    return ModelPythonType(
        name=make_class_name(data_type.name),
        type_hint=make_class_name(data_type.name),
        description=data_type.description,
        default_value=model_type.default_value,
        base_models=tuple(
            converters.convert(inner_data_type)
            for inner_data_type in data_type.data_types
            if inner_data_type.name is not None
        ),
        fields=model_type.fields if nameless_inner_data_types else (),
        arbitrary_fields_allowed=False,
    )


@converters.register(predicate=is_enum)
def convert_enum(data_type: DataType) -> EnumPythonType:
    def generate_enum_member_name(enumerator: Enumerator) -> str:
        if enumerator.name:
            name = enumerator.name
        elif isinstance(enumerator.value, str):
            name = enumerator.value
        else:
            name = f"{data_type.name}_{enumerator.value}"

        return make_constant_name(name)

    members = tuple(
        EnumMember(name=generate_enum_member_name(member), value=member.value) for member in data_type.enumerators
    )

    default_value = None
    for member in members:
        if member.value == data_type.default_value:
            default_value = member

    return EnumPythonType(
        name=make_class_name(data_type.name),
        type_hint=make_class_name(data_type.name),
        description=data_type.description,
        default_value=default_value,
        members=members,
    )


@converters.register(predicate=is_str_enum)
def convert_str_enum(data_type: StringDataType) -> StrEnumPythonType:
    enum_type = convert_enum(data_type)
    return StrEnumPythonType(
        name=enum_type.name,
        type_hint=enum_type.type_hint,
        description=enum_type.description,
        default_value=enum_type.default_value,
        members=enum_type.members,
    )


@converters.register(predicate=is_binary_format)
def convert_binary(data_type: StringDataType) -> FilePythonType:
    return FilePythonType(
        name="File",
        type_hint="File",
        description=data_type.description,
        default_value=data_type.default_value,
    )


@converters.register(predicate=is_literal)
def convert_literal(data_type: DataType) -> LiteralPythonType:
    literals = tuple(enumerator.value for enumerator in data_type.enumerators)
    return LiteralPythonType(
        name=None,
        type_hint="Literal[" + ",".join(repr(literal) for literal in literals) + "]",
        description=data_type.description,
        default_value=data_type.default_value,
        literals=literals,
    )


@converters.register(predicate=is_optional, priority=99)
def convert_optional(data_type: DataType) -> OptionalPythonType:
    inner_py_type = converters.convert(data_type.model_copy(update={"is_nullable": False}))

    return OptionalPythonType(
        name=None,
        type_hint=f"{inner_py_type.type_hint} | None",
        description=data_type.description,
        default_value=data_type.default_value,
        inner_py_type=inner_py_type,
    )
