import textwrap
from functools import reduce
from http import HTTPStatus
from typing import Sequence

from spec2sdk.base import Model
from spec2sdk.generators.converters import converters
from spec2sdk.generators.identifiers import make_variable_name
from spec2sdk.parsers.entities import Endpoint, Parameter, ParameterLocation, Path, RequestBody, Response


def wordwrap(s: str, width: int) -> str:
    return "\n".join(
        textwrap.wrap(
            s,
            width=width,
            expand_tabs=False,
            replace_whitespace=False,
            break_long_words=True,
            break_on_hyphens=True,
        ),
    )


def indent(s: str, width: int) -> str:
    return textwrap.indent(s, " " * width).strip()


class ParameterView:
    def __init__(self, parameter: Parameter):
        self.__parameter = parameter

    @property
    def name(self) -> str:
        return make_variable_name(self.__parameter.name)

    @property
    def original_name(self) -> str:
        return self.__parameter.name

    @property
    def description(self) -> str:
        return self.__parameter.description or ""

    @property
    def type_hint(self) -> str:
        return converters.convert(self.__parameter.data_type).type_hint

    @property
    def required(self) -> bool:
        return self.__parameter.required

    @property
    def default_value(self) -> str:
        return repr(self.__parameter.default_value)


class PathView:
    def __init__(self, path: Path):
        self.__path = path

    @property
    def parameters(self) -> Sequence[ParameterView]:
        return tuple(ParameterView(parameter) for parameter in self.__path.parameters)

    @property
    def path_parameters(self) -> Sequence[ParameterView]:
        return tuple(
            ParameterView(parameter)
            for parameter in self.__path.parameters
            if parameter.location == ParameterLocation.PATH
        )

    @property
    def query_parameters(self) -> Sequence[ParameterView]:
        return tuple(
            ParameterView(parameter)
            for parameter in self.__path.parameters
            if parameter.location == ParameterLocation.QUERY
        )

    @property
    def url(self) -> str:
        return reduce(
            lambda url, parameter: url.replace(f"{{{parameter.original_name}}}", f"{{{parameter.name}}}"),
            self.parameters,
            self.__path.path,
        )


class ResponseView:
    def __init__(self, response: Response):
        self.__response = response

    @property
    def type_hint(self) -> str:
        return (
            converters.convert(self.__response.content.data_type).type_hint if self.__response.content else repr(None)
        )

    @property
    def has_content(self):
        return self.__response.content is not None

    @property
    def media_type(self) -> str | None:
        return self.__response.content.media_type if self.has_content else None

    @property
    def status_code(self) -> HTTPStatus:
        return HTTPStatus(int(self.__response.status_code))


class RequestBodyView:
    def __init__(self, request_body: RequestBody):
        self.__request_body = request_body

    @property
    def name(self) -> str:
        return make_variable_name(converters.convert(self.__request_body.content.data_type).name)

    @property
    def description(self) -> str:
        return self.__request_body.description

    @property
    def type_hint(self) -> str:
        return converters.convert(self.__request_body.content.data_type).type_hint

    @property
    def content_type(self) -> str:
        return self.__request_body.content.media_type


class MethodParameter(Model):
    name: str
    description: str | None
    type_hint: str
    required: bool
    default_value: str | None


class EndpointView:
    def __init__(self, endpoint: Endpoint, response: Response):
        self.__endpoint = endpoint
        self.__response = response

    @property
    def method_name(self) -> str:
        name = make_variable_name(self.__endpoint.operation_id)

        if self.response.status_code != HTTPStatus.OK:
            name += f"_expect_{self.__response.status_code}"

        return name

    @property
    def method_parameters(self) -> Sequence[MethodParameter]:
        parameters = []

        if request_body := self.request_body:
            parameters.append(
                MethodParameter(
                    name=request_body.name,
                    description=request_body.description,
                    type_hint=request_body.type_hint,
                    required=True,
                    default_value=None,
                ),
            )

        parameters += [
            MethodParameter(
                name=parameter.name,
                description=parameter.description,
                type_hint=parameter.type_hint,
                required=parameter.required,
                default_value=parameter.default_value,
            )
            for parameter in self.path.parameters
        ]

        return tuple(parameters)

    @property
    def http_method(self) -> str:
        return self.__endpoint.method

    @property
    def path(self) -> PathView:
        return PathView(self.__endpoint.path)

    @property
    def summary(self) -> str:
        return self.__endpoint.summary

    @property
    def docstring(self) -> str:
        result = []

        if self.summary:
            result.append(wordwrap(self.summary, width=99))

        if self.method_parameters:
            result.append(
                "\n".join(
                    indent(wordwrap(f":param {parameter.name}: {parameter.description or ''}", width=99), width=7)
                    for parameter in self.method_parameters
                ),
            )

        return "\n\n".join(result)

    @property
    def request_body(self) -> RequestBodyView | None:
        return RequestBodyView(self.__endpoint.request_body) if self.__endpoint.request_body else None

    @property
    def response(self) -> ResponseView:
        return ResponseView(response=self.__response)
