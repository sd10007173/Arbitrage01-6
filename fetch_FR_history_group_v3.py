import aiohttp
import asyncio
import sqlite3
from datetime import datetime, timezone, timedelta
import time
import ssl
import certifi
import pandas as pd
import argparse
import sys
import os

# 為了引入 perp_dex_dev，將當前目錄加入 path
sys.path.append(os.getcwd())

# 引入 DEX Fetchers
try:
    from perp_dex_dev.src.dexs.edgex import EdgeXFetcher
    from perp_dex_dev.src.dexs.hyperliquid import HyperliquidFetcher
    from perp_dex_dev.src.dexs.aster import AsterFetcher
    DEX_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 無法引入 perp_dex_dev 模組: {e}")
    print("   請確保 perp_dex_dev 目錄存在且結構正確")
    DEX_AVAILABLE = False

# --- 全局配置 ---
SEMAPHORE_LIMIT = 1  # 限制併發數
MAX_RETRIES = 3
RETRY_DELAY = 5
DB_PATH = "data/funding_rate.db"
SUPPORTED_EXCHANGES = ['binance', 'bybit', 'okx', 'gate', 'edgex', 'hyperliquid', 'aster']
CHUNK_DAYS = 5
WAIT_TIME = 0.5

# --- SQLite 適配器 ---
def adapt_datetime_iso(val):
    return val.isoformat()
sqlite3.register_adapter(datetime, adapt_datetime_iso)

def get_connection():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def get_latest_funding_rate_date():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(DATE(timestamp_utc)) FROM funding_rate_history")
        result = cursor.fetchone()
        conn.close()
        if result and result[0]: return result[0]
        else: sys.exit("❌ funding_rate_history表為空")
    except Exception as e: sys.exit(f"❌ 查詢錯誤: {e}")

def process_date_input(date_input, date_type="start"):
    if date_input == "up_to_date":
        if date_type == "start":
            return get_latest_funding_rate_date()
        else:
            return (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        try:
            datetime.fromisoformat(date_input)
            return date_input
        except ValueError: raise ValueError(f"無效日期: {date_input}")

def validate_date_range(start_date_str, end_date_str, is_auto_mode=False):
    start_dt = datetime.fromisoformat(start_date_str)
    end_dt = datetime.fromisoformat(end_date_str)
    if start_dt > end_dt:
        if not is_auto_mode: print("❌ 開始日期不能晚於結束日期")
        return False
    return True

async def get_target_pairs(conn, exchanges, top_n):
    cursor = conn.cursor()
    tasks = []
    
    # 構建查詢
    select_cols = ", ".join([f"{ex}_support, {ex}_list_date" for ex in exchanges])
    query = f"SELECT id, symbol, trading_pair, market_cap_rank, {select_cols} FROM trading_pair"
    
    if top_n != "all":
        query += " WHERE market_cap_rank IS NOT NULL AND market_cap_rank <= ?"
        params = (top_n,)
    else:
        query += " WHERE 1=1" # 簡單的 where true
        params = ()
        
    query += " ORDER BY market_cap_rank"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    for row in rows:
        for ex in exchanges:
            if row[f'{ex}_support']:
                tasks.append({
                    "symbol": row['symbol'],
                    "trading_pair": row['trading_pair'],
                    "exchange": ex,
                    "list_date": row[f'{ex}_list_date']
                })
    return tasks

async def save_funding_rates(conn, df, exchange, symbol):
    if df.empty: return 0
    to_insert = []
    for timestamp_utc, row in df.iterrows():
        funding_rate = row['funding_rate'] if pd.notna(row['funding_rate']) else None
        to_insert.append((timestamp_utc.to_pydatetime(), symbol, exchange, funding_rate))
    
    if not to_insert: return 0
    
    cursor = conn.cursor()
    try:
        cursor.executemany("""
            INSERT INTO funding_rate_history (timestamp_utc, symbol, exchange, funding_rate)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(timestamp_utc, symbol, exchange) DO UPDATE SET
            funding_rate=excluded.funding_rate, updated_at=CURRENT_TIMESTAMP
        """, to_insert)
        conn.commit()
        return cursor.rowcount
    except sqlite3.Error as e:
        print(f"❌ 資料庫儲存錯誤 ({symbol}_{exchange}): {e}")
        return 0

# --- CEX Fetcher ---
async def fetch_funding_rates_rest(session, exchange, symbol, trading_pair, start_dt, end_dt):
    all_data = []
    current_dt = start_dt
    
    while current_dt < end_dt:
        fetch_end = min(current_dt + timedelta(days=CHUNK_DAYS), end_dt)
        params = {}
        url = ""
        
        if exchange == 'binance':
            url = "https://fapi.binance.com/fapi/v1/fundingRate"
            params = {"symbol": trading_pair, "startTime": int(current_dt.timestamp()*1000), "endTime": int(fetch_end.timestamp()*1000), "limit": 1000}
        elif exchange == 'bybit':
            url = "https://api.bybit.com/v5/market/funding/history"
            params = {"symbol": trading_pair, "category": "linear", "startTime": int(current_dt.timestamp()*1000), "endTime": int(fetch_end.timestamp()*1000), "limit": 200}
        elif exchange == 'okx':
            url = "https://www.okx.com/api/v5/public/funding-rate-history"
            params = {"instId": f"{symbol}-USDT-SWAP", "after": int(fetch_end.timestamp()*1000), "limit": 100}
            
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, params=params, timeout=20) as response:
                    response.raise_for_status()
                    data = await response.json()
                    if exchange == 'binance': all_data.extend(data)
                    elif exchange == 'bybit': 
                        if data.get("retCode") == 0 and data.get("result", {}).get("list"): all_data.extend(data["result"]["list"])
                    elif exchange == 'okx':
                        if data.get("code") == "0": all_data.extend(data.get("data", []))
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1: await asyncio.sleep(RETRY_DELAY)
                else: print(f"❌ ({exchange}) {symbol} 請求失敗: {e}")
        
        await asyncio.sleep(WAIT_TIME)
        current_dt = fetch_end
        if exchange == 'okx': break # OKX 特殊處理
        
    return all_data

