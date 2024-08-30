from typing import Sequence

from spec2sdk.base import Model
from spec2sdk.generators.imports import Import


class TypeRenderer(Model):
    imports: Sequence[Import]
    content: str | None
