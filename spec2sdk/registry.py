from typing import Callable, TypeVar

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
    priority: int


class Registry:
    def __init__(self):
        self.converters: list[ConditionalConverter] = []

    def register(self, predicate: PredicateType, priority: int = 0):
        def inner(func: ConverterType):
            if func in {converter.convert for converter in self.converters}:
                raise AlreadyRegistered(f"The function '{func.__name__}' is already registered")

            self.converters.append(ConditionalConverter(predicate=predicate, convert=func, priority=priority))
            self.converters.sort(key=lambda converter: converter.priority)

            return func

        return inner

    def convert(self, data: InputType) -> OutputType:
        for converter in reversed(self.converters):
            if converter.predicate(data):
                return converter.convert(data)

        raise ConverterNotFound(f"Converter not found for '{data}'")
