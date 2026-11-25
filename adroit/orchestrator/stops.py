"""How a command reports a stop: the message a researcher reads and the shared exit code.

A budget stop exits with :data:`adroit.core.receipts.BUDGET_STOPPED` (3), so a script never reads it
as success. An input or session problem exits 2 and shows ADROIT's own explanation (for example
"supply the originally approved session budget"). A provider failure shows only its class: a provider's
message can echo request details that do not belong on screen.
"""

from __future__ import annotations

from adroit.agents.budget import BudgetExceeded
from adroit.core.receipts import BUDGET_STOPPED

INPUT_STOPPED = 2
OWN_ERRORS = (ValueError, OSError, IndexError, KeyError)


def stop(error: Exception, what: str, retained: str) -> tuple[str, int]:
    """The message and exit code for a stopped command.

    Args:
        error: what stopped it.
        what: the command's name in the message, e.g. "Extraction".
        retained: what is kept, e.g. "Drafts and paid receipts remain stored."
    """
    if isinstance(error, BudgetExceeded):
        ledger = f"; paid responses: {error.ledger_path}" if error.ledger_path else ""
        return f"{error}{ledger}. {retained}", BUDGET_STOPPED
    if isinstance(error, OWN_ERRORS):
        return f"{what} stopped: {error}. {retained}", INPUT_STOPPED
    return f"{what} stopped: the provider call failed ({type(error).__name__}). {retained}", INPUT_STOPPED
