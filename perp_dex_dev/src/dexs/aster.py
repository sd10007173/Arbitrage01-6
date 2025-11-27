import requests
from typing import List
from ..common.base_fetcher import BaseFetcher
from ..common.models import FundingRate

class AsterFetcher(BaseFetcher):
    def __init__(self):
        super().__init__("aster")
        self.base_url = "https://fapi.asterdex.com"

    def fetch_history(self, symbol: str, start_time: int, end_time: int) -> List[FundingRate]:
        # Aster likely uses standard symbol format e.g. "BTCUSDT"
        # If input is "BTC-USD", we might need to convert.
        # Assuming input symbol is compatible or user provides correct one.
        formatted_symbol = symbol.replace("-", "")

        # Check if time range exceeds 7 days (Aster API limit)
        time_range_days = (end_time - start_time) / (1000 * 60 * 60 * 24)

        if time_range_days > 7:
            # Auto-segment for ranges > 7 days
            return self._fetch_segmented(formatted_symbol, symbol, start_time, end_time)
        else:
            # Single request for ranges <= 7 days
            return self._fetch_single(formatted_symbol, symbol, start_time, end_time)

    def _fetch_single(self, formatted_symbol: str, original_symbol: str, start_time: int, end_time: int) -> List[FundingRate]:
        """Fetch data for a single time segment (≤ 7 days)"""
        endpoint = "/fapi/v1/fundingRate"
        url = f"{self.base_url}{endpoint}"

        params = {
            "symbol": formatted_symbol,
            "startTime": start_time,
            "endTime": end_time,
            "limit": 1000
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return self.normalize_response(data, original_symbol)
        except Exception as e:
            print(f"Error fetching data from Aster: {e}")
            return []

    def _fetch_segmented(self, formatted_symbol: str, original_symbol: str, start_time: int, end_time: int) -> List[FundingRate]:
        """Fetch data in 7-day segments and merge"""
        print(f"Time range exceeds 7 days. Auto-segmenting...")

        all_rates = []
        current_start = start_time
        segment_duration = 7 * 24 * 60 * 60 * 1000  # 7 days in milliseconds
        segment_num = 1

        while current_start < end_time:
            # Calculate segment end (max 7 days or end_time)
            current_end = min(current_start + segment_duration, end_time)

            # Convert to datetime for display
            from datetime import datetime
            start_date = datetime.fromtimestamp(current_start / 1000).strftime('%Y-%m-%d')
            end_date = datetime.fromtimestamp(current_end / 1000).strftime('%Y-%m-%d')

            print(f"  Segment {segment_num}: {start_date} to {end_date}")

            # Fetch this segment
            segment_rates = self._fetch_single(formatted_symbol, original_symbol, current_start, current_end)

            if segment_rates:
                all_rates.extend(segment_rates)
                print(f"  → Got {len(segment_rates)} records")

            # Move to next segment
            current_start = current_end
            segment_num += 1

        # Sort by timestamp to ensure chronological order
        all_rates.sort(key=lambda x: x.timestamp)

        print(f"Total segments: {segment_num - 1}, Total records: {len(all_rates)}")
        return all_rates

    def normalize_response(self, data: list, symbol: str) -> List[FundingRate]:
        funding_rates = []
        for item in data:
            # Standard Binance-like response:
            # {"symbol": "BTCUSDT", "fundingTime": 1600000000000, "fundingRate": "0.0001"}
            funding_rates.append(FundingRate(
                exchange=self.exchange_name,
                symbol=symbol,
                timestamp=item['fundingTime'],
                rate=float(item['fundingRate']),
                interval="8h",  # Aster funding is every 8 hours
                is_settlement=True  # All records from Aster API are settlement records
            ))
        return funding_rates
