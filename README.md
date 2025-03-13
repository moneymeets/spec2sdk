# Usage

## From command line

- Local specification `spec2sdk --schema-path path/to/api.yml --output-dir path/to/output-dir/`
- Remote specification `spec2sdk --schema-url https://example.com/path/to/api.yml --output-dir path/to/output-dir/`

## From the code

```python
from pathlib import Path
from spec2sdk.main import generate

# Local specification
generate(schema_url=Path("path/to/api.yml").absolute().as_uri(), output_dir=Path("path/to/output-dir/"))

# Remote specification
generate(schema_url="https://example.com/path/to/api.yml", output_dir=Path("path/to/output-dir/"))
```

# Open API specification requirements

## Operation ID

`operationId` must be specified for each endpoint to generate meaningful method names. It must be unique among all operations described in the API.

### Input

```yaml
paths:
  /health:
    get:
      operationId: healthCheck
      responses:
        '200':
          description: Successful response
```

### Output

```python
class APIClient:
    def health_check(self) -> None:
        ...
```

## Inline schemas

Inline schemas should be annotated with the schema name in the `x-schema-name` field that doesn't overlap with the existing schema names in the specification.

### Input

```yaml
paths:
  /me:
    get:
      operationId: getMe
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                x-schema-name: User
                type: object
                properties:
                  name:
                    type: string
                  email:
                    type: string
```

### Output

```python
class User(Model):
    name: str | None = Field(default=None)
    email: str | None = Field(default=None)
```

## Enum variable names

Variable names for enums can be specified by the `x-enum-varnames` field.

### Input

```yaml
components:
  schemas:
    Direction:
      x-enum-varnames: [ NORTH, SOUTH, WEST, EAST ]
      type: string
      enum: [ N, S, W, E ]
```

### Output

```python
from enum import StrEnum

class Direction(StrEnum):
    NORTH = "N"
    SOUTH = "S"
    WEST = "W"
    EAST = "E"
```

# Custom types

Register Python converters and renderers to implement custom types.

## Input

```yaml
components:
  schemas:
    User:
      type: object
      properties:
        name:
          type: string
        email:
          type: string
          format: email
```

```python
from pathlib import Path
from typing import Sequence

from spec2sdk.openapi.entities import DataType, StringDataType
from spec2sdk.models.converters import converters, convert_common_fields
from spec2sdk.models.entities import PythonType
from spec2sdk.models.imports import Import
from spec2sdk.main import generate


class EmailType(PythonType):
    @property
    def type_hint(self) -> str:
        return self.name or "EmailStr"

    @property
    def imports(self) -> Sequence[Import]:
        return (
            Import(name="EmailStr", package="pydantic"),
        )

    def render(self) -> str:
        return f"type {self.name} = EmailStr" if self.name else ""


def is_email_format(data_type: DataType) -> bool:
    return isinstance(data_type, StringDataType) and data_type.format == "email"


@converters.register(predicate=is_email_format)
def convert_email_field(data_type: StringDataType) -> EmailType:
    return EmailType(**convert_common_fields(data_type))


if __name__ == "__main__":
    generate(schema_url=Path("api.yml").absolute().as_uri(), output_dir=Path("output"))
```

## Output

```python
from pydantic import EmailStr, Field

class User(Model):
    name: str | None = Field(default=None)
    email: EmailStr | None = Field(default=None)
```

# Using generated client

1. Create HTTP client. It should conform to the `HTTPClientProtocol` which can be found in the generated `http_client.py`. Below is an example of the HTTP client implemented using `httpx` library to handle HTTP requests. Assume that `sdk` is the output directory for the generated code.
```python
from http import HTTPStatus

import httpx
from httpx._types import AuthTypes, TimeoutTypes

from sdk.http_client import HTTPRequest, HTTPResponse


class HTTPClient:
    def __init__(self, *, base_url: str, auth: AuthTypes | None = None, timeout: TimeoutTypes | None = None, **kwargs):
        self._http_client = httpx.Client(auth=auth, base_url=base_url, timeout=timeout, **kwargs)

    def send_request(self, *, request: HTTPRequest) -> HTTPResponse:
        response = self._http_client.request(
            method=request.method,
            url=request.url,
            content=request.content,
            headers=request.headers,
        )
        return HTTPResponse(
            status_code=HTTPStatus(response.status_code),
            content=response.content,
            headers=response.headers.multi_items(),
        )
```
2. Create API client. It should conform to the `APIClientProtocol` which can be found in the generated `api_client.py`. Below is an example of the API client.
```python
from http import HTTPMethod, HTTPStatus
from types import NoneType
from typing import Any, Mapping, Type
from urllib.parse import urlencode

from pydantic import TypeAdapter

from sdk.api_client import APIClientResponse
from sdk.http_client import HTTPClientProtocol, HTTPRequest


class APIClient:
    def __init__(self, http_client: HTTPClientProtocol):
        self._http_client = http_client

    def serialize[T](self, *, data: T, data_type: Type[T], content_type: str | None) -> bytes:
        match content_type:
            case "application/json":
                return TypeAdapter(data_type).dump_json(data, by_alias=True)
            case _:
                return data

    def deserialize[T](self, *, data: bytes | None, data_type: Type[T], content_type: str | None) -> T:
        match content_type:
            case "application/json":
                return TypeAdapter(data_type).validate_json(data)
            case _:
                return data

    def build_url(self, path: str, query: Mapping[str, Any] | None = None) -> str:
        if query is None:
            return path

        return f"{path}?{urlencode(query, doseq=True)}"

    def send_request[I, O](
        self,
        *,
        method: HTTPMethod,
        path: str,
        query: Mapping[str, Any] | None = None,
        content_type: str | None = None,
        data: I | None = None,
        data_type: Type[I] = NoneType,
        accept: str | None = None,
        response_type: Type[O] = NoneType,
        expected_status_code: HTTPStatus = HTTPStatus.OK,
    ) -> APIClientResponse[O]:
        content = self.serialize(data=data, data_type=data_type, content_type=content_type) if data else None
        request = HTTPRequest(
            method=method,
            url=self.build_url(path, query),
            headers=(("Content-Type", content_type),) if content_type else (),
            content=content,
        )
        response = self._http_client.send_request(request=request)

        if response.status_code != expected_status_code:
            raise Exception(
                f"Response has unexpected status code. Expected {expected_status_code}, got {response.status_code}."
            )

        if accept is not None and not any(
            response_content_type := tuple(
                value for key, value in response.headers if (key.lower() == "content-type") and (accept in value)
            ),
        ):
            raise Exception(f"Response has unexpected content type. Expected {accept}, got {response_content_type}.")

        return APIClientResponse(
            http_response=response,
            data=self.deserialize(data=response.content, data_type=response_type, content_type=accept),
        )
```
3. Combine clients together to access API.
```python
from sdk.api import API

api = API(
    api_client=APIClient(
        http_client=HTTPClient(
            base_url="https://api.example.com",
            auth=BasicAuth(username="user", password="pass"),
        ),
    ),
)
```
