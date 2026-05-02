"""fmql — FrontMatter Utilities."""

from importlib.metadata import version as _pkg_version

from fmql.aggregation import Avg, Count, GroupedQuery, Max, Min, Sum
from fmql.cypher import CypherResult, compile_cypher
from fmql.dates import now, today
from fmql.describe import FieldStat, WorkspaceStats, describe
from fmql.edits import ApplyReport, EditOp, EditPlan
from fmql.errors import CypherError, CypherUnsupported, EditError
from fmql.packet import Packet
from fmql.parser import parse, parse_file
from fmql.parser import serialize_packet as serialize
from fmql.query import Query
from fmql.resolvers import (
    IdResolver,
    RelativePathResolver,
    SlugResolver,
    UuidResolver,
    resolver_by_name,
)
from fmql.workspace import Workspace

__version__ = _pkg_version("fmql")

__all__ = [
    "ApplyReport",
    "Avg",
    "Count",
    "CypherError",
    "CypherResult",
    "CypherUnsupported",
    "EditError",
    "EditOp",
    "EditPlan",
    "FieldStat",
    "GroupedQuery",
    "IdResolver",
    "Max",
    "Min",
    "Packet",
    "Query",
    "RelativePathResolver",
    "SlugResolver",
    "Sum",
    "UuidResolver",
    "Workspace",
    "WorkspaceStats",
    "compile_cypher",
    "describe",
    "now",
    "parse",
    "parse_file",
    "resolver_by_name",
    "serialize",
    "today",
    "__version__",
]
