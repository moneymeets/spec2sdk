import pytest

from spec2sdk.registry import AlreadyRegistered, ConverterNotFound, Registry


def identity_converter(value: str) -> str:
    return value


def revert_converter(value: str) -> str:
    return value[::-1]


def test_duplicate_registration():
    registry = Registry()
    registry.register(predicate=lambda _: True)(identity_converter)

    with pytest.raises(AlreadyRegistered):
        registry.register(predicate=lambda _: True)(identity_converter)


def test_converter_not_found():
    registry = Registry()

    with pytest.raises(ConverterNotFound):
        registry.convert(None)
