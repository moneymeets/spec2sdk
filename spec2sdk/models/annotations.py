from itertools import groupby
from typing import Any, Sequence

from spec2sdk.base import Model
from spec2sdk.models.imports import Import


class TypeConstraintParameter(Model):
    name: str
    value: Any


class TypeConstraint(Model):
    name: str
    parameters: Sequence[TypeConstraintParameter]
    imports: Sequence[Import]


class TypeAnnotation(Model):
    type_hint: str
    type_imports: Sequence[Import]
    constraints: Sequence[TypeConstraint]

    @property
    def imports(self) -> Sequence[Import]:
        return (
            *(
                (
                    Import(name="Annotated", package="typing"),
                    *(import_ for constraint in self.constraints for import_ in constraint.imports),
                )
                if self.constraints
                else ()
            ),
            *self.type_imports,
        )

    def render(self) -> str:
        constraints = ", ".join(
            (
                f"{annotation_name}("
                + ", ".join(
                    f"{parameter.name}={parameter.value}"
                    for annotation in annotation_group
                    for parameter in annotation.parameters
                )
                + ")"
            )
            for annotation_name, annotation_group in groupby(self.constraints, lambda a: a.name)
        )

        return f"Annotated[{self.type_hint}, {constraints}]" if constraints else self.type_hint
