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

# --- 全局配置 ---
# 將並發限制從 10 調降到 5，以避免觸發幣安的速率限制
SEMAPHORE_LIMIT = 1  # 同時運行的最大異步任務數
MAX_RETRIES = 3      # API請求失敗時的最大重試次數
RETRY_DELAY = 15      # 重試前的延遲秒數 (從2秒增加到5秒，給伺服器更多喘息時間)

# --- 新增：處理 Python 3.12 的 sqlite3 日期時間 DeprecationWarning ---
# 1. 定義一個新的 adapter，將 python datetime 物件轉換為 ISO 8601 字串
def adapt_datetime_iso(val):
    """將 datetime.datetime 適配為時區感知的 ISO 8601 字串"""
    return val.isoformat()

# 2. 註冊這個 adapter 來處理所有的 datetime 物件
sqlite3.register_adapter(datetime, adapt_datetime_iso)
# --- 結束 ---

DB_PATH = "data/funding_rate.db"
SUPPORTED_EXCHANGES = ['binance', 'bybit', 'okx']
CHUNK_DAYS = 5 # 每次 API 抓取區間（天）
WAIT_TIME = 0.5 # 每次 API 呼叫間隔

def get_connection():
    """獲取資料庫連接"""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def get_latest_funding_rate_date():
    """獲取funding_rate_history表中最新記錄的日期"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(DATE(timestamp_utc)) as latest_date
            FROM funding_rate_history
        """)
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0]
        else:
            print("❌ funding_rate_history表為空")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 查詢funding_rate_history表時發生錯誤: {e}")
        sys.exit(1)

def process_date_input(date_input, date_type="start"):
    """處理日期輸入，支持up_to_date，並記錄日誌"""
    if date_input == "up_to_date":
        if date_type == "start":
            latest_date = get_latest_funding_rate_date()
            print(f"📅 自動設定開始日期: {latest_date} (來自funding_rate_history最新記錄)")
            return latest_date
        else:  # end
            utc_now = datetime.now(timezone.utc)
            yesterday = utc_now - timedelta(days=1)
            yesterday_str = yesterday.strftime('%Y-%m-%d')
            print(f"📅 自動設定結束日期: {yesterday_str} (UTC+0昨天)")
            return yesterday_str
    else:
        # 驗證日期格式
        try:
            datetime.fromisoformat(date_input)
            print(f"📅 使用指定日期: {date_input}")
            return date_input
        except ValueError:
            raise ValueError(f"無效的日期格式: {date_input}")

def validate_date_range(start_date_str, end_date_str, is_auto_mode=False):
    """
    驗證日期範圍的邏輯性
    
    Args:
        start_date_str: 開始日期字符串
        end_date_str: 結束日期字符串  
        is_auto_mode: 是否為自動模式（up_to_date）
    
    Returns:
        bool: 是否有效
    """
    start_dt = datetime.fromisoformat(start_date_str)
    end_dt = datetime.fromisoformat(end_date_str)
    
    if start_dt > end_dt:
        if is_auto_mode:
            print("❌ 自動模式檢測到異常：最新數據日期晚於昨天")
            print(f"   最新數據日期: {start_date_str}")
            print(f"   目標結束日期: {end_date_str}")
            print("💡 建議：檢查系統時間或數據庫中的時間戳是否正確")
        else:
            print("❌ 開始日期不能晚於結束日期")
        return False
    
    if start_dt == end_dt:
        if is_auto_mode:
            print("⚠️ 自動模式檢測：開始日期等於結束日期")
            print(f"   處理日期: {start_date_str}")
            print("💡 系統將嘗試獲取該日期的數據")
        else:
            print("⚠️ 開始日期等於結束日期，將只處理一天的數據")
    
    return True

