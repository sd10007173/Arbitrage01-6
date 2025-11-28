#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V11版本：新增 DEX 支援檢查 (EdgeX, Hyperliquid, Aster)
- 繼承 V10 的所有功能 (Bybit 修復, Binance OHLC, OKX/Gate 優化)
- 新增 EdgeX, Hyperliquid, Aster 的支援檢查
- 使用 perp_dex_dev 中的邏輯或直接 API 請求
"""

import ccxt
import sqlite3
import time
import argparse
import requests
import json
from datetime import datetime, timedelta

# 引入 perp_dex_dev 的 fetchers (如果路徑允許，否則使用直接 API)
# 為了避免路徑問題，這裡我們直接實作輕量級的檢查邏輯，參考 perp_dex_dev 的實作

def connect_db():
    """連接資料庫"""
    return sqlite3.connect('data/funding_rate.db')

def update_exchange_support(conn, trading_pair_id, exchange_name, supported, listing_date):
    """更新交易所支援狀態到資料庫"""
    cursor = conn.cursor()

    # 構建欄位名稱
    support_column = f"{exchange_name}_support"
    date_column = f"{exchange_name}_list_date"

    if listing_date:
        cursor.execute(f"""
            UPDATE trading_pair 
            SET {support_column} = ?, {date_column} = ?
            WHERE id = ?
        """, (supported, listing_date.strftime('%Y-%m-%d'), trading_pair_id))
    else:
        cursor.execute(f"""
            UPDATE trading_pair 
            SET {support_column} = ?, {date_column} = NULL
            WHERE id = ?
        """, (supported, trading_pair_id))

# --- CEX 相關邏輯 (從 V10 複製) ---

def get_listing_date_from_info(market_info):
    """從市場的 'info' 字段中嘗試提取上市日期"""
    if not market_info:
        return None
    possible_keys = ['listingTime', 'listTime', 'onboardDate', 'created_at', 'onlineTime', 'publishTime', 'listing_time', 'launchTime']
    for key in possible_keys:
        if key in market_info and market_info[key]:
            try:
                ts = int(market_info[key])
                if ts > 10 ** 12: return datetime.fromtimestamp(ts / 1000)
                else: return datetime.fromtimestamp(ts)
            except (ValueError, TypeError):
                continue
    return None

def get_bybit_launch_time(exchange, symbol_slash):
    try:
        symbol = symbol_slash.split('/')[0] + symbol_slash.split('/')[1].split(':')[0]
        result = exchange.publicGetV5MarketInstrumentsInfo({'category': 'linear', 'symbol': symbol})
        if result['result']['list']:
            instrument = result['result']['list'][0]
            launch_time_ms = instrument.get('launchTime')
            if launch_time_ms and launch_time_ms != "0":
                return datetime.fromtimestamp(int(launch_time_ms) / 1000)
        return None
    except Exception as e:
        print(f"    ❌ bybit LaunchTime 查詢失敗: {e}")
        return None

def check_volume_and_get_listing_date(exchange, symbol_slash, exchange_name):
    try:
        # 檢查最近3天成交量
        recent_ohlcv = exchange.fetch_ohlcv(symbol_slash, '1d', limit=3)
        if not recent_ohlcv: return False, None
        has_recent_volume = any(candle[5] > 0 for candle in recent_ohlcv if candle[5] is not None)
        if not has_recent_volume: return False, None

        listing_date = None
        if exchange_name == 'bybit':
            listing_date = get_bybit_launch_time(exchange, symbol_slash)
        elif exchange_name == 'binance':
            try:
                early_ohlcv = exchange.fetch_ohlcv(symbol_slash, '1d', since=exchange.parse8601('2015-01-01T00:00:00Z'), limit=1)
                if early_ohlcv: return True, datetime.fromtimestamp(early_ohlcv[0][0] / 1000)
            except Exception: pass
        elif exchange_name in ['okx', 'gate']:
            listing_date = None # 跳過 API 呼叫

        if listing_date:
            return True, listing_date
        else:
            return True, None
    except Exception as e:
        print(f"    ❌ 檢查失敗: {e}")
        return False, None

# --- DEX 相關邏輯 (新增) ---

def check_aster_support(symbol):
    """檢查 Aster 支援狀態與上市日期"""
    try:
        url = "https://fapi.asterdex.com/fapi/v1/exchangeInfo"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        target_symbol = f"{symbol}USDT"
        
        if "symbols" in data:
            for item in data["symbols"]:
                if item["symbol"] == target_symbol:
                    # 找到交易對
                    onboard_date = None
                    if "onboardDate" in item:
                        try:
                            ts = int(item["onboardDate"])
                            onboard_date = datetime.fromtimestamp(ts / 1000)
                        except:
                            pass
                    return True, onboard_date
        return False, None
    except Exception as e:
        print(f"    ❌ Aster 檢查失敗: {e}")
        return False, None

def check_edgex_support(symbol):
    """檢查 EdgeX 支援狀態與上市日期 (二分法搜尋)"""
    try:
        # 1. Check Support
        meta_url = "https://pro.edgex.exchange/api/v1/public/meta/getMetaData"
        response = requests.get(meta_url, timeout=10)
        data = response.json()
        target_name = f"{symbol}USD" # EdgeX uses BTCUSD
        
        is_supported = False
        if "data" in data and "contractList" in data["data"]:
            for contract in data["data"]["contractList"]:
                if contract.get("contractName") == target_name:
                    is_supported = True
                    break
        
        if not is_supported: return False, None

        # 2. Binary Search for Listing Date (using Funding Rate History as proxy since Kline API is elusive)
        # EdgeX Funding Rate API: /api/v1/public/market/fundingHistory
        # We need to find the earliest date with data.
        # Range: 2020-01-01 to Now
        
        print(f"    🔍 EdgeX: 正在搜尋 {symbol} 上市日期...")
        
        low = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
        high = datetime.now(timezone.utc).timestamp() * 1000
        earliest_date = None
        
        # Optimization: Check if data exists at 'low' first? No, likely not.
        # Strategy: Binary search for the transition from No Data -> Data
        
        # EdgeX Funding History API
        # url = "https://pro.edgex.exchange/api/v1/public/market/fundingHistory"
        # params: symbol=BTC-USD, page=1, size=10, startTime=...
        
        # Let's try a simpler approach first: Check yearly, then monthly? 
        # Or standard binary search.
        
        # Since we don't have a reliable Kline API for EdgeX yet (404s), 
        # and Funding History might be heavy.
        # Let's try to find a working Kline API again or use Funding History.
        # Based on perp_dex_dev, EdgeX uses:
        # https://pro.edgex.exchange/api/v1/public/market/fundingHistory
        
        # Let's use Funding History for binary search.
        
        def has_data(ts):
            url = "https://pro.edgex.exchange/api/v1/public/market/fundingHistory"
            # Check a 1-day window around ts
            params = {
                "symbol": f"{symbol}-USD",
                "page": 1,
                "size": 1,
                "startTime": int(ts),
                "endTime": int(ts + 86400000)
            }
            try:
                r = requests.get(url, params=params, timeout=5)
                d = r.json()
                if d.get("code") == "0" and d.get("data") and d.get("data").get("list"):
                    return True
                return False
            except:
                return False

        # Refined Binary Search
        # We want to find T such that has_data(T) is True and has_data(T-1day) is False.
        
        # First, ensure we have data at 'high' (Now)
        if not has_data(high - 86400000):
            # Maybe it's a very new pair or API issue
            return True, None
            
        # Binary Search
        iterations = 0
        while high - low > 86400000: # 1 day precision
            mid = (low + high) / 2
            if has_data(mid):
                high = mid # Data exists, look earlier
                earliest_date = mid
            else:
                low = mid # No data, look later
            iterations += 1
            if iterations > 20: break # Safety break
            
        if earliest_date:
            return True, datetime.fromtimestamp(earliest_date / 1000)
        else:
            return True, None

    except Exception as e:
        print(f"    ❌ EdgeX 檢查失敗: {e}")
        return False, None

def check_hyperliquid_support(symbol):
    """檢查 Hyperliquid 支援狀態與上市日期 (二分法搜尋)"""
    try:
        # 1. Check Support
        url = "https://api.hyperliquid.xyz/info"
        response = requests.post(url, json={"type": "meta"}, timeout=10)
        data = response.json()
        target_coin = symbol
        
        is_supported = False
        if "universe" in data:
            for asset in data["universe"]:
                if asset.get("name") == target_coin:
                    is_supported = True
                    break
        
        if not is_supported: return False, None

        # 2. Binary Search for Listing Date using Candle Snapshot
        # Hyperliquid Candle API is efficient.
        print(f"    🔍 Hyperliquid: 正在搜尋 {symbol} 上市日期...")
        
        low = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
        high = datetime.now(timezone.utc).timestamp() * 1000
        earliest_date = None
        
        def has_data(ts):
            # Check if there is any candle in a 1-week window starting from ts
            # Using a wider window to avoid gaps
            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol,
                    "interval": "1d",
                    "startTime": int(ts),
                    "endTime": int(ts + 86400000 * 7) 
                }
            }
            try:
                r = requests.post("https://api.hyperliquid.xyz/info", json=payload, timeout=5)
                d = r.json()
                if isinstance(d, list) and len(d) > 0:
                    return True
                return False
            except:
                return False

        # Ensure data at 'high'
        if not has_data(high - 86400000 * 7):
             return True, None

        iterations = 0
        while high - low > 86400000: # 1 day precision
            mid = (low + high) / 2
            if has_data(mid):
                high = mid
                earliest_date = mid
            else:
                low = mid
            iterations += 1
            if iterations > 20: break
            
        if earliest_date:
            return True, datetime.fromtimestamp(earliest_date / 1000)
        else:
            return True, None

    except Exception as e:
        print(f"    ❌ Hyperliquid 檢查失敗: {e}")
        return False, None

# --- 主程式 ---

def main(exchanges=None, top_n=None):
    start_time = time.time()
    print("=" * 60)
    print("🚀 V11版本：新增 DEX 支援 (EdgeX, Hyperliquid, Aster)")
    print("=" * 60)

    conn = connect_db()
    cursor = conn.cursor()

    # 構建查詢語句
    query = "SELECT id, symbol, trading_pair FROM trading_pair"
    params = []
    if top_n is not None:
        query += " WHERE market_cap_rank IS NOT NULL AND market_cap_rank <= ?"
        params.append(top_n)
        print(f"📊 篩選條件: 市值排名前 {top_n} 名")
    query += " ORDER BY market_cap_rank"

    cursor.execute(query, params)
    trading_pairs_from_db = cursor.fetchall()
    total_pairs = len(trading_pairs_from_db)
    print(f"\n📊 總共需要處理 {total_pairs} 個交易對")

    # 確定要檢查的交易所
    cex_list = ['binance', 'bybit', 'okx', 'gate']
    dex_list = ['aster', 'edgex', 'hyperliquid']
    all_supported = cex_list + dex_list
    
    if exchanges is not None:
        exchanges_to_check = [ex for ex in exchanges if ex in all_supported]
        print(f"🎯 指定檢查交易所: {exchanges_to_check}")
    else:
        exchanges_to_check = all_supported
        print(f"🔍 檢查所有支持的交易所: {exchanges_to_check}")

    # 初始化 CEX 連接
    all_exchanges = {}
    all_markets = {}
    print(f"\n🔗 正在連接 CEX 交易所...")
    for ex_name in exchanges_to_check:
        if ex_name in cex_list:
            try:
                if ex_name == 'binance': instance = ccxt.binance({'options': {'defaultType': 'future'}})
                elif ex_name == 'bybit': instance = ccxt.bybit({'options': {'defaultType': 'swap'}})
                elif ex_name == 'okx': instance = ccxt.okx()
                elif ex_name == 'gate': instance = ccxt.gate()
                
                print(f"  ✅ {ex_name} 連接成功")
                all_exchanges[ex_name] = instance
                all_markets[ex_name] = instance.load_markets()
            except Exception as e:
                print(f"  ❌ {ex_name} 連接失敗: {e}")

    print(f"\n🎯 開始處理交易對...")
    total_processed = 0

    for i, row in enumerate(trading_pairs_from_db):
        db_id = row[0]
        symbol = row[1]
        trading_pair = row[2] # e.g., BTCUSDT

        print(f"\n({i + 1}/{total_pairs}) 正在處理: {symbol} ({trading_pair})")

        for ex_name in exchanges_to_check:
            supported = 0
            listing_date = None
            
            # --- CEX 處理 ---
            if ex_name in cex_list:
                exchange_instance = all_exchanges.get(ex_name)
                if not exchange_instance: continue
                
                markets = all_markets.get(ex_name, {})
                symbol_slash = f"{symbol}/USDT:USDT" if ex_name == 'bybit' else f"{symbol}/USDT"
                
                print(f"    🔍 (CEX) 檢查 {ex_name} 的 {symbol}...")
                has_volume, l_date = check_volume_and_get_listing_date(exchange_instance, symbol_slash, ex_name)
                supported = 1 if has_volume else 0
                listing_date = l_date
                
                # 備援：從 market info 找日期
                if supported and not listing_date and trading_pair in markets:
                    market_info = markets.get(trading_pair)
                    if market_info:
                        info_date = get_listing_date_from_info(market_info.get('info'))
                        if info_date: listing_date = info_date

            # --- DEX 處理 ---
            elif ex_name in dex_list:
                print(f"    🔍 (DEX) 檢查 {ex_name} 的 {symbol}...")
                is_supported = False
                l_date = None
                
                if ex_name == 'aster':
                    is_supported, l_date = check_aster_support(symbol)
                elif ex_name == 'edgex':
                    is_supported, l_date = check_edgex_support(symbol)
                elif ex_name == 'hyperliquid':
                    is_supported, l_date = check_hyperliquid_support(symbol)
                
                supported = 1 if is_supported else 0
                listing_date = l_date

            # 顯示結果
            support_status = "支援" if supported else "不支援"
            date_str = listing_date.date() if listing_date else "未知"
            print(f"    📊 {ex_name}: {support_status}, 上市日期: {date_str}")

            # 更新資料庫
            update_exchange_support(conn, db_id, ex_name, supported, listing_date)
            total_processed += 1

    conn.commit()
    conn.close()
    
    execution_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("🎉 V11版本更新完成！")
    print(f"⏱️  總耗時: {execution_time:.2f} 秒")
    print(f"💾 總更新次數: {total_processed}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='交易所交易對支持檢查工具 V11')
    parser.add_argument('--exchanges', nargs='+', help='指定要檢查的交易所')
    parser.add_argument('--top_n', type=int, help='只檢查市值排名前N名')
    args = parser.parse_args()
    main(exchanges=args.exchanges, top_n=args.top_n)