import argparse
import time
import csv
from datetime import datetime, timedelta
from pathlib import Path
from src.dexs.hyperliquid import HyperliquidFetcher
from src.dexs.aster import AsterFetcher
from src.dexs.edgex import EdgeXFetcher
from src.dexs.lighter import LighterFetcher

def main():
    parser = argparse.ArgumentParser(description="Fetch historical funding rates from Perp DEXs.")
    parser.add_argument("exchange", choices=["hyperliquid", "aster", "edgex", "lighter"], help="The exchange to fetch from.")
    parser.add_argument("--symbol", type=str, required=True, help="The trading symbol (e.g., BTC-USD, ETHUSDT).")
    parser.add_argument("--days", type=int, default=1, help="Number of days of history to fetch (default: 1).")
    parser.add_argument("--start-date", type=str, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", type=str, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--output", type=str, help="Output CSV file path (e.g., data/funding_rates.csv). If not specified, data will only be displayed.")
    parser.add_argument("--settlement-only", action="store_true", help="Only include settlement records (actual funding rate payments, not snapshots).")

    args = parser.parse_args()
    
    # Calculate time range
    if args.start_date:
        start_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
        start_time = int(start_dt.timestamp() * 1000)

        if args.end_date:
            end_dt = datetime.strptime(args.end_date, "%Y-%m-%d")
            # Set end time to end of that day (23:59:59) or just use the date
            # Let's assume end of day for inclusivity or just the timestamp
            end_time = int(end_dt.timestamp() * 1000)
        else:
            end_time = int(time.time() * 1000)
    else:
        end_time = int(time.time() * 1000)
        start_time = int((datetime.now() - timedelta(days=args.days)).timestamp() * 1000)

    # Validate date range
    current_time = int(time.time() * 1000)
    if start_time > current_time or end_time > current_time:
        print("Warning: Your date range includes future dates. Most exchanges don't have data for future dates.")
        print(f"Current time: {datetime.fromtimestamp(current_time/1000)}")
        print(f"Your range: {datetime.fromtimestamp(start_time/1000)} to {datetime.fromtimestamp(end_time/1000)}")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    fetcher = None
    if args.exchange == "hyperliquid":
        fetcher = HyperliquidFetcher()
    elif args.exchange == "aster":
        fetcher = AsterFetcher()
    elif args.exchange == "edgex":
        fetcher = EdgeXFetcher()
    elif args.exchange == "lighter":
        fetcher = LighterFetcher()
        
    print(f"Fetching data from {args.exchange} for {args.symbol}...")
    print(f"Time range: {datetime.fromtimestamp(start_time/1000)} to {datetime.fromtimestamp(end_time/1000)}")
    
    rates = fetcher.fetch_history(args.symbol, start_time, end_time)

    if not rates:
        print("No data fetched.")
        return

    print(f"Fetched {len(rates)} records.")

    # Filter for settlement records only if requested
    if args.settlement_only:
        original_count = len(rates)
        rates = [r for r in rates if r.is_settlement is True]
        print(f"Filtered to {len(rates)} settlement records (removed {original_count - len(rates)} non-settlement records).")

        if not rates:
            print("No settlement records found in the fetched data.")
            return
    print("First 5 records:")
    for rate in rates[:5]:
        print(rate.to_dict())
    print("Last 5 records:")
    for rate in rates[-5:]:
        print(rate.to_dict())

    # Generate output filename
    if args.output:
        output_path = Path(args.output)
    else:
        # Auto-generate filename: {exchange}_{symbol}_{start_date}_to_{end_date}[_settlement]_{timestamp}.csv
        start_date_str = datetime.fromtimestamp(start_time/1000).strftime('%Y%m%d')
        end_date_str = datetime.fromtimestamp(end_time/1000).strftime('%Y%m%d')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Add 'settlement' suffix if --settlement-only is used
        settlement_suffix = '_settlement' if args.settlement_only else ''

        filename = f"{args.exchange}_{args.symbol}_{start_date_str}_to_{end_date_str}{settlement_suffix}_{timestamp}.csv"
        output_path = Path("data") / filename

    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['exchange', 'symbol', 'timestamp', 'datetime', 'rate', 'interval', 'is_settlement'])
        writer.writeheader()
        for rate in rates:
            row = rate.to_dict()
            # Add human-readable datetime field
            row['datetime'] = datetime.fromtimestamp(rate.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow(row)

    print(f"\nData saved to {output_path}")
    print(f"Total records saved: {len(rates)}")

if __name__ == "__main__":
    main()
