from graphlib import TopologicalSorter
from pathlib import Path
from typing import Sequence

from jinja2 import Environment, FileSystemLoader

from spec2sdk.generators.converters import converters
from spec2sdk.generators.entities import PythonType
from spec2sdk.parsers.entities import Specification

from ..imports import render_imports
from ..utils import get_root_data_types
from .entities import TypeRenderer
from .renderers import renderers


def create_jinja_environment() -> Environment:
    return Environment(loader=FileSystemLoader(f"{Path(__file__).parent}/templates"))


def unwrap_py_types(py_types: Sequence[PythonType]) -> Sequence[PythonType]:
    """
    Recursively unwraps all python types and returns all unique python types.
    """
    return tuple(
        {
            dependent_type
            for py_type in py_types
            for dependent_type in (py_type, *unwrap_py_types(py_type.dependency_types))
        },
    )


def generate_models(spec: Specification) -> str:
    root_data_types = get_root_data_types(spec)
    root_py_types = tuple(map(converters.convert, root_data_types))
    all_py_types = unwrap_py_types(root_py_types)

    # Types must be sorted in the order of defining their dependencies
    topological_sorter = TopologicalSorter({py_type: py_type.dependency_types for py_type in all_py_types})
    topological_sorter.prepare()
    type_renderers: Sequence[TypeRenderer] = ()

    while topological_sorter.is_active():
        node_group = topological_sorter.get_ready()
        type_renderers += tuple(map(renderers.convert, sorted(node_group, key=lambda py_type: py_type.name or "")))
        topological_sorter.done(*node_group)

    # Render imports
    content = render_imports(
        tuple({import_ for type_renderer in type_renderers for import_ in type_renderer.imports}),
    )

    # Render base model class
    content += create_jinja_environment().get_template("base_model.j2").render() + "\n"

    # Render types with a name
    content += "\n".join(type_renderer.content for type_renderer in type_renderers if type_renderer.content is not None)

    return content
