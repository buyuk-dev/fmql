"""fmq — FrontMatter Utilities."""

from fmq.dates import now, today
from fmq.edits import ApplyReport, EditOp, EditPlan
from fmq.errors import EditError
from fmq.packet import Packet
from fmq.query import Query
from fmq.resolvers import RelativePathResolver, SlugResolver, UuidResolver, resolver_by_name
from fmq.workspace import Workspace

__version__ = "0.1.0"

__all__ = [
    "ApplyReport",
    "EditError",
    "EditOp",
    "EditPlan",
    "Packet",
    "Query",
    "RelativePathResolver",
    "SlugResolver",
    "UuidResolver",
    "Workspace",
    "now",
    "resolver_by_name",
    "today",
    "__version__",
]
