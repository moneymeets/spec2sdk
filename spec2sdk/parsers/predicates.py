from typing import Callable


def contains(key: str) -> Callable[[dict], bool]:
    def compare(schema: dict) -> bool:
        return key in schema

    return compare


def type_equals(type_name: str) -> Callable[[dict], bool]:
    def compare(schema: dict) -> bool:
        return schema.get("type") == type_name

    return compare
