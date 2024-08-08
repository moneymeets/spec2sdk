from pathlib import Path
from typing import Sequence

from jinja2 import Environment, FileSystemLoader

from spec2sdk.generators.converters import converters
from spec2sdk.generators.entities import PythonType
from spec2sdk.parsers.entities import Specification

from ..imports import Import, render_imports
from ..utils import get_root_data_types
from .views import EndpointView


def get_imports(py_types: Sequence[PythonType], models_import: Import) -> Sequence[Import]:
    def get_importable_type_names(py_type: PythonType) -> Sequence[str]:
        return (
            (py_type.name,)
            if py_type.name
            else tuple(
                type_name
                for dependency_type in py_type.dependency_types
                for type_name in get_importable_type_names(dependency_type)
            )
        )

    return tuple(
        {
            models_import.model_copy(update={"name": name})
            for py_type in py_types
            for name in get_importable_type_names(py_type)
        },
    )


def generate_client(spec: Specification, models_import: Import) -> str:
    root_data_types = get_root_data_types(spec)
    root_python_types = tuple(map(converters.convert, root_data_types))
    imports = get_imports(py_types=root_python_types, models_import=models_import)

    return (
        Environment(loader=FileSystemLoader(f"{Path(__file__).parent}/templates"))
        .get_template("client.j2")
        .render(
            imports=render_imports(imports),
            endpoints=tuple(
                EndpointView(endpoint=endpoint, response=response)
                for endpoint in spec.endpoints
                for response in endpoint.responses
            ),
        )
    )