async def get_target_pairs(conn, exchanges, top_n):
    """
    從資料庫中根據市值排名和交易所支援情況，篩選出目標交易對。
    返回一個任務列表，每個任務包含 symbol, exchange 和 list_date。
    
    Args:
        conn: 資料庫連接
        exchanges: 交易所列表
        top_n: 市值排名前N名，或 "all" 表示所有交易對
    """
    cursor = conn.cursor()
    tasks = []
    
    # 構建查詢語句
    # 我們需要動態地檢查每個請求的交易所是否被支援
    placeholders = ','.join('?' for _ in exchanges)
    
    # 根據 top_n 參數動態構建 WHERE 條件
    if top_n == "all":
        # 查詢所有交易對（有市值排名的和沒有市值排名的）
        query = f"""
            SELECT id, symbol, trading_pair, market_cap_rank, 
                   {', '.join([f'{ex}_support' for ex in exchanges])},
                   {', '.join([f'{ex}_list_date' for ex in exchanges])}
            FROM trading_pair
            ORDER BY CASE 
                WHEN market_cap_rank IS NOT NULL THEN market_cap_rank 
                ELSE 999999 
            END
        """
        cursor.execute(query)
    else:
        # 查詢市值排名前N名的交易對
        query = f"""
            SELECT id, symbol, trading_pair, market_cap_rank, 
                   {', '.join([f'{ex}_support' for ex in exchanges])},
                   {', '.join([f'{ex}_list_date' for ex in exchanges])}
            FROM trading_pair
            WHERE market_cap_rank IS NOT NULL AND market_cap_rank <= ?
            ORDER BY market_cap_rank
        """
        cursor.execute(query, (top_n,))
    
    rows = cursor.fetchall()
    
    for row in rows:
        for ex in exchanges:
            # 檢查該交易所是否支援此交易對
            if row[f'{ex}_support']:
                # 只處理支援的交易所
                if ex in SUPPORTED_EXCHANGES:
                    tasks.append({
                        "symbol": row['symbol'],
                        "trading_pair": row['trading_pair'], # e.g., BTCUSDT
                        "exchange": ex,
                        "list_date": row[f'{ex}_list_date']
                    })
    return tasks

async def save_funding_rates(conn, df, exchange, symbol):
    """將處理過的 DataFrame (含NULL) 的資金費率數據批量存入資料庫"""
    if df.empty:
        return 0

    to_insert = []
    for timestamp_utc, row in df.iterrows():
        # pandas.NaN 在這裡會被正確處理，sqlite3驅動會將其轉換為NULL
        funding_rate = row['funding_rate'] if pd.notna(row['funding_rate']) else None
        to_insert.append((
            timestamp_utc.to_pydatetime(),  # 從 pandas Timestamp 轉換為 python datetime
            symbol,
            exchange,
            funding_rate
        ))

    if not to_insert:
        return 0

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
        print(f"❌ 資料庫儲存時出錯 ({symbol}_{exchange}): {e}")
        conn.rollback()
        return 0

