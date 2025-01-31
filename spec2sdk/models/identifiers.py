import re
from keyword import iskeyword
from typing import Final, Pattern

from humps import decamelize, pascalize

INVALID_CHARACTERS_PATTERN: Final[Pattern] = re.compile(r"[^0-9a-z]+|^[^a-z]+", flags=re.IGNORECASE)


def make_identifier(name: str) -> str:
    """
    Makes valid Python identifier from the string by removing invalid leading characters
    and replacing invalid characters with underscore.
    """

    name = "_".join(name_part for name_part in INVALID_CHARACTERS_PATTERN.split(name) if name_part)

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
