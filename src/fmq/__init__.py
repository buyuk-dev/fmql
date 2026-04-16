"""fmq — FrontMatter Utilities."""

from fmq.dates import now, today
from fmq.edits import ApplyReport, EditOp, EditPlan
from fmq.errors import EditError
from fmq.packet import Packet
from fmq.query import Query
from fmq.workspace import Workspace

__version__ = "0.1.0"

__all__ = [
    "ApplyReport",
    "EditError",
    "EditOp",
    "EditPlan",
    "Packet",
    "Query",
    "Workspace",
    "now",
    "today",
    "__version__",
]
