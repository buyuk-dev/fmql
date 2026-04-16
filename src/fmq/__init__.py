"""fmq — FrontMatter Utilities."""

from fmq.dates import now, today
from fmq.packet import Packet
from fmq.query import Query
from fmq.workspace import Workspace

__version__ = "0.1.0"

__all__ = [
    "Packet",
    "Query",
    "Workspace",
    "now",
    "today",
    "__version__",
]
