from typing import Any, Self, Sequence

from spec2sdk.base import Model


class PythonType(Model):
    name: str | None
    type_hint: str | None
    description: str | None
    default_value: Any

    @property
    def dependency_types(self) -> Sequence[Self]:
        return ()

    def __hash__(self):
        return hash((self.__class__, self.name or self.type_hint))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.name == other.name
        else:
            return self.model_dump() == other


class LiteralPythonType(PythonType):
    literals: Sequence[Any]


class EnumMember(Model):
    name: str
    value: Any


class EnumPythonType(PythonType):
    name: str
    members: Sequence[EnumMember]
    default_value: EnumMember | None


class StrEnumPythonType(EnumPythonType):
    pass


class IntegerPythonType(PythonType):
    default_value: int | None


class FloatPythonType(PythonType):
    default_value: float | None


class BooleanPythonType(PythonType):
    default_value: bool | None


class StringPythonType(PythonType):
    default_value: str | None


class FilePythonType(PythonType):
    pass


class ModelField(Model):
    name: str
    alias: str
    type_hint: str | None
    description: str | None
    default_value: Any
    is_required: bool
    inner_py_type: PythonType


class ModelPythonType(PythonType):
    base_models: Sequence["ModelPythonType"]
    fields: Sequence[ModelField]
    arbitrary_fields_allowed: bool

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return *tuple(field.inner_py_type for field in self.fields), *self.base_models


class OptionalPythonType(PythonType):
    inner_py_type: PythonType

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return (self.inner_py_type,)


class ListPythonType(PythonType):
    inner_py_type: PythonType

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return (self.inner_py_type,)


class UnionPythonType(PythonType):
    inner_py_types: Sequence[PythonType]

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return self.inner_py_types
