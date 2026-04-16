class FmqError(Exception):
    pass


class ParseError(FmqError):
    pass


class QueryError(FmqError):
    pass


class FilterError(QueryError):
    pass


class EditError(FmqError):
    pass


class CypherError(QueryError):
    pass


class CypherUnsupported(CypherError):
    pass
