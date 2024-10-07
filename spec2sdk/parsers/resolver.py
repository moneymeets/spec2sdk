from functools import reduce
from typing import Any, ClassVar, Sequence
from urllib.parse import urldefrag, urljoin
from urllib.request import urlopen

import yaml
from pydantic import BaseModel, ConfigDict

from spec2sdk.parsers.exceptions import CircularReference

SCHEMA_NAME_FIELD = "x-schema-name"


class SchemaLoader(BaseModel):
    model_config = ConfigDict(frozen=True)
    _schema_cache: ClassVar[dict] = {}
    schema_url: str

    def _read_schema(self) -> dict:
        if self.schema_url not in self._schema_cache:
            self._schema_cache[self.schema_url] = yaml.safe_load(stream=urlopen(self.schema_url))

        return self._schema_cache[self.schema_url]

    def get_schema_fragment(self, path: str) -> dict:
        return reduce(
            lambda acc, key: acc[key],
            filter(None, path.split("/")),
            self._read_schema(),
        )

    def parse(self, reference: str) -> "SchemaLoader":
        reference_url, _ = urldefrag(reference)
        new_schema_url = urljoin(self.schema_url, reference_url)

        return self if new_schema_url == self.schema_url else SchemaLoader(schema_url=new_schema_url)


class ResolvingParser:
    def __init__(self):
        self._resolved_references = {}

    def _resolve_schema(self, schema_loader: SchemaLoader, schema: dict, parent_reference_ids: Sequence[str]) -> dict:
        def resolve_value(value: Any) -> Any:
            if isinstance(value, dict):
                return self._resolve_schema(schema_loader, value, parent_reference_ids)
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            else:
                return value

        def resolve_reference(reference: str) -> dict:
            reference_schema_loader = schema_loader.parse(reference)
            _, reference_fragment_path = urldefrag(reference)
            reference_id = f"{reference_schema_loader.schema_url}#{reference_fragment_path}"

            if reference_id in parent_reference_ids:
                raise CircularReference(f"Circular reference found in {reference}")

            if reference_id not in self._resolved_references:
                self._resolved_references[reference_id] = {
                    SCHEMA_NAME_FIELD: reference_fragment_path.rsplit("/", 1)[-1],
                } | self._resolve_schema(
                    schema_loader=reference_schema_loader,
                    schema=reference_schema_loader.get_schema_fragment(path=reference_fragment_path),
                    parent_reference_ids=(*parent_reference_ids, reference_id),
                )

            return self._resolved_references[reference_id]

        return {
            new_key: new_value
            for key, value in schema.items()
            for new_key, new_value in (
                resolve_reference(value) if key == "$ref" else {key: resolve_value(value)}
            ).items()
        }

    def parse(self, url: str) -> dict:
        schema_loader = SchemaLoader(schema_url=url)

        return self._resolve_schema(
            schema_loader=schema_loader,
            schema=schema_loader.get_schema_fragment(path="/"),
            parent_reference_ids=(),
        )
