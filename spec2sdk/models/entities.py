from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import Any, Sequence

from spec2sdk.base import Model
from spec2sdk.models.annotations import TypeAnnotation, TypeConstraint, TypeConstraintParameter
from spec2sdk.models.imports import Import
from spec2sdk.templating import create_jinja_environment


class PythonType(Model, ABC):
    name: str | None

    @property
    def dependency_types(self) -> Sequence["PythonType"]:
        return ()

    @property
    @abstractmethod
    def type_definition(self) -> TypeAnnotation: ...

    @property
    def type_annotation(self) -> TypeAnnotation:
        return (
            TypeAnnotation(type_hint=self.name, type_imports=self.type_definition.type_imports, constraints=())
            if self.name
            else self.type_definition
        )

    @cached_property
    def type_hint(self) -> str:
        return self.type_annotation.render()

    @property
    def imports(self) -> Sequence[Import]:
        return self.type_definition.imports

    @abstractmethod
    def render(self) -> str:
        """
        Returns rendered Python type. Method will only be called if type has a name.
        """
        ...


class SimpleType(PythonType, ABC):
    def render(self) -> str:
        return f"type {self.name} = {self.type_definition.render()}"


class LiteralType(SimpleType):
    literals: Sequence[Any]

    @property
    def type_definition(self) -> TypeAnnotation:
        return TypeAnnotation(
            type_hint="Literal[" + ",".join(repr(literal) for literal in self.literals) + "]",
            type_imports=(Import(name="Literal", package="typing"),),
            constraints=(),
        )


class EnumMember(Model):
    name: str
    value: Any


class EnumMemberView(Model):
    name: str
    value: str


class EnumType(PythonType):
    members: Sequence[EnumMember]

    @property
    def type_definition(self) -> TypeAnnotation:
        return TypeAnnotation(
            type_hint=self.name,
            type_imports=(Import(name="Enum", package="enum"),),
            constraints=(),
        )

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
    def type_definition(self) -> TypeAnnotation:
        return TypeAnnotation(
            type_hint=self.name,
            type_imports=(Import(name="StrEnum", package="enum"),),
            constraints=(),
        )

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


class NumericType[T](SimpleType):
    minimum: T | None
    maximum: T | None
    exclusive_minimum: T | None
    exclusive_maximum: T | None
    multiple_of: T | None

    @property
    @abstractmethod
    def type_name(self) -> str: ...

    @property
    def type_definition(self) -> TypeAnnotation:
        constrained_type = (
            (self.minimum is not None)
            or (self.maximum is not None)
            or (self.exclusive_minimum is not None)
            or (self.exclusive_maximum is not None)
            or (self.multiple_of is not None)
        )

        constraints = (
            (
                TypeConstraint(
                    name="Field",
                    parameters=(
                        *(
                            (TypeConstraintParameter(name="ge", value=self.minimum),)
                            if self.minimum is not None
                            else ()
                        ),
                        *(
                            (TypeConstraintParameter(name="le", value=self.maximum),)
                            if self.maximum is not None
                            else ()
                        ),
                        *(
                            (TypeConstraintParameter(name="gt", value=self.exclusive_minimum),)
                            if self.exclusive_minimum is not None
                            else ()
                        ),
                        *(
                            (TypeConstraintParameter(name="lt", value=self.exclusive_maximum),)
                            if self.exclusive_maximum is not None
                            else ()
                        ),
                        *(
                            (TypeConstraintParameter(name="multiple_of", value=self.multiple_of),)
                            if self.multiple_of is not None
                            else ()
                        ),
                    ),
                    imports=(Import(name="Field", package="pydantic"),),
                ),
            )
            if constrained_type
            else ()
        )

        return TypeAnnotation(type_hint=self.type_name, type_imports=(), constraints=constraints)


class IntegerType(NumericType[int]):
    @property
    def type_name(self) -> str:
        return "int"


class FloatType(NumericType[float]):
    @property
    def type_name(self) -> str:
        return "float"


class BooleanType(SimpleType):
    @property
    def type_definition(self) -> TypeAnnotation:
        return TypeAnnotation(type_hint="bool", type_imports=(), constraints=())


