from pathlib import Path
from typing import Sequence

from jinja2 import Environment, FileSystemLoader

from spec2sdk.base import Model


class Import(Model):
    name: str
    package: str


def render_imports(imports: Sequence[Import]) -> str:
    jinja_environment = Environment(loader=FileSystemLoader(f"{Path(__file__).parent}/templates"))
    return jinja_environment.get_template("imports.j2").render(imports=imports)
