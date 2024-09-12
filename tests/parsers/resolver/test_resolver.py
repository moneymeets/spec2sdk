import json
from pathlib import Path

import pytest

from spec2sdk.parsers.exceptions import CircularReference
from spec2sdk.parsers.resolver import ResolvingParser

TEST_DATA_DIR = Path(__file__).parent / "test_data"


@pytest.mark.parametrize("test_data_name", ("local_references", "remote_references"))
def test_resolve_references(test_data_name: str):
    data_dir = TEST_DATA_DIR / test_data_name
    input_spec = data_dir / "input" / "api.yml"
    expected_schema = json.loads((data_dir / "expected_output" / "schema.json").read_text())

    assert (
        ResolvingParser(base_path=input_spec.parent).parse(
            relative_filepath=input_spec.relative_to(input_spec.parent),
        )
        == expected_schema
    )


def test_circular_reference():
    with pytest.raises(CircularReference):
        ResolvingParser(base_path=TEST_DATA_DIR / "circular_reference").parse(relative_filepath=Path("api.yml"))
