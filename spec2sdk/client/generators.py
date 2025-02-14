from pathlib import Path
from typing import Sequence

from spec2sdk.client.views import EndpointView
from spec2sdk.models.converters import converters
from spec2sdk.models.entities import PythonType
from spec2sdk.models.imports import Import, render_imports
from spec2sdk.openapi.entities import Specification
from spec2sdk.openapi.parsers import get_root_data_types
from spec2sdk.templating import create_jinja_environment


def get_imports(py_types: Sequence[PythonType], models_import: Import) -> Sequence[Import]:
    """
    Returns imports for each type in the following cases:
    - if type has a name, it can be imported directly from the models file
      (e.g. `from models import User`)
    - if type doesn't have a name, import types used in the type definition
      (e.g. `from typing import Literal` for `Literal["json", "xml"]`)
    - if type doesn't have a name, import types for inner types
      (e.g. `from models import Product` for `list[Product]`)
    """

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
        }
        | {import_ for py_type in py_types if not py_type.name for import_ in py_type.imports},
    )


def generate_client(spec: Specification, models_import: Import, output_dir: Path):
    root_data_types = get_root_data_types(spec)
    root_python_types = tuple(map(converters.convert, root_data_types))
    imports = get_imports(py_types=root_python_types, models_import=models_import)
    jinja_environment = create_jinja_environment(templates_path=Path(__file__).parent / "templates")

    api_content = jinja_environment.get_template("api.j2").render(
        imports=render_imports(imports),
        endpoints=tuple(
            EndpointView(endpoint=endpoint, response=response)
            for endpoint in spec.endpoints
            for response in endpoint.responses
        ),
    )
    output_dir.joinpath("api.py").write_text(api_content)

    for filename in ("http_client", "api_client"):
        output_dir.joinpath(f"{filename}.py").write_text(
            jinja_environment.get_template(f"{filename}.j2").render(),
        )