async def fetch_funding_rates_rest(session, exchange, symbol, trading_pair, start_dt, end_dt):
    """
    使用 aiohttp 直接請求 REST API，並加入重試機制
    V3 更新：修復 OKX 分頁邏輯，支持完整歷史數據獲取
    """
    all_data = []

    if exchange == 'okx':
        # OKX 特殊處理：反向分頁邏輯（從新到舊）
        url = "https://www.okx.com/api/v5/public/funding-rate-history"
        current_after = int(end_dt.timestamp() * 1000)  # 從結束時間開始（反向遍歷）
        start_timestamp_ms = int(start_dt.timestamp() * 1000)
        page_count = 0

        while True:
            params = {
                "instId": f"{symbol}-USDT-SWAP",
                "after": current_after,
                "limit": 100
            }

            # 重試邏輯
            batch_data = []
            for attempt in range(MAX_RETRIES):
                try:
                    async with session.get(url, params=params, timeout=20) as response:
                        response.raise_for_status()
                        data = await response.json()

                        if data.get("code") == "0":
                            batch_data = data.get("data", [])
                        break

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt < MAX_RETRIES - 1:
                        print(f"🟡 (OKX) {symbol} 請求失敗 (第 {attempt + 1}/{MAX_RETRIES} 次): {e}. 在 {RETRY_DELAY} 秒後重試...")
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        print(f"❌ (OKX) {symbol} 頁面 {page_count + 1} 請求錯誤: {e}")

            # 如果沒有數據了，退出
            if not batch_data:
                break

            page_count += 1

            # 過濾出在 start_dt 之後的數據
            valid_records = []
            oldest_in_batch = None

            for r in batch_data:
                funding_time_ms = int(r['fundingTime'])
                if funding_time_ms >= start_timestamp_ms:
                    valid_records.append(r)
                # 記錄這批數據中最早的時間
                if oldest_in_batch is None or funding_time_ms < oldest_in_batch:
                    oldest_in_batch = funding_time_ms

            # 添加有效數據
            all_data.extend(valid_records)

            # 檢查退出條件
            if oldest_in_batch and oldest_in_batch <= start_timestamp_ms:
                # 最早的數據已經早於或等於 start_dt，獲取完畢
                break

            # 更新 after 參數為這批數據中最早的 fundingTime
            if oldest_in_batch:
                current_after = oldest_in_batch
            else:
                # 沒有有效時間戳，退出
                break

            await asyncio.sleep(WAIT_TIME)

        print(f"   (OKX) {symbol}: 共獲取 {page_count} 頁，{len(all_data)} 條資金費率記錄")

    else:
        # Binance 和 Bybit 的原有邏輯（正向遍歷）
        current_dt = start_dt

        while current_dt < end_dt:
            fetch_end = min(current_dt + timedelta(days=CHUNK_DAYS), end_dt)
            params = {}
            url = ""

            if exchange == 'binance':
                url = "https://fapi.binance.com/fapi/v1/fundingRate"
                params.update({
                    "symbol": trading_pair,
                    "startTime": int(current_dt.timestamp() * 1000),
                    "endTime": int(fetch_end.timestamp() * 1000),
                    "limit": 1000
                })
            elif exchange == 'bybit':
                url = "https://api.bybit.com/v5/market/funding/history"
                params.update({
                    "symbol": trading_pair,
                    "category": "linear",
                    "startTime": int(current_dt.timestamp() * 1000),
                    "endTime": int(fetch_end.timestamp() * 1000),
                    "limit": 200
                })

            # 重試邏輯
            for attempt in range(MAX_RETRIES):
                try:
                    async with session.get(url, params=params, timeout=20) as response:
                        response.raise_for_status()
                        data = await response.json()

                        if exchange == 'binance':
                            all_data.extend(data)
                        elif exchange == 'bybit':
                            if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                                all_data.extend(data["result"]["list"])

                    break # 成功，跳出重試循環

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt < MAX_RETRIES - 1:
                        print(f"🟡 ({exchange.upper()}) {symbol} 請求失敗 (第 {attempt + 1}/{MAX_RETRIES} 次): {e}. 在 {RETRY_DELAY} 秒後重試...")
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        print(f"❌ ({exchange.upper()}) {symbol} {current_dt.strftime('%Y-%m-%d')} 請求錯誤: {e}")

            await asyncio.sleep(WAIT_TIME)
            current_dt = fetch_end

    return all_data

