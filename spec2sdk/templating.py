from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def create_jinja_environment(templates_path: Path) -> Environment:
    return Environment(loader=FileSystemLoader(templates_path))
