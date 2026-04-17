"""fm — FrontMatter Utilities."""

from fm.aggregation import Avg, Count, GroupedQuery, Max, Min, Sum
from fm.cypher import CypherResult, compile_cypher
from fm.dates import now, today
from fm.describe import FieldStat, WorkspaceStats, describe
from fm.edits import ApplyReport, EditOp, EditPlan
from fm.errors import CypherError, CypherUnsupported, EditError
from fm.packet import Packet
from fm.query import Query
from fm.resolvers import RelativePathResolver, SlugResolver, UuidResolver, resolver_by_name
from fm.search import TextScanIndex
from fm.workspace import Workspace

__version__ = "0.1.0"

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
    "Max",
    "Min",
    "Packet",
    "Query",
    "RelativePathResolver",
    "SlugResolver",
    "Sum",
    "TextScanIndex",
    "UuidResolver",
    "Workspace",
    "WorkspaceStats",
    "compile_cypher",
    "describe",
    "now",
    "resolver_by_name",
    "today",
    "__version__",
]
