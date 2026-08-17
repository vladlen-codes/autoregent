from datetime import datetime

from pydantic import BaseModel


class AccountBalance(BaseModel):
    """Expected schema for the informational route used throughout the demo."""

    account_id: str
    balance: float
    currency: str
    as_of: datetime