async def fetch_and_save_fr(session, task, start_date, end_date):
    symbol = task['symbol']
    exchange_id = task['exchange']
    trading_pair = task['trading_pair']

    # 1. 確定基準開始日期 (使用者輸入 vs 上市日期)
    actual_start_date = start_date
    list_date_dt = None
    if task['list_date']:
        list_date_dt = datetime.fromisoformat(task['list_date']).replace(tzinfo=timezone.utc)
        actual_start_date = max(start_date, list_date_dt)

        # 如果上市日期晚於用戶指定的結束日期，直接跳過
        if list_date_dt >= end_date:
            print(f"ℹ️ ({exchange_id.upper()}) {symbol}: 上市日期 ({list_date_dt.date()}) 晚於指定結束日期 ({(end_date - timedelta(days=1)).date()})，跳過。")
            return

    # 2. 智慧增量更新檢查：檢查用戶指定時間範圍內的數據完整性
    conn = get_connection()
    cursor = conn.cursor()
    
    # 檢查用戶指定時間範圍內是否有完整數據
    cursor.execute("""
        SELECT COUNT(DISTINCT DATE(timestamp_utc)) as existing_days
        FROM funding_rate_history 
        WHERE symbol = ? AND exchange = ? 
        AND DATE(timestamp_utc) BETWEEN DATE(?) AND DATE(?)
    """, (symbol, exchange_id, actual_start_date.date(), (end_date - timedelta(days=1)).date()))
    
    existing_days = cursor.fetchone()[0]
    expected_days = (end_date.date() - actual_start_date.date()).days
    
    # 如果指定時間範圍內的數據已經完整，則跳過
    if existing_days >= expected_days and expected_days > 0:
        print(f"✅ ({exchange_id.upper()}) {symbol}: 指定時間範圍 ({actual_start_date.date()} 到 {(end_date - timedelta(days=1)).date()}) 數據已完整，無需更新。")
        conn.close()
        return
    
    # 找到需要補充的時間範圍
    if existing_days > 0:
        # 找到資料庫中該時間範圍內的最新時間戳
        cursor.execute("""
            SELECT MAX(timestamp_utc) 
            FROM funding_rate_history 
            WHERE symbol = ? AND exchange = ? 
            AND DATE(timestamp_utc) BETWEEN DATE(?) AND DATE(?)
        """, (symbol, exchange_id, actual_start_date.date(), (end_date - timedelta(days=1)).date()))
        
        latest_in_range = cursor.fetchone()[0]
        if latest_in_range:
            latest_db_date = datetime.fromisoformat(latest_in_range).replace(tzinfo=timezone.utc)
            # 從最新時間的下一個小時開始抓取
            incremental_start_date = latest_db_date + timedelta(hours=1)
            actual_start_date = max(actual_start_date, incremental_start_date)
    
    conn.close()

    if actual_start_date >= end_date:
        print(f"✅ ({exchange_id.upper()}) {symbol}: 數據已是最新，無需更新。")
        return

    print(f"🚀 ({exchange_id.upper()}) 開始獲取 {symbol} 從 {actual_start_date.strftime('%Y-%m-%d %H:%M:%S')} 的數據...")

    api_rates = await fetch_funding_rates_rest(session, exchange_id, symbol, trading_pair, actual_start_date, end_date)

    # --- 新增邏輯：生成完整時間軸並合併 ---
    # pd.date_range 的結尾是包含的，但我們的 end_date 是開區間，所以減去一小時
    hourly_index = pd.date_range(start=actual_start_date, end=end_date - timedelta(hours=1), freq='h', tz='UTC')
    
    # 2. 將API返回的數據轉換為帶有時間索引的DataFrame，並對齊到整點小時
    api_df = None
    if api_rates:
        processed_rates = []
        for r in api_rates:
            try:
                rate_record = {}
                ts = None
                if exchange_id == 'binance':
                    ts = datetime.fromtimestamp(int(r['fundingTime']) / 1000, tz=timezone.utc)
                    rate_record['funding_rate'] = float(r['fundingRate'])
                elif exchange_id == 'bybit':
                    ts = datetime.fromtimestamp(int(r['fundingRateTimestamp']) / 1000, tz=timezone.utc)
                    rate_record['funding_rate'] = float(r['fundingRate'])
                elif exchange_id == 'okx':
                    ts = datetime.fromtimestamp(int(r['fundingTime']) / 1000, tz=timezone.utc)
                    rate_record['funding_rate'] = float(r['fundingRate'])
                
                if ts:
                    # 核心修正：將時間戳向下對齊到最近的整點小時
                    rate_record['timestamp_utc'] = ts.replace(minute=0, second=0, microsecond=0)
                    processed_rates.append(rate_record)

            except (KeyError, ValueError) as e:
                print(f"⚠️ ({exchange_id.upper()}) {symbol}: 解析API數據時跳過一筆記錄 - {e}")
        
        if processed_rates:
            # 將 list of dicts 轉為 DataFrame
            temp_df = pd.DataFrame(processed_rates)
            # 處理同一小時內可能有多筆數據的情況，我們只保留最後一筆，確保數據的唯一性
            api_df = temp_df.groupby('timestamp_utc').last()

    # 3. 以完整時間軸為基礎，合併API數據
    final_df = pd.DataFrame(index=hourly_index)
    final_df.index.name = 'timestamp_utc'
    if api_df is not None:
        final_df = final_df.join(api_df)

    # --- 邏輯結束 ---

    if not final_df.empty:
        conn = get_connection()
        inserted_count = await save_funding_rates(conn, final_df, exchange_id, symbol)
        conn.close()
        print(f"✅ ({exchange_id.upper()}) {symbol}: 成功處理 {inserted_count} 筆數據 (含NULL)。")
    else:
        print(f"ℹ️ ({exchange_id.upper()}) {symbol}: 在指定區間內未找到數據。")

