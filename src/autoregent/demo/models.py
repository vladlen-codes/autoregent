from datetime import datetime

from pydantic import BaseModel


class AccountBalance(BaseModel):
    """Expected schema for the demo's informational route."""

    account_id: str
    balance: float
    currency: str
    as_of: datetime
