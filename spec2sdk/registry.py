from typing import Any, Callable, TypeVar

from pydantic import BaseModel

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")

PredicateType = Callable[[InputType], bool]
ConverterType = Callable[[InputType], OutputType]


class AlreadyRegistered(Exception):
    pass


class ConverterNotFound(Exception):
    pass


class ConditionalConverter(BaseModel):
    predicate: PredicateType
    convert: ConverterType


class Registry:
    def __init__(self):
        self.converters: list[ConditionalConverter] = []

    def register(self, predicate: PredicateType):
        def inner(func: ConverterType):
            if func in {converter.convert for converter in self.converters}:
                raise AlreadyRegistered(f"The function '{func.__name__}' is already registered")

            self.converters.append(ConditionalConverter(predicate=predicate, convert=func))

            return func

        return inner

    def convert(self, data) -> Any:
        for converter in reversed(self.converters):
            if converter.predicate(data):
                return converter.convert(data)

        raise ConverterNotFound(f"Converter not found for '{data}'")