# --- DEX Fetcher Wrapper ---
def fetch_dex_funding_rates(exchange, symbol, start_dt, end_dt):
    """同步調用 perp_dex_dev 的 fetcher"""
    if not DEX_AVAILABLE: return []
    
    fetcher = None
    target_symbol = ""
    
    # Symbol 映射與 Fetcher 初始化
    if exchange == 'edgex':
        fetcher = EdgeXFetcher()
        target_symbol = f"{symbol}-USD" # EdgeX 需要 ETH-USD
    elif exchange == 'hyperliquid':
        fetcher = HyperliquidFetcher()
        target_symbol = symbol # Hyperliquid 需要 ETH
    elif exchange == 'aster':
        fetcher = AsterFetcher()
        target_symbol = f"{symbol}USDT" # Aster 需要 ETHUSDT
        
    if not fetcher: return []
    
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)
    
    try:
        # 調用 perp_dex_dev 的 fetch_history
        rates = fetcher.fetch_history(target_symbol, start_ts, end_ts)
        
        # 過濾 is_settlement == True
        settlement_rates = [r for r in rates if r.is_settlement]
        
        # 轉換格式
        processed_data = []
        for r in settlement_rates:
            # 轉換為 UTC datetime
            ts = datetime.fromtimestamp(r.timestamp / 1000, tz=timezone.utc)
            processed_data.append({
                'timestamp_utc': ts,
                'funding_rate': r.rate
            })
            
        return processed_data
        
    except Exception as e:
        print(f"❌ ({exchange}) {symbol} DEX 獲取失敗: {e}")
        return []

