import requests
from typing import List
from ..common.base_fetcher import BaseFetcher
from ..common.models import FundingRate

class EdgeXFetcher(BaseFetcher):
    def __init__(self):
        super().__init__("edgex")
        self.base_url = "https://pro.edgex.exchange"

    def fetch_history(self, symbol: str, start_time: int, end_time: int) -> List[FundingRate]:
        # EdgeX requires a numeric contractId.
        # We need to fetch metadata to map symbol to contractId.
        
        # Normalize symbol: remove hyphens (e.g. ETH-USDT -> ETHUSDT)
        normalized_symbol = symbol.replace("-", "")
        
        contract_id = self.get_contract_id(normalized_symbol)
        if not contract_id:
            print(f"Could not find contract ID for {symbol} ({normalized_symbol})")
            return []

        # EdgeX endpoint for funding rate history
        endpoint = "/api/v1/public/funding/getFundingRatePage"
        url = f"{self.base_url}{endpoint}"
        
        all_rates = []
        offset_data = None

        # Loop for pagination with safety limit
        page_count = 1
        max_pages = 1000  # Safety limit to prevent infinite loops
        while page_count <= max_pages:
            params = {
                "contractId": contract_id,
                "size": 100,
                "filterBeginTimeInclusive": start_time,
                "filterEndTimeExclusive": end_time
            }
            if offset_data:
                params["offsetData"] = offset_data
            
            try:
                print(f"Fetching page {page_count}...")
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                new_rates = self.normalize_response(data, symbol)
                print(f"Found {len(new_rates)} new records on page {page_count}.")
                
                if not new_rates:
                    # If we get an offset but no new rates, it might be the end
                    if offset_data:
                        print("Received offset data but no new records. Assuming end of data.")
                        break
                    # If no offset and no rates, definitely the end.
                    break
                    
                all_rates.extend(new_rates)
                page_count += 1
                
                # Check for next page
                if isinstance(data, dict):
                    inner_data = data.get('data', {})
                    offset_data = inner_data.get('nextPageOffsetData')
                    
                    # If no offset data or empty, stop
                    if not offset_data:
                        print("No more pages. Fetching complete.")
                        break
                else:
                    print("Unexpected response format. Stopping.")
                    break
                    
            except Exception as e:
                print(f"Error fetching data from EdgeX on page {page_count}: {e}")
                break

        if page_count > max_pages:
            print(f"Warning: Reached maximum page limit ({max_pages}). There may be more data available.")

        return all_rates

    def get_contract_id(self, symbol: str) -> str:
        endpoint = "/api/v1/public/meta/getMetaData"
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Parse metadata to find contractId
            # Structure: {"data": {"contractList": [{"contractId": "...", "contractName": "..."}, ...]}}
            if isinstance(data, dict):
                inner_data = data.get('data', {})
                contract_list = inner_data.get('contractList', [])
                
                for contract in contract_list:
                    if contract.get('contractName') == symbol:
                        return contract.get('contractId')
            return None
        except Exception as e:
            print(f"Error fetching metadata from EdgeX: {e}")
            return None

    def normalize_response(self, data: dict, symbol: str) -> List[FundingRate]:
        funding_rates = []
        # Response structure: {"data": [{"fundingTimestamp": ..., "fundingRate": ...}, ...]}
        # or list directly? Docs said "response structure seems to be under schemafundingrate"
        # Let's handle both list and dict with 'data' key just in case.
        
        items = []
        if isinstance(data, dict):
            inner_data = data.get('data', {})
            if isinstance(inner_data, dict):
                items = inner_data.get('dataList', [])
            elif isinstance(inner_data, list):
                items = inner_data
        elif isinstance(data, list):
            items = data
            
        for item in items:
            # Fields: fundingTimestamp, fundingRate, isSettlement, fundingRateIntervalMin
            timestamp = item.get('fundingTimestamp')
            rate = item.get('fundingRate')
            is_settlement = item.get('isSettlement')
            interval_min = item.get('fundingRateIntervalMin')

            # Convert interval from minutes to hours
            interval = None
            if interval_min:
                hours = int(interval_min) / 60
                if hours >= 1:
                    interval = f"{int(hours)}h"
                else:
                    interval = f"{int(interval_min)}m"

            if timestamp and rate is not None:
                funding_rates.append(FundingRate(
                    exchange=self.exchange_name,
                    symbol=symbol,
                    timestamp=int(timestamp),
                    rate=float(rate),
                    interval=interval,
                    is_settlement=is_settlement
                ))
        return funding_rates
