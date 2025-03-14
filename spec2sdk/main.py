import argparse
import shutil
import subprocess
from pathlib import Path

from openapi_spec_validator import validate

from spec2sdk.client.generators import generate_client
from spec2sdk.models.generators import generate_models
from spec2sdk.models.imports import Import
from spec2sdk.openapi.parsers import parse_spec
from spec2sdk.openapi.resolver import ResolvingParser


def format_files(path: Path):
    def run_formatter(formatter: str):
        print(f"Running {formatter} on {path}")
        subprocess.run(f"{formatter} {path}", shell=True, check=True)

    # Formatting and linting explanation:
    # 1. Format the code [line will be a 120 character]
    # 2. Add trailing comma [line will be a 121 character]
    # 3. Format the code [line will be a 120 character]
    # 4. Apply linting auto fixes, and then check if the generated code follow the linting rules
    run_formatter("ruff format")
    run_formatter("ruff check --select COM812 --fix")
    run_formatter("ruff format")
    run_formatter("ruff check --fix")


def generate(schema_url: str, output_dir: Path):
    schema = ResolvingParser().parse(schema_url=schema_url)
    validate(schema)
    spec = parse_spec(schema)

    if output_dir.exists():
        shutil.rmtree(str(output_dir))

    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("__init__.py").write_text("")

    models_path = generate_models(spec=spec, output_dir=output_dir)
    generate_client(spec=spec, models_import=Import(name="", package=f".{models_path.stem}"), output_dir=output_dir)

    format_files(output_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Path to the output directory where the generated code will be written to",
        required=True,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--schema-path",
        type=Path,
        help="File path to the OpenAPI specification file in YAML format",
    )
    group.add_argument(
        "--schema-url",
        type=str,
        help="URL of the OpenAPI specification file in YAML format",
    )

    args = parser.parse_args()
    generate(
        schema_url=args.schema_path.absolute().as_uri() if args.schema_path else args.schema_url,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