class StringType(SimpleType):
    pattern: str | None
    min_length: int | None
    max_length: int | None

    @property
    def type_definition(self) -> TypeAnnotation:
        constrained_type = bool(self.pattern) or (self.min_length is not None) or (self.max_length is not None)
        constraints = (
            (
                TypeConstraint(
                    name="StringConstraints",
                    parameters=(
                        *(
                            (TypeConstraintParameter(name="pattern", value=f'r"{self.pattern}"'),)
                            if self.pattern is not None
                            else ()
                        ),
                        *(
                            (TypeConstraintParameter(name="min_length", value=self.min_length),)
                            if self.min_length is not None
                            else ()
                        ),
                        *(
                            (TypeConstraintParameter(name="max_length", value=self.max_length),)
                            if self.max_length is not None
                            else ()
                        ),
                    ),
                    imports=(Import(name="StringConstraints", package="pydantic"),),
                ),
            )
            if constrained_type
            else ()
        )

        return TypeAnnotation(type_hint="str", type_imports=(), constraints=constraints)


class BinaryType(SimpleType):
    @property
    def type_definition(self) -> TypeAnnotation:
        return TypeAnnotation(type_hint="bytes", type_imports=(), constraints=())


class ModelField(Model):
    name: str
    alias: str
    description: str | None
    default_value: Any
    is_required: bool
    inner_py_type: PythonType


class ModelFieldView(Model):
    name: str
    type_hint: str


class ModelType(PythonType):
    base_models: Sequence["ModelType"]
    description: str | None
    fields: Sequence[ModelField]
    arbitrary_fields_allowed: bool

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return *tuple(field.inner_py_type for field in self.fields), *self.base_models

    @property
    def type_definition(self) -> TypeAnnotation:
        return TypeAnnotation(
            type_hint=self.name,
            type_imports=(
                *(import_ for field in self.fields for import_ in self.create_field_annotation(field).imports),
                *((Import(name="ConfigDict", package="pydantic"),) if self.arbitrary_fields_allowed else ()),
            ),
            constraints=(),
        )

    def create_field_annotation(self, field: ModelField) -> TypeAnnotation:
        field_constraints = (
            *(
                (TypeConstraintParameter(name="default", value=repr(field.default_value)),)
                if field.default_value is not None or not field.is_required
                else ()
            ),
            *((TypeConstraintParameter(name="alias", value=repr(field.alias)),) if field.name != field.alias else ()),
            *(
                (
                    TypeConstraintParameter(
                        name="description",
                        value=repr(" ".join(field.description.splitlines()).strip()),
                    ),
                )
                if field.description
                else ()
            ),
        )

        return (
            field.inner_py_type.type_annotation.model_copy(
                update={
                    "constraints": (
                        *field.inner_py_type.type_annotation.constraints,
                        TypeConstraint(
                            name="Field",
                            parameters=field_constraints,
                            imports=((Import(name="Field", package="pydantic"),)),
                        ),
                    ),
                },
            )
            if field_constraints
            else field.inner_py_type.type_annotation
        )

    def render(self) -> str:
        base_class_names = tuple(base_model.name for base_model in self.base_models if base_model.name)

        return (
            create_jinja_environment(templates_path=Path(__file__).parent / "templates")
            .get_template("model.j2")
            .render(
                base_class_name=", ".join(base_class_names) if base_class_names else "Model",
                model_type=self,
                fields=tuple(
                    ModelFieldView(name=field.name, type_hint=self.create_field_annotation(field).render())
                    for field in self.fields
                ),
                arbitrary_fields_allowed=self.arbitrary_fields_allowed,
            )
        )


class NoneType(SimpleType):
    @property
    def type_definition(self) -> TypeAnnotation:
        return TypeAnnotation(type_hint="None", type_imports=(), constraints=())


class ListType(SimpleType):
    inner_py_type: PythonType
    min_items: int | None
    max_items: int | None

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return (self.inner_py_type,)

    @property
    def type_definition(self) -> TypeAnnotation:
        constrained_type = (self.min_items is not None) or (self.max_items is not None)
        constraints = (
            (
                TypeConstraint(
                    name="Field",
                    parameters=(
                        *(
                            (TypeConstraintParameter(name="min_length", value=self.min_items),)
                            if self.min_items is not None
                            else ()
                        ),
                        *(
                            (TypeConstraintParameter(name="max_length", value=self.max_items),)
                            if self.max_items is not None
                            else ()
                        ),
                    ),
                    imports=(Import(name="Field", package="pydantic"),),
                ),
            )
            if constrained_type
            else ()
        )

        return TypeAnnotation(
            type_hint=f"list[{self.inner_py_type.type_hint}]",
            type_imports=(),
            constraints=constraints,
        )


class UnionType(SimpleType):
    inner_py_types: Sequence[PythonType]

    @property
    def dependency_types(self) -> Sequence[PythonType]:
        return self.inner_py_types

    @property
    def type_definition(self) -> TypeAnnotation:
        return TypeAnnotation(
            type_hint=" | ".join(py_type.type_hint for py_type in self.inner_py_types),
            type_imports=(),
            constraints=(),
        )
