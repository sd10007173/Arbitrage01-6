import requests
import time
from typing import List
from ..common.base_fetcher import BaseFetcher
from ..common.models import FundingRate

class HyperliquidFetcher(BaseFetcher):
    def __init__(self):
        super().__init__("hyperliquid")
        self.base_url = "https://api.hyperliquid.xyz/info"

    def fetch_history(self, symbol: str, start_time: int, end_time: int) -> List[FundingRate]:
        # Hyperliquid uses "coin" instead of symbol, e.g. "ETH"
        coin = symbol.split("-")[0] if "-" in symbol else symbol
        
        payload = {
            "type": "fundingHistory",
            "coin": coin,
            "startTime": start_time,
            "endTime": end_time
        }
        
        try:
            response = requests.post(self.base_url, json=payload)
            response.raise_for_status()
            data = response.json()
            return self.normalize_response(data, symbol)
        except Exception as e:
            print(f"Error fetching data from Hyperliquid: {e}")
            return []

    def normalize_response(self, data: list, symbol: str) -> List[FundingRate]:
        funding_rates = []
        for item in data:
            # Item structure: {'coin': 'ETH', 'fundingRate': '0.0000125', 'premium': '...', 'time': 1715...}
            funding_rates.append(FundingRate(
                exchange=self.exchange_name,
                symbol=symbol,
                timestamp=item['time'],
                rate=float(item['fundingRate']),
                interval="1h",  # Hyperliquid funding is hourly
                is_settlement=True  # All records from Hyperliquid API are settlement records
            ))
        return funding_rates
