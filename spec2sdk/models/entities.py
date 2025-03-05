import textwrap
from abc import abstractmethod
from pathlib import Path
from typing import Any, Sequence

from spec2sdk.base import Model
from spec2sdk.models.imports import Import
from spec2sdk.templating import create_jinja_environment


class PythonType(Model):
    name: str | None
    description: str | None
    default_value: Any

    @property
    @abstractmethod
    def type_hint(self) -> str: ...

    @property
    @abstractmethod
    def imports(self) -> Sequence[Import]: ...

    @abstractmethod
    def render(self) -> str: ...

    @property
    def dependency_types(self) -> Sequence["PythonType"]:
        return ()


class LiteralType(PythonType):
    literals: Sequence[Any]

    @property
    def type_hint(self) -> str:
        return "Literal[" + ",".join(repr(literal) for literal in self.literals) + "]"

    @property
    def imports(self) -> Sequence[Import]:
        return (Import(name="Literal", package="typing"),)

    def render(self) -> str:
        return f"type {self.name} = {self.type_hint}" if self.name else ""


class EnumMember(Model):
    name: str
    value: Any


class EnumMemberView(Model):
    name: str
    value: str


class EnumType(PythonType):
    members: Sequence[EnumMember]
    default_value: EnumMember | None

    @property
    def type_hint(self) -> str:
        return self.name

    @property
    def imports(self) -> Sequence[Import]:
        return (Import(name="Enum", package="enum"),)

    def render(self) -> str:
        return (
            create_jinja_environment(templates_path=Path(__file__).parent / "templates")
            .get_template("enum.j2")
            .render(
                enum_type=self,
                base_class_name="Enum",
                members=tuple(EnumMemberView(name=member.name, value=member.value) for member in self.members),
            )
        )


class StrEnumType(EnumType):
    @property
    def imports(self) -> Sequence[Import]:
        return (Import(name="StrEnum", package="enum"),)

    def render(self) -> str:
        return (
            create_jinja_environment(templates_path=Path(__file__).parent / "templates")
            .get_template("enum.j2")
            .render(
                enum_type=self,
                base_class_name="StrEnum",
                members=tuple(EnumMemberView(name=member.name, value=f'"{member.value}"') for member in self.members),
            )
        )


class IntegerType(PythonType):
    default_value: int | None

    @property
    def type_hint(self) -> str:
        return self.name or "int"

    @property
    def imports(self) -> Sequence[Import]:
        return ()

    def render(self) -> str:
        return f"type {self.name} = int" if self.name else ""


class FloatType(PythonType):
    default_value: float | None

    @property
    def type_hint(self) -> str:
        return self.name or "float"

    @property
    def imports(self) -> Sequence[Import]:
        return ()

    def render(self) -> str:
        return f"type {self.name} = float" if self.name else ""


class BooleanType(PythonType):
    default_value: bool | None

    @property
    def type_hint(self) -> str:
        return self.name or "bool"

    @property
    def imports(self) -> Sequence[Import]:
        return ()

    def render(self) -> str:
        return f"type {self.name} = bool" if self.name else ""


class StringType(PythonType):
    default_value: str | None

    @property
    def type_hint(self) -> str:
        return self.name or "str"

    @property
    def imports(self) -> Sequence[Import]:
        return ()

    def render(self) -> str:
        return f"type {self.name} = str" if self.name else ""


class BinaryType(PythonType):
    @property
    def type_hint(self) -> str:
        return self.name or "bytes"

    @property
    def imports(self) -> Sequence[Import]:
        return ()

    def render(self) -> str:
        return f"type {self.name} = bytes" if self.name else ""


class ModelField(Model):
    name: str
    alias: str
    type_hint: str
    description: str | None
    default_value: Any
    is_required: bool
    inner_py_type: PythonType


class ModelFieldView(Model):
    name: str
    type_definition: str


class ModelType(PythonType):
    base_models: Sequence["ModelType"]
    fields: Sequence[ModelField]
    arbitrary_fields_allowed: bool

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return *tuple(field.inner_py_type for field in self.fields), *self.base_models

    @property
    def type_hint(self) -> str:
        return self.name

    @property
    def imports(self) -> Sequence[Import]:
        return (
            *((Import(name="Field", package="pydantic"),) if len(self.fields) > 0 else ()),
            *((Import(name="ConfigDict", package="pydantic"),) if self.arbitrary_fields_allowed else ()),
        )

    def render(self) -> str:
        def split_long_lines(s: str) -> str:
            return '"' + ' ""'.join(line.replace('"', r"\"") for line in textwrap.wrap(s, width=80)) + '"'

        def create_model_field_view(field: ModelField) -> ModelFieldView:
            attrs = []

            if field.default_value is not None or not field.is_required:
                attrs.append(f"default={repr(field.default_value)}")

            if field.name != field.alias:
                attrs.append(f'alias="{field.alias}"')

            if field.description:
                attrs.append(f"description={split_long_lines(field.description)}")

            return ModelFieldView(
                name=field.name,
                type_definition=field.type_hint + (f" = Field({','.join(attrs)})" if attrs else ""),
            )

        base_class_names = tuple(base_model.name for base_model in self.base_models if base_model.name)

        return (
            create_jinja_environment(templates_path=Path(__file__).parent / "templates")
            .get_template("model.j2")
            .render(
                base_class_name=", ".join(base_class_names) if base_class_names else "Model",
                model_type=self,
                fields=tuple(map(create_model_field_view, self.fields)),
                arbitrary_fields_allowed=self.arbitrary_fields_allowed,
            )
        )


class OptionalType(PythonType):
    inner_py_type: PythonType

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return (self.inner_py_type,)

    @property
    def type_hint(self) -> str:
        return self.name or f"{self.inner_py_type.type_hint} | None"

    @property
    def imports(self) -> Sequence[Import]:
        return ()

    def render(self) -> str:
        if self.name:
            root_type = f"{self.inner_py_type.type_hint} | None"
            return f"type {self.name} = {root_type}"
        else:
            return ""


class ListType(PythonType):
    inner_py_type: PythonType

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return (self.inner_py_type,)

    @property
    def type_hint(self) -> str:
        return self.name or f"list[{self.inner_py_type.type_hint}]"

    @property
    def imports(self) -> Sequence[Import]:
        return ()

    def render(self) -> str:
        if self.name:
            root_type = f"list[{self.inner_py_type.type_hint}]"
            return f"type {self.name} = {root_type}"
        else:
            return ""


class UnionType(PythonType):
    inner_py_types: Sequence[PythonType]

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return self.inner_py_types

    @property
    def type_hint(self) -> str:
        return self.name or " | ".join(py_type.type_hint for py_type in self.inner_py_types)

    @property
    def imports(self) -> Sequence[Import]:
        return ()

    def render(self) -> str:
        if self.name:
            root_type = " | ".join(py_type.type_hint for py_type in self.inner_py_types)
            return f"type {self.name} = {root_type}"
        else:
            return ""
