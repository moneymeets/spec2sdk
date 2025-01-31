# Usage

## From command line

`spec2sdk --input path/to/api.yml --output-dir path/to/output-dir/`

## From the code

```python
from pathlib import Path
from spec2sdk.main import generate

generate(url=Path("path/to/api.yml").absolute().as_uri(), output_dir=Path("path/to/output-dir/"))
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
from spec2sdk.models.converters import converters, get_common_fields
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
    return EmailType(**get_common_fields(data_type))


if __name__ == "__main__":
    generate(url=Path("api.yml").absolute().as_uri(), output_dir=Path("output"))
```

## Output

```python
from pydantic import EmailStr, Field

class User(Model):
    name: str | None = Field(default=None)
    email: EmailStr | None = Field(default=None)
```

# Writing HTTP client

HTTP client should conform to the `HTTPClientProtocol` which can be found in the generated `api_client.py`. Below is an example of the HTTP client implemented using `httpx` to handle HTTP requests.
```python
from http import HTTPMethod, HTTPStatus
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx
from httpx._types import AuthTypes, TimeoutTypes


class HTTPClient:
    def __init__(self, *, base_url: str, auth: AuthTypes | None = None, timeout: TimeoutTypes | None = None, **kwargs):
        self._http_client = httpx.Client(auth=auth, base_url=base_url, timeout=timeout, **kwargs)

    def build_url(self, path: str, query: Mapping[str, Any] | None = None) -> str:
        if query is None:
            return path

        return f"{path}?{urlencode(query, doseq=True)}"

    def send_request(
        self,
        method: HTTPMethod,
        url: str,
        accept: str | None = None,
        content_type: str | None = None,
        content: bytes | None = None,
        expected_status_code: HTTPStatus = HTTPStatus.OK,
    ) -> bytes | None:
        response = self._http_client.request(
            method=method,
            url=url,
            content=content,
            headers=content_type and {"Content-Type": content_type},
        )

        if response.status_code != expected_status_code:
            raise Exception(
                f"Unexpected status code for {method} {url}: {response.status_code}.",
            )

        if (accept is not None) and (accept not in (response_content_type := response.headers.get("Content-Type", ""))):
            raise Exception(f"Expected {accept}, got {response_content_type}.")

        return response.content
```