async def main(exchanges=None, top_n=None, start_date=None, end_date=None):
    """
    主執行程序 - 支持命令行參數和交互式模式
    
    Args:
        exchanges: 交易所列表，None則交互式輸入
        top_n: 市值排名前N名，None則交互式輸入  
        start_date: 開始日期字符串，None則交互式輸入
        end_date: 結束日期字符串，None則交互式輸入
    """
    print("--- 資金費率歷史數據獲取工具 V3 ---")
    
    # 獲取交易所（命令行或交互式）
    if exchanges is None:
        # 交互式輸入
        exchanges = []
        while not exchanges:
            exchanges_input = input("請輸入要查詢的交易所, 用空格分隔 (例如: binance bybit okx): ").strip().lower()
            input_list = [ex.strip() for ex in exchanges_input.split() if ex.strip()]
            
            if not input_list:
                print("未輸入任何交易所，請重新輸入。")
                continue

            # 驗證所有輸入的交易所是否都有效
            invalid_exchanges = [ex for ex in input_list if ex not in SUPPORTED_EXCHANGES]
            
            if invalid_exchanges:
                print(f"❌ 錯誤：包含不支援或拼寫錯誤的交易所: {', '.join(invalid_exchanges)}")
                print(f"   目前支援的交易所為: {', '.join(SUPPORTED_EXCHANGES)}")
            else:
                exchanges = input_list # 全部有效，賦值並結束循環
    else:
        # 命令行模式 - 驗證交易所
        invalid_exchanges = [ex for ex in exchanges if ex not in SUPPORTED_EXCHANGES]
        if invalid_exchanges:
            print(f"❌ 不支持的交易所: {invalid_exchanges}")
            print(f"✅ 支持的交易所: {SUPPORTED_EXCHANGES}")
            return
        print(f"🎯 指定交易所: {exchanges}")

    # 獲取市值排名（命令行或交互式）
    if top_n is None:
        # 交互式輸入
        top_n = None
        while top_n is None:
            try:
                user_input = input("請輸入要查詢的市值排名前 N (例如: 500) 或輸入 'all' 查詢所有交易對: ").strip()
                if user_input.lower() == 'all':
                    top_n = "all"
                else:
                    top_n_int = int(user_input)
                    if top_n_int <= 0:
                        print("請輸入一個大於 0 的整數，或輸入 'all'。")
                        top_n = None
                    else:
                        top_n = top_n_int
            except ValueError:
                print("無效的輸入，請輸入一個數字或 'all'。")
    else:
        if top_n == "all":
            print("📊 市值排名: 所有交易對")
        else:
            print(f"📊 市值排名: 前 {top_n} 名")

    # 獲取開始日期（命令行或交互式）
    start_date_str = start_date
    if start_date_str is None:
        # 交互式輸入
        start_date_str = ""
        while not start_date_str:
            try:
                start_date_input = input("請輸入開始日期 (格式 YYYY-MM-DD) 或輸入 'up_to_date' 從最新數據開始: ").strip()
                start_date_str = process_date_input(start_date_input, "start")
                break
            except ValueError as e:
                print(f"❌ {e}")
                start_date_str = ""
    else:
        # 命令行模式 - 處理日期參數
        try:
            start_date_str = process_date_input(start_date_str, "start")
        except ValueError as e:
            print(f"❌ 開始日期處理錯誤: {e}")
            return
    
    # 獲取結束日期（命令行或交互式）
    end_date_str = end_date
    if end_date_str is None:
        # 交互式輸入
        end_date_str = ""
        while not end_date_str:
            try:
                end_date_input = input("請輸入結束日期 (格式 YYYY-MM-DD) 或輸入 'up_to_date' 更新到昨天: ").strip()
                end_date_str = process_date_input(end_date_input, "end")
                break
            except ValueError as e:
                print(f"❌ {e}")
                end_date_str = ""
    else:
        # 命令行模式 - 處理日期參數
        try:
            end_date_str = process_date_input(end_date_str, "end")
        except ValueError as e:
            print(f"❌ 結束日期處理錯誤: {e}")
            return
    
    # 檢查日期邏輯
    is_auto_mode = (start_date == "up_to_date" or end_date == "up_to_date")
    if not validate_date_range(start_date_str, end_date_str, is_auto_mode):
        print("❌ 日期範圍驗證失敗")
        return
            
    print("-------------------------------------\n")
    
    # 解析並設定時區
    start_date_dt = datetime.fromisoformat(start_date_str).replace(tzinfo=timezone.utc)
    # 修正：將結束日期視為包含當天。例如，輸入 2025-06-11，則抓取到 2025-06-11 23:00:00 的數據
    # 我們透過將日期加一天，並將其作為開區間的結束點來實現
    end_date_dt = datetime.fromisoformat(end_date_str).replace(tzinfo=timezone.utc) + timedelta(days=1)
    
    # 建立資料庫連線
    conn = get_connection()
    
    # 1. 獲取目標任務列表
    if top_n == "all":
        print(f"正在從資料庫查詢 所有支援 {', '.join(exchanges)} 的交易對...")
    else:
        print(f"正在從資料庫查詢 市值前 {top_n} 且支援 {', '.join(exchanges)} 的交易對...")
    tasks = await get_target_pairs(conn, exchanges, top_n)
    conn.close()
    
    if not tasks:
        print("未找到任何符合條件的任務，程式終止。")
        return
        
    print(f"找到 {len(tasks)} 個任務，準備開始獲取數據...")

    # --- 新增：併發控制器 ---
    # 設置一個Semaphore來限制同時運行的任務數量
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    async def run_with_semaphore(task_coro):
        async with semaphore:
            return await task_coro
    # --- 結束 ---

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        fetch_tasks = [run_with_semaphore(fetch_and_save_fr(session, task, start_date_dt, end_date_dt)) for task in tasks]
        await asyncio.gather(*fetch_tasks)

    print("\n🎉 所有任務執行完畢！")

