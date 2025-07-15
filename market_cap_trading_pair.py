import sqlite3
import os
import argparse
from pycoingecko import CoinGeckoAPI
from datetime import datetime
import requests
import time
import math # 導入 math 模塊

DB_PATH = "data/funding_rate.db"

def get_connection():
    """獲取數據庫連接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_top_n_coins(n=200):
    """
    從 CoinGecko API 獲取市值排名前 N 的幣種數據，支持分頁。
    """
    print(f"正在從 CoinGecko API 獲取市值排名前 {n} 的幣種數據...")
    all_coins = []
    per_page = 250  # CoinGecko API 每頁最多 250 筆
    total_pages = math.ceil(n / per_page)
    
    for page in range(1, total_pages + 1):
        remaining = n - len(all_coins)
        current_per_page = min(per_page, remaining)
        
        if current_per_page <= 0:
            break

        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': current_per_page,
            'page': page,
            'sparkline': False
        }
        
        try:
            # 添加延遲以避免被 API 限制
            if page > 1:
                time.sleep(1) # 短暫延遲
            
            print(f"正在請求第 {page}/{total_pages} 頁，獲取 {current_per_page} 筆數據...")
            response = requests.get(url, params=params)
            response.raise_for_status()  # 如果請求失敗則拋出異常
            data = response.json()

            if not data:
                print(f"✅ 第 {page} 頁無數據，查詢結束。")
                break

            all_coins.extend(data)
            print(f"✅ 成功獲取 {len(data)} 筆數據。目前總數: {len(all_coins)}")

        except requests.exceptions.RequestException as e:
            print(f"❌ API 請求失敗: {e}")
            return None # 返回 None 表示失敗
    
    return all_coins[:n] # 確保最終返回的數量不超過 N

def clear_market_cap_data(conn):
    """清空所有現有交易對的市值相關數據"""
    print("正在清空舊的市值排名數據...")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE trading_pair 
            SET 
                market_cap = NULL,
                market_cap_rank = NULL,
                total_volume = NULL,
                updated_at = ?
        """, (datetime.now().isoformat(),))
        print(f"✅ {cursor.rowcount} 筆記錄的市值數據已被清空。")
        conn.commit()
    except sqlite3.Error as e:
        print(f"❌ 清空市值數據時發生資料庫錯誤: {e}")
        conn.rollback()

def upsert_coin_data(conn, coin):
    """更新或插入新的幣種數據 (Upsert)"""
    cursor = conn.cursor()
    symbol = coin.get('symbol', '').upper()
    trading_pair = f"{symbol}USDT"
    now = datetime.now().isoformat()

    try:
        # 查找現有記錄
        cursor.execute("SELECT id FROM trading_pair WHERE symbol = ?", (symbol,))
        existing_record = cursor.fetchone()

        if existing_record:
            # 更新現有記錄
            cursor.execute("""
                UPDATE trading_pair
                SET 
                    market_cap = ?,
                    market_cap_rank = ?,
                    total_volume = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                coin.get('market_cap'),
                coin.get('market_cap_rank'),
                coin.get('total_volume'),
                now,
                existing_record['id']
            ))
        else:
            # 插入新記錄
            cursor.execute("""
                INSERT INTO trading_pair (
                    symbol, trading_pair, market_cap, market_cap_rank, total_volume, 
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                trading_pair,
                coin.get('market_cap'),
                coin.get('market_cap_rank'),
                coin.get('total_volume'),
                now,
                now
            ))
        return True
    except sqlite3.Error as e:
        print(f"❌ 更新/插入 Symbol: {symbol} 時發生資料庫錯誤: {e}")
        return False

def main(top_n=None):
    """
    主執行程序
    
    Args:
        top_n: 市值排名前N名，None則交互式輸入
    """
    print("市值與交易對更新腳本開始執行...")
    
    # 獲取 top_n 參數
    if top_n is None:
        # 交互式輸入
        while True:
            try:
                top_n_str = input("請輸入您想獲取的市值排名前 N 大的幣種數量 (例如: 500): ")
                top_n = int(top_n_str)
                if top_n > 0:
                    break
                else:
                    print("請輸入一個大於 0 的正整數。")
            except ValueError:
                print("無效的輸入，請輸入一個數字。")
    else:
        # 命令行模式 - 驗證參數
        if not isinstance(top_n, int) or top_n <= 0:
            print("❌ top_n 必須是大於 0 的正整數")
            return False
        print(f"🎯 使用指定的市值排名: 前{top_n}名")

    # 獲取 API 數據
    coins_data = fetch_top_n_coins(top_n)
    
    if not coins_data:
        print("無法從 API 獲取數據，腳本終止。")
        return False

    # 連接資料庫
    conn = get_connection()
    
    # 清空舊排名
    clear_market_cap_data(conn)
    
    # 更新/插入新數據
    success_count = 0
    failure_count = 0
    print(f"開始處理 {len(coins_data)} 筆幣種數據...")
    for coin in coins_data:
        if upsert_coin_data(conn, coin):
            success_count += 1
        else:
            failure_count += 1
    
    # 提交事務並關閉連線
    conn.commit()
    conn.close()
    
    print("\n----- 更新完成 -----")
    print(f"總共處理了 {len(coins_data)} 筆從 API 獲取的數據。")
    print(f"✅ 成功更新/插入: {success_count} 筆")
    print(f"❌ 失敗: {failure_count} 筆")
    print("腳本執行完畢。")
    
    return success_count > 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='市值與交易對更新腳本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用範例:
  python market_cap_trading_pair.py --top_n 500
  python market_cap_trading_pair.py --top_n 1000
        '''
    )
    
    parser.add_argument('--top_n', type=int, help='市值排名前N名 (必須為正整數)')
    
    args = parser.parse_args()
    
    if args.top_n:
        # 命令行模式
        success = main(args.top_n)
        if not success:
            exit(1)
    else:
        # 交互式模式
        main() 