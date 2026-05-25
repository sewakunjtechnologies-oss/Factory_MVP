"""Action modules: each import must run for its `@tool` decorators to fire."""

from . import po_actions  # noqa: F401  -- read sample-data tools + update_po_notes write
from . import contractor_actions  # noqa: F401  -- DB-backed read
from . import dispatch_actions  # noqa: F401  -- DB-backed read
from . import fabric_actions  # noqa: F401  -- DB-backed read
from . import mill_actions  # noqa: F401  -- DB-backed write (mill order)
from . import stage_actions  # noqa: F401  -- DB-backed write (stage progress)
from . import report_actions  # noqa: F401  -- DB-backed write (PDF generation)
from . import po_feasibility_actions  # noqa: F401  -- DB-backed read (fabric vs requirement)
