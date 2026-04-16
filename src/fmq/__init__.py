"""fmq — FrontMatter Utilities."""

from fmq.aggregation import Avg, Count, GroupedQuery, Max, Min, Sum
from fmq.cypher import CypherResult, compile_cypher
from fmq.dates import now, today
from fmq.describe import FieldStat, WorkspaceStats, describe
from fmq.edits import ApplyReport, EditOp, EditPlan
from fmq.errors import CypherError, CypherUnsupported, EditError
from fmq.packet import Packet
from fmq.query import Query
from fmq.resolvers import RelativePathResolver, SlugResolver, UuidResolver, resolver_by_name
from fmq.search import TextScanIndex
from fmq.workspace import Workspace

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