async def fetch_and_save_fr(session, task, start_date, end_date):
    symbol = task['symbol']
    exchange_id = task['exchange']
    trading_pair = task['trading_pair']
    
    # 1. 確定開始日期
    actual_start_date = start_date
    if task['list_date']:
        list_date_dt = datetime.fromisoformat(task['list_date']).replace(tzinfo=timezone.utc)
        actual_start_date = max(start_date, list_date_dt)
        if list_date_dt >= end_date:
            print(f"ℹ️ ({exchange_id}) {symbol}: 上市日期晚於結束日期，跳過。")
            return

    # 2. 增量檢查 (省略部分代碼以保持簡潔，邏輯同 V2)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT DATE(timestamp_utc)) FROM funding_rate_history 
        WHERE symbol = ? AND exchange = ? AND DATE(timestamp_utc) BETWEEN DATE(?) AND DATE(?)
    """, (symbol, exchange_id, actual_start_date.date(), (end_date - timedelta(days=1)).date()))
    existing_days = cursor.fetchone()[0]
    expected_days = (end_date.date() - actual_start_date.date()).days
    
    if existing_days >= expected_days and expected_days > 0:
        print(f"✅ ({exchange_id}) {symbol}: 數據已完整，跳過。")
        conn.close()
        return
        
    # 查找最新數據點以進行增量更新
    if existing_days > 0:
        cursor.execute("""
            SELECT MAX(timestamp_utc) FROM funding_rate_history 
            WHERE symbol = ? AND exchange = ? AND DATE(timestamp_utc) BETWEEN DATE(?) AND DATE(?)
        """, (symbol, exchange_id, actual_start_date.date(), (end_date - timedelta(days=1)).date()))
        latest = cursor.fetchone()[0]
        if latest:
            actual_start_date = max(actual_start_date, datetime.fromisoformat(latest).replace(tzinfo=timezone.utc) + timedelta(hours=1))
    conn.close()
    
    if actual_start_date >= end_date: return

    print(f"🚀 ({exchange_id}) 開始獲取 {symbol} 從 {actual_start_date}...")

    # 3. 獲取數據
    api_df = None
    
    if exchange_id in ['binance', 'bybit', 'okx', 'gate']:
        # CEX: 異步獲取
        api_rates = await fetch_funding_rates_rest(session, exchange_id, symbol, trading_pair, actual_start_date, end_date)
        if api_rates:
            processed = []
            for r in api_rates:
                try:
                    ts = None
                    rate = 0.0
                    if exchange_id == 'binance':
                        ts = datetime.fromtimestamp(int(r['fundingTime'])/1000, tz=timezone.utc)
                        rate = float(r['fundingRate'])
                    elif exchange_id == 'bybit':
                        ts = datetime.fromtimestamp(int(r['fundingRateTimestamp'])/1000, tz=timezone.utc)
                        rate = float(r['fundingRate'])
                    elif exchange_id == 'okx':
                        ts = datetime.fromtimestamp(int(r['fundingTime'])/1000, tz=timezone.utc)
                        rate = float(r['fundingRate'])
                    
                    if ts:
                        processed.append({'timestamp_utc': ts.replace(minute=0, second=0, microsecond=0), 'funding_rate': rate})
                except: pass
            
            if processed:
                temp_df = pd.DataFrame(processed)
                api_df = temp_df.groupby('timestamp_utc').last()
                
    elif exchange_id in ['edgex', 'hyperliquid', 'aster']:
        # DEX: 同步獲取 (在異步函數中執行)
        # 為了不阻塞，使用 run_in_executor (雖然這裡是簡單的實現，直接調用也行，因為並發數低)
        loop = asyncio.get_event_loop()
        dex_data = await loop.run_in_executor(None, fetch_dex_funding_rates, exchange_id, symbol, actual_start_date, end_date)
        
        if dex_data:
            temp_df = pd.DataFrame(dex_data)
            # DEX 數據已經過濾過 settlement，且轉換好格式
            # 對齊到整點 (雖然 DEX 通常已經是整點，但保險起見)
            temp_df['timestamp_utc'] = temp_df['timestamp_utc'].apply(lambda x: x.replace(minute=0, second=0, microsecond=0))
            api_df = temp_df.groupby('timestamp_utc').last()

    # 4. 合併與保存
    hourly_index = pd.date_range(start=actual_start_date, end=end_date - timedelta(hours=1), freq='h', tz='UTC')
    final_df = pd.DataFrame(index=hourly_index)
    final_df.index.name = 'timestamp_utc'
    
    if api_df is not None:
        final_df = final_df.join(api_df)
        
    if not final_df.empty:
        conn = get_connection()
        count = await save_funding_rates(conn, final_df, exchange_id, symbol)
        conn.close()
        print(f"✅ ({exchange_id}) {symbol}: 存入 {count} 筆數據。")
    else:
        print(f"ℹ️ ({exchange_id}) {symbol}: 無數據。")

async def main(exchanges=None, top_n=None, start_date=None, end_date=None):
    print("--- 資金費率歷史獲取 V3 (支援 DEX) ---")
    
    # 參數處理 (省略部分交互式邏輯，專注於命令行)
    if not exchanges: exchanges = SUPPORTED_EXCHANGES
    
    start_date_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    end_date_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc) + timedelta(days=1)
    
    conn = get_connection()
    tasks = await get_target_pairs(conn, exchanges, top_n)
    conn.close()
    
    if not tasks:
        print("無任務。")
        return

    print(f"準備執行 {len(tasks)} 個任務...")
    
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    async def run_with_semaphore(task):
        async with semaphore:
            await fetch_and_save_fr(session, task, start_date_dt, end_date_dt)

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        await asyncio.gather(*[run_with_semaphore(t) for t in tasks])

    print("🎉 完成！")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch FR History V3')
    parser.add_argument('--exchanges', nargs='+', choices=SUPPORTED_EXCHANGES)
    parser.add_argument('--top_n', type=str)
    parser.add_argument('--start_date', type=str)
    parser.add_argument('--end_date', type=str)
    args = parser.parse_args()
    
    # 簡單的參數處理
    top_n_val = "all" if args.top_n == "all" else int(args.top_n)
    start_val = process_date_input(args.start_date, "start")
    end_val = process_date_input(args.end_date, "end")
    
    asyncio.run(main(args.exchanges, top_n_val, start_val, end_val))