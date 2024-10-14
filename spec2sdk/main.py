import argparse
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from openapi_spec_validator import validate

from spec2sdk.generators.client.generators import generate_client
from spec2sdk.generators.imports import Import
from spec2sdk.generators.models.generators import generate_models
from spec2sdk.parsers.parsers import parse_spec
from spec2sdk.parsers.resolver import ResolvingParser


def format_file(path: Path):
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


def generate(url: str, output_dir: Path):
    schema = ResolvingParser().parse(url=url)
    validate(schema)
    spec = parse_spec(schema)

    if output_dir.exists():
        shutil.rmtree(str(output_dir))

    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("__init__.py").write_text("")

    models_path = output_dir.joinpath("models.py")
    models_path.write_text(generate_models(spec=spec))
    format_file(models_path)

    client_path = output_dir.joinpath("api_client.py")
    client_path.write_text(generate_client(spec=spec, models_import=Import(name="", package=f".{models_path.stem}")))
    format_file(client_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        help="File path or URL to the OpenAPI specification file in the YAML format",
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Path to the output directory where the generated code will be written to",
        required=True,
    )

    args = parser.parse_args()
    generate(
        url=Path(args.input).absolute().as_uri() if urlparse(args.input).scheme == "" else args.input,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
