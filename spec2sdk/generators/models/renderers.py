import textwrap
from pathlib import Path
from typing import Sequence

from jinja2 import Environment, FileSystemLoader

from spec2sdk.generators.entities import (
    BooleanPythonType,
    EnumPythonType,
    FilePythonType,
    FloatPythonType,
    IntegerPythonType,
    ListPythonType,
    LiteralPythonType,
    ModelField,
    ModelPythonType,
    OptionalPythonType,
    PythonType,
    StrEnumPythonType,
    StringPythonType,
    UnionPythonType,
)
from spec2sdk.generators.models.entities import TypeRenderer
from spec2sdk.generators.predicates import is_instance
from spec2sdk.registry import Registry

from ...base import Model
from ..imports import Import

renderers = Registry()


def create_jinja_environment() -> Environment:
    return Environment(loader=FileSystemLoader(f"{Path(__file__).parent}/templates"))


def render_root_model(
    py_type: PythonType,
    extra_imports: Sequence[Import] = (),
    content: str = "",
) -> TypeRenderer:
    return TypeRenderer(
        imports=(
            *extra_imports,
            *((Import(name="RootModel", package="pydantic"),) if py_type.name else ()),
        ),
        content=f"{py_type.name} = RootModel[{content}]" if py_type.name else None,
    )


@renderers.register(predicate=is_instance(IntegerPythonType))
def render_integer(py_type: IntegerPythonType) -> TypeRenderer:
    return render_root_model(py_type, content="int")


@renderers.register(predicate=is_instance(FloatPythonType))
def render_float(py_type: FloatPythonType) -> TypeRenderer:
    return render_root_model(py_type, content="float")


@renderers.register(predicate=is_instance(BooleanPythonType))
def render_boolean(py_type: BooleanPythonType) -> TypeRenderer:
    return render_root_model(py_type, content="bool")


@renderers.register(predicate=is_instance(StringPythonType))
def render_string(py_type: StringPythonType) -> TypeRenderer:
    return render_root_model(py_type, content="str")


@renderers.register(predicate=is_instance(OptionalPythonType))
def render_optional(py_type: OptionalPythonType) -> TypeRenderer:
    return render_root_model(
        py_type=py_type,
        content=f"{py_type.inner_py_type.type_hint} | None",
    )


@renderers.register(predicate=is_instance(ListPythonType))
def render_list(py_type: ListPythonType) -> TypeRenderer:
    return render_root_model(
        py_type=py_type,
        content=f"list[{py_type.inner_py_type.type_hint}]",
    )


@renderers.register(predicate=is_instance(FilePythonType))
def render_file(py_type: FilePythonType) -> TypeRenderer:
    return TypeRenderer(
        imports=(Import(name="NamedTuple", package="typing"),),
        content="""
class File(NamedTuple):
    name: str
    content: bytes
"""
        if py_type.name is not None
        else None,
    )


@renderers.register(predicate=is_instance(LiteralPythonType))
def render_literal(py_type: LiteralPythonType) -> TypeRenderer:
    return render_root_model(
        py_type=py_type,
        extra_imports=(Import(name="Literal", package="typing"),),
        content="Literal[" + ",".join(repr(literal) for literal in py_type.literals) + "]",
    )


class EnumMemberView(Model):
    name: str
    value: str


@renderers.register(predicate=is_instance(EnumPythonType))
def render_enum(py_type: EnumPythonType) -> TypeRenderer:
    return TypeRenderer(
        imports=(Import(name="Enum", package="enum"),),
        content=(
            create_jinja_environment()
            .get_template("enum.j2")
            .render(
                enum_type=py_type,
                base_class_name="Enum",
                members=tuple(EnumMemberView(name=member.name, value=member.value) for member in py_type.members),
            )
            if py_type.name is not None
            else None
        ),
    )


@renderers.register(predicate=is_instance(StrEnumPythonType))
def render_str_enum(py_type: StrEnumPythonType) -> TypeRenderer:
    return TypeRenderer(
        imports=(Import(name="StrEnum", package="enum"),),
        content=(
            create_jinja_environment()
            .get_template("enum.j2")
            .render(
                enum_type=py_type,
                base_class_name="StrEnum",
                members=tuple(
                    EnumMemberView(name=member.name, value=f'"{member.value}"') for member in py_type.members
                ),
            )
            if py_type.name is not None
            else None
        ),
    )


@renderers.register(predicate=is_instance(UnionPythonType))
def render_union(py_type: UnionPythonType) -> TypeRenderer:
    return render_root_model(
        py_type,
        content=" | ".join(py_type.type_hint for py_type in py_type.inner_py_types),
    )


class ModelFieldView(Model):
    name: str
    type_definition: str


@renderers.register(predicate=is_instance(ModelPythonType))
def render_model(py_type: ModelPythonType) -> TypeRenderer:
    def split_long_lines(s: str) -> str:
        return '"' + '""'.join(line.replace('"', r"\"") for line in textwrap.wrap(s, width=80)) + '"'

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
            type_definition=field.inner_py_type.type_hint + (f' = Field({",".join(attrs)})' if attrs else ""),
        )

    base_class_names = tuple(base_model.name for base_model in py_type.base_models if base_model.name)

    return TypeRenderer(
        imports=(
            *((Import(name="Field", package="pydantic"),) if len(py_type.fields) > 0 else ()),
            *((Import(name="ConfigDict", package="pydantic"),) if py_type.arbitrary_fields_allowed else ()),
        ),
        content=(
            create_jinja_environment()
            .get_template("model.j2")
            .render(
                base_class_name=", ".join(base_class_names) if base_class_names else "Model",
                model_type=py_type,
                fields=tuple(map(create_model_field_view, py_type.fields)),
                arbitrary_fields_allowed=py_type.arbitrary_fields_allowed,
            )
            if py_type.name
            else None
        ),
    )
