from abc import ABC, abstractmethod
from typing import List
from .models import FundingRate

class BaseFetcher(ABC):
    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name

    @abstractmethod
    def fetch_history(self, symbol: str, start_time: int, end_time: int) -> List[FundingRate]:
        """
        Fetch historical funding rates.
        
        Args:
            symbol: The trading symbol (e.g., "BTC-USD").
            start_time: Start timestamp in milliseconds.
            end_time: End timestamp in milliseconds.
            
        Returns:
            List[FundingRate]: A list of FundingRate objects.
        """
        pass
