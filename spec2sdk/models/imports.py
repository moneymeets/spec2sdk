from pathlib import Path
from typing import Sequence

from spec2sdk.base import Model
from spec2sdk.templating import create_jinja_environment


class Import(Model):
    name: str
    package: str

    def __hash__(self):
        return hash((self.name, self.package))


def render_imports(imports: Sequence[Import]) -> str:
    return (
        create_jinja_environment(templates_path=Path(__file__).parent / "templates")
        .get_template("imports.j2")
        .render(imports=imports)
    )
