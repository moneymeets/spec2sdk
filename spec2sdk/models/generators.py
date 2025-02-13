from collections import Counter
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Sequence

from spec2sdk.models.converters import converters
from spec2sdk.models.entities import PythonType
from spec2sdk.models.imports import render_imports
from spec2sdk.openapi.entities import Specification
from spec2sdk.openapi.parsers import get_root_data_types
from spec2sdk.templating import create_jinja_environment


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


def get_duplicate_type_names(py_types: Sequence[PythonType]) -> Sequence[str]:
    type_names = tuple(py_type.name for py_type in py_types if py_type.name is not None)
    duplicate_type_names = Counter(type_names) - Counter(set(type_names))
    return tuple(duplicate_type_names.keys())


def generate_models(spec: Specification, output_dir: Path) -> Path:
    root_data_types = get_root_data_types(spec)
    root_py_types = tuple(map(converters.convert, root_data_types))
    all_py_types = unwrap_py_types(root_py_types)

    if duplicate_type_names := get_duplicate_type_names(all_py_types):
        raise Exception(f"Found duplicate type names: {', '.join(duplicate_type_names)}")

    # Types must be sorted in the order of defining their dependencies
    topological_sorter = TopologicalSorter({py_type: py_type.dependency_types for py_type in all_py_types})
    topological_sorter.prepare()
    sorted_py_types: Sequence[PythonType] = ()

    while topological_sorter.is_active():
        node_group = topological_sorter.get_ready()
        sorted_py_types += tuple(sorted(node_group, key=lambda py_type: py_type.name or ""))
        topological_sorter.done(*node_group)

    # Render imports
    content = render_imports(
        tuple({import_ for py_type in sorted_py_types for import_ in py_type.imports}),
    )

    # Render base model class
    content += (
        create_jinja_environment(templates_path=Path(__file__).parent / "templates")
        .get_template("base_model.j2")
        .render()
        + "\n"
    )

    # Render types with a name
    content += "\n".join(py_type.render() for py_type in sorted_py_types if py_type.name is not None)

    models_path = output_dir.joinpath("models.py")
    models_path.write_text(content)

    return models_path
