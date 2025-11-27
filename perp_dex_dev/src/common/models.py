from dataclasses import dataclass
from typing import Optional

@dataclass
class FundingRate:
    exchange: str
    symbol: str
    timestamp: int  # Unix timestamp in milliseconds
    rate: float
    interval: Optional[str] = None  # e.g., "1h", "8h"
    is_settlement: Optional[bool] = None  # Whether this is an actual settlement time

    def to_dict(self):
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "rate": self.rate,
            "interval": self.interval,
            "is_settlement": self.is_settlement
        }
