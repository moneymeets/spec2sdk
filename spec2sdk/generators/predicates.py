from typing import Callable, Type

from spec2sdk.parsers.entities import DataType, StringDataType


def is_instance[T](data_class: Type[T] | tuple[Type[T], ...]) -> Callable[[T], bool]:
    def compare(data_type: T) -> bool:
        return isinstance(data_type, data_class)

    return compare


def is_enum(data_type: DataType) -> bool:
    return data_type.name is not None and data_type.enumerators


def is_str_enum(data_type: DataType) -> bool:
    return isinstance(data_type, StringDataType) and is_enum(data_type)


def is_binary_format(data_type: DataType) -> bool:
    return isinstance(data_type, StringDataType) and data_type.format == "binary"


def is_literal(data_type: DataType) -> bool:
    return data_type.name is None and data_type.enumerators


def is_optional(data_type: DataType) -> bool:
    return data_type.is_nullable
