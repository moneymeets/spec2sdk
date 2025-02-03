import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import pytest

from spec2sdk.openapi import resolver
from spec2sdk.openapi.exceptions import CircularReference
from spec2sdk.openapi.resolver import ResolvingParser

TEST_DATA_DIR = Path(__file__).parent / "test_data"


@pytest.mark.parametrize("test_data_name", ("local_references", "remote_references", "references_with_siblings"))
def test_resolve_references(test_data_name: str):
    data_dir = TEST_DATA_DIR / test_data_name
    spec_path = data_dir / "input" / "api.yml"
    expected_schema = json.loads((data_dir / "expected_output" / "schema.json").read_text())

    assert ResolvingParser().parse(url=spec_path.absolute().as_uri()) == expected_schema


def test_url_references():
    def mock_response(url: str) -> str:
        parsed_url = urlparse(url)
        filepath = (
            Path(parsed_url.path)
            if parsed_url.scheme == "file"
            else (TEST_DATA_DIR / "url_references" / "input" / parsed_url.path.removeprefix("/"))
        )
        return filepath.read_text()

    with patch.object(resolver, "urlopen", side_effect=mock_response):
        test_resolve_references("url_references")


def test_circular_reference():
    with pytest.raises(CircularReference):
        ResolvingParser().parse(url=(TEST_DATA_DIR / "circular_reference" / "api.yml").absolute().as_uri())


def test_schema_cache():
    def mock_response(url: str) -> str:
        return Path(urlparse(url).path).read_text()

    with patch.object(resolver, "urlopen", side_effect=mock_response) as mock_urlopen:
        ResolvingParser().parse(url=(TEST_DATA_DIR / "schema_cache" / "api.yml").absolute().as_uri())
        assert mock_urlopen.call_count == 2
