import re
from keyword import iskeyword

from humps import decamelize, pascalize


def make_identifier(name: str) -> str:
    """
    Makes valid Python identifier from the string.
    """
    # Remove invalid characters
    name = re.sub(r"[^0-9a-zA-Z_]", "_", name)

    # Remove leading characters until we find a letter
    name = re.sub(r"^[^a-zA-Z]+", "", name)

    # Replace consecutive duplicates of the underscore
    name = re.sub(r"_+", "_", name)

    # Add underscore to the name if it's a valid Python keyword
    if iskeyword(name):
        name += "_"

    return name


def make_class_name(name: str) -> str:
    return pascalize(make_identifier(name))


def make_constant_name(name: str) -> str:
    return make_identifier(name).upper()


def make_variable_name(name: str) -> str:
    return decamelize(make_identifier((name)))
