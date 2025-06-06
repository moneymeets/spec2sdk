from spec2sdk.models.entities import (
    BinaryType,
    BooleanType,
    EnumMember,
    EnumType,
    FloatType,
    IntegerType,
    ListType,
    LiteralType,
    ModelField,
    ModelType,
    NoneType,
    StrEnumType,
    StringType,
    UnionType,
)
from spec2sdk.models.identifiers import make_class_name, make_constant_name, make_variable_name
from spec2sdk.models.predicates import is_binary_format, is_enum, is_instance, is_literal, is_str_enum
from spec2sdk.openapi.entities import (
    AllOfDataType,
    AnyOfDataType,
    ArrayDataType,
    BooleanDataType,
    DataType,
    Enumerator,
    IntegerDataType,
    NullDataType,
    NumberDataType,
    ObjectDataType,
    OneOfDataType,
    StringDataType,
)
from spec2sdk.registry import Registry

converters = Registry()


def make_type_class_name(data_type: DataType) -> str | None:
    return make_class_name(data_type.name) if data_type.name else None


@converters.register(predicate=is_instance(StringDataType))
def convert_string(data_type: StringDataType) -> StringType:
    return StringType(
        name=make_type_class_name(data_type),
        pattern=data_type.pattern,
        min_length=data_type.min_length,
        max_length=data_type.max_length,
    )


@converters.register(predicate=is_instance(IntegerDataType))
def convert_integer(data_type: IntegerDataType) -> IntegerType:
    return IntegerType(
        name=make_type_class_name(data_type),
        minimum=data_type.minimum,
        maximum=data_type.maximum,
        exclusive_minimum=data_type.exclusive_minimum,
        exclusive_maximum=data_type.exclusive_maximum,
        multiple_of=data_type.multiple_of,
    )


@converters.register(predicate=is_instance(NumberDataType))
def convert_number(data_type: NumberDataType) -> FloatType:
    return FloatType(
        name=make_type_class_name(data_type),
        minimum=data_type.minimum,
        maximum=data_type.maximum,
        exclusive_minimum=data_type.exclusive_minimum,
        exclusive_maximum=data_type.exclusive_maximum,
        multiple_of=data_type.multiple_of,
    )


@converters.register(predicate=is_instance(BooleanDataType))
def convert_boolean(data_type: BooleanDataType) -> BooleanType:
    return BooleanType(name=make_type_class_name(data_type))


@converters.register(predicate=is_instance(ObjectDataType))
def convert_object(data_type: ObjectDataType) -> ModelType:
    return ModelType(
        name=make_type_class_name(data_type),
        base_models=(),
        description=data_type.description,
        fields=tuple(
            ModelField(
                name=make_variable_name(prop.name),
                alias=prop.name,
                description=prop.description if inner_py_type.name is None else None,
                default_value=prop.default_value,
                is_required=prop.is_required,
                inner_py_type=inner_py_type,
            )
            for prop in data_type.properties
            if (
                inner_py_type := converters.convert(
                    prop.data_type
                    if prop.is_required
                    else OneOfDataType(
                        name=None,
                        enumerators=None,
                        data_types=(
                            prop.data_type,
                            NullDataType(name=None, enumerators=None),
                        ),
                    ),
                )
            )
        ),
        arbitrary_fields_allowed=data_type.additional_properties,
    )


@converters.register(predicate=is_instance(ArrayDataType))
def convert_array(data_type: ArrayDataType) -> ListType:
    return ListType(
        name=make_type_class_name(data_type),
        inner_py_type=converters.convert(data_type.item_type),
        min_items=data_type.min_items,
        max_items=data_type.max_items,
    )


@converters.register(predicate=is_instance((AnyOfDataType, OneOfDataType)))
def convert_one_of(data_type: OneOfDataType | AnyOfDataType) -> UnionType:
    inner_py_types = tuple(map(converters.convert, data_type.data_types))

    return UnionType(
        name=make_type_class_name(data_type),
        inner_py_types=inner_py_types,
    )


@converters.register(predicate=is_instance(AllOfDataType))
def convert_all_of(data_type: AllOfDataType) -> ModelType:
    if not all(
        isinstance(inner_data_type, (ObjectDataType, AllOfDataType)) for inner_data_type in data_type.data_types
    ):
        raise TypeError("Non-object data types in allOf are not supported")

    nameless_inner_data_types = tuple(
        inner_data_type for inner_data_type in data_type.data_types if inner_data_type.name is None
    )
    if len(nameless_inner_data_types) > 1:
        raise TypeError("Multiple data types without a name in allOf is not supported")

    model_type = convert_object(
        nameless_inner_data_types[0] if nameless_inner_data_types else data_type.data_types[0],
    )

    return ModelType(
        name=make_class_name(data_type.name),
        description=None,
        base_models=tuple(
            converters.convert(inner_data_type)
            for inner_data_type in data_type.data_types
            if inner_data_type.name is not None
        ),
        fields=model_type.fields if nameless_inner_data_types else (),
        arbitrary_fields_allowed=False,
    )


@converters.register(predicate=is_enum)
def convert_enum(data_type: DataType) -> EnumType:
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

    return EnumType(
        name=make_class_name(data_type.name),
        members=members,
    )


@converters.register(predicate=is_str_enum)
def convert_str_enum(data_type: StringDataType) -> StrEnumType:
    return StrEnumType(**convert_enum(data_type).model_dump())


@converters.register(predicate=is_binary_format)
def convert_binary(data_type: StringDataType) -> BinaryType:
    return BinaryType(name=make_type_class_name(data_type))


@converters.register(predicate=is_literal)
def convert_literal(data_type: DataType) -> LiteralType:
    return LiteralType(
        name=None,
        literals=tuple(enumerator.value for enumerator in data_type.enumerators or ()),
    )


@converters.register(predicate=is_instance(NullDataType))
def convert_none(data_type: NullDataType) -> NoneType:
    return NoneType(name=data_type.name)
