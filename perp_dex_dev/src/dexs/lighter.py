import requests
from typing import List
from ..common.base_fetcher import BaseFetcher
from ..common.models import FundingRate

class LighterFetcher(BaseFetcher):
    def __init__(self):
        super().__init__("lighter")
        self.base_url = "https://mainnet.zklighter.elliot.ai/api/v1/funding-rates"

    def fetch_history(self, symbol: str, start_time: int, end_time: int) -> List[FundingRate]:
        # Lighter endpoint seems to return current rates. 
        # We will try to pass query params for history if supported.
        # If not, it might only return current.
        
        params = {
            "symbol": symbol,
            # "start_time": start_time, # Guessing parameters
            # "end_time": end_time
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            print(f"DEBUG: Lighter raw response: {data}")
            return self.normalize_response(data, symbol)
        except Exception as e:
            print(f"Error fetching data from Lighter: {e}")
            return []

    def normalize_response(self, data: dict, symbol: str) -> List[FundingRate]:
        funding_rates = []
        # The search result said response includes market_id, symbol, rate.
        # It might be a single object or list.
        if isinstance(data, list):
            items = data
        else:
            items = [data]
            
        for item in items:
            # Check if symbol matches if we got all rates
            if item.get('symbol') == symbol or symbol in item.get('symbol', ''):
                funding_rates.append(FundingRate(
                    exchange=self.exchange_name,
                    symbol=item.get('symbol', symbol),
                    timestamp=int(time.time() * 1000), # If no timestamp, use current
                    rate=float(item.get('rate', 0)),
                    interval="1h"
                ))
        return funding_rates
