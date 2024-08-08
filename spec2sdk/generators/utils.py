from typing import Sequence

from spec2sdk.parsers.entities import DataType, Specification


def get_root_data_types(spec: Specification) -> Sequence[DataType]:
    """
    Returns the only data types used directly in the parameters, request bodies and responses.
    Duplicates are removed from the result.
    """
    data_types = set()

    for endpoint in spec.endpoints:
        data_types.update(tuple(parameter.data_type for parameter in endpoint.path.parameters))

        if endpoint.request_body:
            data_types.add(endpoint.request_body.content.data_type)

        data_types.update(tuple(response.content.data_type for response in endpoint.responses if response.content))

    return tuple(data_types)
