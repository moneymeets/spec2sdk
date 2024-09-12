class ParserError(Exception):
    pass


class CircularReference(ParserError):
    pass
