class FmError(Exception):
    pass


class ParseError(FmError):
    pass


class QueryError(FmError):
    pass


class FilterError(QueryError):
    pass


class EditError(FmError):
    pass


class CypherError(QueryError):
    pass


class CypherUnsupported(CypherError):
    pass
