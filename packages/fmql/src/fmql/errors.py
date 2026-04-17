class FmqlError(Exception):
    pass


class ParseError(FmqlError):
    pass


class QueryError(FmqlError):
    pass


class FilterError(QueryError):
    pass


class EditError(FmqlError):
    pass


class CypherError(QueryError):
    pass


class CypherUnsupported(CypherError):
    pass