def run_main():
    """包裝函數，處理命令行參數"""
    parser = argparse.ArgumentParser(
        description='資金費率歷史數據獲取工具 V3 - 批量獲取交易對資金費率（修復OKX分頁）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 交互式模式
  python fetch_FR_history_group_v3.py
  
  # 命令行模式 - 基本用法
  python fetch_FR_history_group_v3.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09

  # 命令行模式 - 單個交易所
  python fetch_FR_history_group_v3.py --exchanges binance --top_n 50 --start_date 2025-07-01 --end_date 2025-07-03

  # 命令行模式 - 所有支持的交易所（包含修復後的OKX）
  python fetch_FR_history_group_v3.py --exchanges binance bybit okx --top_n 200 --start_date 2025-07-01 --end_date 2025-07-09

  # 命令行模式 - 查詢所有交易對
  python fetch_FR_history_group_v3.py --exchanges binance --top_n all --start_date 2025-07-01 --end_date 2025-07-09

  # 命令行模式 - 使用up_to_date
  python fetch_FR_history_group_v3.py --exchanges binance --top_n 100 --start_date up_to_date --end_date up_to_date
        """
    )
    
    parser.add_argument('--exchanges', nargs='+',
                       choices=SUPPORTED_EXCHANGES,
                       help='指定要查詢的交易所（空格分隔），例如：binance bybit okx')
    
    parser.add_argument('--top_n', type=str,
                       help='市值排名前N名（例如：100）或輸入 "all" 查詢所有交易對')
    
    parser.add_argument('--start_date', type=str,
                       help='開始日期，格式：YYYY-MM-DD，例如：2025-07-01 或 up_to_date (從最新數據開始)')
    
    parser.add_argument('--end_date', type=str,
                       help='結束日期，格式：YYYY-MM-DD，例如：2025-07-09 或 up_to_date (更新到昨天)')
    
    args = parser.parse_args()
    
    # 檢查參數完整性
    cmd_params = [args.exchanges, args.top_n, args.start_date, args.end_date]
    has_any_param = any(param is not None for param in cmd_params)
    has_all_params = all(param is not None for param in cmd_params)
    
    if has_any_param and not has_all_params:
        print("❌ 命令行模式需要提供所有參數：--exchanges, --top_n, --start_date, --end_date")
        print("💡 或者不提供任何參數使用交互式模式")
        parser.print_help()
        return
    
    # 驗證參數
    if has_all_params:
        # 驗證 top_n 參數
        if args.top_n.lower() == 'all':
            top_n_validated = "all"
        else:
            try:
                top_n_int = int(args.top_n)
                if top_n_int <= 0:
                    print("❌ --top_n 參數必須是正整數或 'all'")
                    return
                top_n_validated = top_n_int
            except ValueError:
                print("❌ --top_n 參數必須是正整數或 'all'")
                return
        
        # 驗證日期參數
        try:
            start_date_validated = process_date_input(args.start_date, "start")
            end_date_validated = process_date_input(args.end_date, "end")
            
            # 檢查日期邏輯
            is_auto_mode = (args.start_date == "up_to_date" or args.end_date == "up_to_date")
            if not validate_date_range(start_date_validated, end_date_validated, is_auto_mode):
                print("❌ 日期範圍驗證失敗")
                return
        except ValueError as e:
            print(f"❌ 日期參數錯誤: {e}")
            return
    
    # 調用主函數
    if has_all_params:
        print("🚀 命令行模式")
        asyncio.run(main(
            exchanges=args.exchanges,
            top_n=top_n_validated,
            start_date=start_date_validated,
            end_date=end_date_validated
        ))
    else:
        print("🚀 交互式模式")
        asyncio.run(main())

if __name__ == "__main__":
    run_main()