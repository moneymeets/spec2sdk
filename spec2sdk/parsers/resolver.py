from functools import reduce
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

import yaml

from spec2sdk.parsers.exceptions import CircularReference

SCHEMA_NAME_FIELD = "x-schema-name"


class ResolvingParser:
    def __init__(self, base_path: Path):
        self._base_path = base_path
        self._file_cache = {}
        self._resolved_references = {}

    def _read_schema_from_file(self, relative_filepath: Path) -> dict:
        absolute_filepath = (self._base_path / relative_filepath).resolve()
        if absolute_filepath not in self._file_cache:
            self._file_cache[absolute_filepath] = yaml.safe_load(absolute_filepath.read_text())
        return self._file_cache[absolute_filepath]

    def _resolve_schema(self, relative_filepath: Path, schema: dict, parent_references: Sequence[str]) -> dict:
        def resolve_value(value: Any) -> Any:
            if isinstance(value, dict):
                return self._resolve_schema(relative_filepath, value, parent_references)
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            else:
                return value

        def resolve_reference(reference: str) -> dict:
            if reference in parent_references:
                raise CircularReference(f"Circular reference found in {reference}")

            if reference not in self._resolved_references:
                parsed_ref = urlparse(reference)

                if parsed_ref.scheme == parsed_ref.netloc == "":
                    ref_relative_filepath = (
                        relative_filepath.parent / Path(parsed_ref.path) if parsed_ref.path else relative_filepath
                    )
                    ref_schema_fragment = reduce(
                        lambda acc, key: acc[key],
                        filter(None, parsed_ref.fragment.split("/")),
                        self._read_schema_from_file(ref_relative_filepath),
                    )
                    ref_schema_name = parsed_ref.fragment.rsplit("/", 1)[-1]

                    self._resolved_references[reference] = {
                        SCHEMA_NAME_FIELD: ref_schema_name,
                    } | self._resolve_schema(
                        relative_filepath=ref_relative_filepath,
                        schema=ref_schema_fragment,
                        parent_references=(*parent_references, reference),
                    )
                else:
                    raise NotImplementedError(f"Unsupported schema reference: {reference}")

            return self._resolved_references[reference]

        return {
            new_key: new_value
            for key, value in schema.items()
            for new_key, new_value in (
                resolve_reference(value) if key == "$ref" else {key: resolve_value(value)}
            ).items()
        }

    def parse(self, relative_filepath: Path) -> dict:
        return self._resolve_schema(
            relative_filepath=relative_filepath,
            schema=self._read_schema_from_file(relative_filepath),
            parent_references=(),
        )
