#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整套利收益分析工具 v1.0
整合幣安和Bybit的資金費用、手續費、保證金數據
支援增量計算和歷史數據處理
"""

import hashlib
import hmac
import time
import os
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd
import json
import argparse
from urllib.parse import urlencode


class BinanceDataCollector:
    """幣安數據收集器"""
    
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = 'https://fapi.binance.com'

    def _generate_signature(self, query_string):
        """生成API簽名"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, endpoint, params=None):
        """發送API請求"""
        if params is None:
            params = {}

        params['timestamp'] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = self._generate_signature(query_string)
        params['signature'] = signature

        headers = {'X-MBX-APIKEY': self.api_key}
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Binance API錯誤: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Binance API異常: {str(e)}")
            return None

    def get_funding_fee_history(self, start_date, end_date):
        """獲取資金費用歷史"""
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp() * 1000)

        params = {
            'startTime': start_ts,
            'endTime': end_ts,
            'incomeType': 'FUNDING_FEE',
            'limit': 1000
        }

        result = self._make_request('/fapi/v1/income', params)
        return result if result else []

    def get_trading_fee_history(self, start_date, end_date):
        """獲取手續費歷史"""
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp() * 1000)

        params = {
            'startTime': start_ts,
            'endTime': end_ts,
            'incomeType': 'COMMISSION',
            'limit': 1000
        }

        result = self._make_request('/fapi/v1/income', params)
        return result if result else []

    def get_current_positions(self):
        """獲取當前持倉保證金"""
        result = self._make_request('/fapi/v2/positionRisk')
        
        if result:
            positions = {}
            for pos in result:
                symbol = pos['symbol']
                position_amt = float(pos['positionAmt'])
                
                if position_amt != 0:
                    # 使用正確的初始保證金計算：名義價值 / 槓桿倍數
                    notional = float(pos['notional'])
                    leverage = float(pos['leverage'])
                    initial_margin = abs(notional) / leverage if leverage > 0 else 0
                    positions[symbol] = initial_margin
                    
            return positions
        return {}


class BybitDataCollector:
    """Bybit數據收集器"""
    
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = 'https://api.bybit.com'

    def generate_signature(self, params: dict) -> str:
        """生成簽名"""
        sorted_params = sorted(params.items())
        query_string = '&'.join(f"{key}={value}" for key, value in sorted_params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, endpoint, params=None):
        """發送請求"""
        if params is None:
            params = {}

        url = self.base_url + endpoint
        timestamp = int(time.time() * 1000)

        params.update({
            "api_key": self.api_key,
            "timestamp": str(timestamp),
        })

        sign = self.generate_signature(params)
        params["sign"] = sign

        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data["retCode"] == 0:
                    return data["result"]
                else:
                    print(f"Bybit API錯誤: {data['retMsg']}")
                    return None
            else:
                print(f"Bybit HTTP錯誤: {response.status_code}")
                return None
        except Exception as e:
            print(f"Bybit API異常: {str(e)}")
            return None

    def get_funding_fee_history(self, start_date, end_date):
        """獲取資金費用歷史"""
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        all_records = []
        current_dt = start_dt

        while current_dt <= end_dt:
            # Bybit API限制：時間範圍不能超過7天，使用1天批次確保數據完整
            batch_end_dt = current_dt  # 改為逐日查詢

            start_ts = int(current_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            end_ts = int((batch_end_dt + timedelta(days=1) - timedelta(seconds=1)).replace(tzinfo=timezone.utc).timestamp() * 1000)

            # 使用分頁查詢獲取所有記錄
            cursor = None
            page_num = 1
            batch_records = []

            print(f"   Bybit查詢: {current_dt.strftime('%Y-%m-%d')}")

            while True:
                params = {
                    "accountType": "UNIFIED",
                    "type": "SETTLEMENT",
                    "limit": "200",  # 增加單頁限制
                    "startTime": str(start_ts),
                    "endTime": str(end_ts)
                }

                if cursor:
                    params["cursor"] = cursor

                result = self._make_request("/v5/account/transaction-log", params)

                if result and 'list' in result:
                    page_records = result['list']
                    batch_records.extend(page_records)
                    
                    # 檢查是否還有更多頁面
                    next_cursor = result.get('nextPageCursor')
                    if next_cursor and len(page_records) > 0:
                        cursor = next_cursor
                        page_num += 1
                        print(f"   正在查詢第{page_num}頁...")
                        time.sleep(0.5)  # 分頁間隔
                    else:
                        break
                else:
                    break

            if batch_records:
                all_records.extend(batch_records)
                print(f"   找到 {len(batch_records)} 筆記錄")
            else:
                print(f"   該日期無記錄")

            current_dt += timedelta(days=1)
            time.sleep(1)

        print(f"   Bybit總計: {len(all_records)} 筆資金費用記錄")
        return all_records

    def get_trading_fee_history(self, start_date, end_date):
        """獲取手續費歷史"""
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        all_records = []
        current_dt = start_dt

        while current_dt <= end_dt:
            # 使用1天批次確保數據完整
            batch_end_dt = current_dt

            start_ts = int(current_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            end_ts = int((batch_end_dt + timedelta(days=1) - timedelta(seconds=1)).replace(tzinfo=timezone.utc).timestamp() * 1000)

            # 使用分頁查詢獲取所有記錄
            cursor = None
            page_num = 1
            batch_records = []

            print(f"   Bybit手續費查詢: {current_dt.strftime('%Y-%m-%d')}")

            while True:
                params = {
                    "accountType": "UNIFIED",
                    "type": "TRADE", 
                    "limit": "200",  # 增加單頁限制
                    "startTime": str(start_ts),
                    "endTime": str(end_ts)
                }

                if cursor:
                    params["cursor"] = cursor

                result = self._make_request("/v5/account/transaction-log", params)

                if result and 'list' in result:
                    page_records = result['list']
                    trade_records = [r for r in page_records if float(r.get('fee', 0)) > 0]
                    batch_records.extend(trade_records)
                    
                    # 檢查是否還有更多頁面
                    next_cursor = result.get('nextPageCursor')
                    if next_cursor and len(page_records) > 0:
                        cursor = next_cursor
                        page_num += 1
                        print(f"   正在查詢第{page_num}頁...")
                        time.sleep(0.5)  # 分頁間隔
                    else:
                        break
                else:
                    break

            if batch_records:
                all_records.extend(batch_records)
                print(f"   找到 {len(batch_records)} 筆手續費記錄")
            else:
                print(f"   該日期無手續費記錄")

            current_dt += timedelta(days=1)
            time.sleep(1)

        print(f"   Bybit手續費總計: {len(all_records)} 筆記錄")
        return all_records

    def get_current_positions(self):
        """獲取當前持倉"""
        params = {
            "category": "linear",
            "settleCoin": "USDT"
        }
        result = self._make_request("/v5/position/list", params)
        
        if result and 'list' in result:
            positions = {}
            for pos in result['list']:
                symbol = pos['symbol']
                size = float(pos.get('size', 0))
                
                if size > 0:
                    # 使用API提供的初始保證金
                    position_im = float(pos.get('positionIM', 0))
                    if position_im > 0:
                        positions[symbol] = position_im
                    else:
                        # 備用方案：計算初始保證金
                        position_value = float(pos.get('positionValue', 0))
                        leverage = float(pos.get('leverage', 1))
                        calc_margin = abs(position_value) / leverage if leverage > 0 else 0
                        positions[symbol] = calc_margin
                    
            return positions
        return {}


class ArbitrageAnalyzer:
    """套利分析器"""
    
    def __init__(self, binance_api_key, binance_secret, bybit_api_key, bybit_secret):
        self.binance = BinanceDataCollector(binance_api_key, binance_secret)
        self.bybit = BybitDataCollector(bybit_api_key, bybit_secret)
        
        self.margin_history_file = "csv/Return/margin_history.json"
        self.margin_history_csv = "csv/Return/margin_history.csv"
        self.margin_history = self.load_margin_history()
        
    def load_margin_history(self):
        """載入歷史保證金"""
        try:
            if os.path.exists(self.margin_history_file):
                with open(self.margin_history_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def save_margin_history(self):
        """保存歷史保證金到JSON"""
        os.makedirs(os.path.dirname(self.margin_history_file), exist_ok=True)
        with open(self.margin_history_file, 'w') as f:
            json.dump(self.margin_history, f, indent=2)
    
    def save_margin_to_csv(self, binance_positions, bybit_positions, timestamp_str):
        """保存保證金數據到CSV"""
        os.makedirs(os.path.dirname(self.margin_history_csv), exist_ok=True)
        
        # 準備CSV數據
        csv_data = []
        
        # 添加幣安數據
        for symbol, margin in binance_positions.items():
            csv_data.append({
                'Timestamp': timestamp_str,
                'Exchange': 'Binance',
                'Symbol': symbol,
                'Position_Margin': margin,
                'Source': 'current_api_call'
            })
        
        # 添加Bybit數據
        for symbol, margin in bybit_positions.items():
            csv_data.append({
                'Timestamp': timestamp_str,
                'Exchange': 'Bybit',
                'Symbol': symbol,
                'Position_Margin': margin,
                'Source': 'current_api_call'
            })
        
        # 創建DataFrame
        new_df = pd.DataFrame(csv_data)
        
        # 如果CSV文件已存在，追加數據
        if os.path.exists(self.margin_history_csv):
            existing_df = pd.read_csv(self.margin_history_csv)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df
        
        # 保存到CSV
        combined_df.to_csv(self.margin_history_csv, index=False)
        print(f"💾 保證金數據已保存到 {self.margin_history_csv}")
    
    def update_current_margin_data(self):
        """更新當前保證金數據"""
        print("📊 獲取當前保證金數據...")
        
        # 獲取當前保證金
        binance_positions = self.binance.get_current_positions()
        bybit_positions = self.bybit.get_current_positions()
        
        # 生成時間戳（精確到秒，UTC+0）
        timestamp_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # 保存到JSON（保持原格式兼容）
        self.margin_history[date_str] = {
            'binance': binance_positions,
            'bybit': bybit_positions,
            'source': 'current_api_call',
            'timestamp': timestamp_str
        }
        self.save_margin_history()
        
        # 保存到CSV
        self.save_margin_to_csv(binance_positions, bybit_positions, timestamp_str)
        
        print(f"✅ 保證金數據已更新: {timestamp_str}")
    
    def get_latest_margin_from_csv(self, date_str):
        """從CSV中獲取指定日期的最新保證金數據"""
        if not os.path.exists(self.margin_history_csv):
            return {}, {}, 'no_margin_data'
        
        try:
            df = pd.read_csv(self.margin_history_csv)
            
            # 篩選指定日期的數據
            df['Date'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m-%d')
            date_df = df[df['Date'] == date_str]
            
            if date_df.empty:
                return {}, {}, 'no_margin_data'
            
            # 轉換時間戳為datetime對象進行正確比較
            date_df['Timestamp_dt'] = pd.to_datetime(date_df['Timestamp'])
            latest_timestamp_dt = date_df['Timestamp_dt'].max()
            latest_df = date_df[date_df['Timestamp_dt'] == latest_timestamp_dt]
            
            # 分離幣安和Bybit數據
            binance_data = latest_df[latest_df['Exchange'] == 'Binance']
            bybit_data = latest_df[latest_df['Exchange'] == 'Bybit']
            
            binance_positions = dict(zip(binance_data['Symbol'], binance_data['Position_Margin']))
            bybit_positions = dict(zip(bybit_data['Symbol'], bybit_data['Position_Margin']))
            
            # 使用原始時間戳字符串
            latest_timestamp_str = latest_df['Timestamp'].iloc[0]
            
            return binance_positions, bybit_positions, f'csv_data_{latest_timestamp_str}'
            
        except Exception as e:
            print(f"⚠️ 讀取CSV保證金數據時出錯: {e}")
            return {}, {}, 'csv_read_error'
    
    def get_margin_for_date(self, date_str, force_update=False):
        """獲取指定日期保證金（統一從歷史記錄中取最新時間的數據）"""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # 如果是今天且需要更新，則先獲取當前數據
        if date_str == today and force_update:
            self.update_current_margin_data()
        
        # 從CSV中讀取該日期的最新保證金數據
        return self.get_latest_margin_from_csv(date_str)

    def analyze_data(self, start_date, end_date):
        """分析數據"""
        print(f"開始分析 {start_date} 到 {end_date} 的數據...")
        
        # 獲取數據
        print("獲取幣安資金費用...")
        binance_funding = self.binance.get_funding_fee_history(start_date, end_date)
        print("獲取幣安手續費...")
        binance_trading = self.binance.get_trading_fee_history(start_date, end_date)
        print("獲取Bybit資金費用...")
        bybit_funding = self.bybit.get_funding_fee_history(start_date, end_date)
        print("獲取Bybit手續費...")
        bybit_trading = self.bybit.get_trading_fee_history(start_date, end_date)
        
        # 準備輸出
        overall_records = []
        binance_records = []
        bybit_records = []
        
        # 生成日期範圍
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        date_range = pd.date_range(start=start_dt, end=end_dt, freq='D')
        
        # 獲取所有交易對
        all_symbols = set()
        
        for fee in binance_funding + binance_trading:
            all_symbols.add(fee['symbol'])
        
        for fee in bybit_funding + bybit_trading:
            all_symbols.add(fee['symbol'])
        
        print(f"找到 {len(all_symbols)} 個交易對")
        
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # 如果分析範圍包含今天，先更新當日保證金數據
        if today in [date.strftime('%Y-%m-%d') for date in date_range]:
            print("🔄 檢測到分析範圍包含今天，先更新當日保證金數據...")
            self.update_current_margin_data()
        
        for date in date_range:
            date_str = date.strftime('%Y-%m-%d')
            
            print(f"處理日期: {date_str}")
            
            # 獲取保證金（統一從歷史記錄中取最新時間的數據）
            binance_margins, bybit_margins, margin_source = self.get_margin_for_date(date_str, force_update=False)
            
            for symbol in all_symbols:
                # 計算幣安數據
                binance_ff = sum(float(f['income']) for f in binance_funding 
                               if f['symbol'] == symbol and 
                               datetime.fromtimestamp(f['time']/1000, tz=timezone.utc).strftime('%Y-%m-%d') == date_str)
                
                binance_tf = sum(float(f['income']) for f in binance_trading 
                               if f['symbol'] == symbol and 
                               datetime.fromtimestamp(f['time']/1000, tz=timezone.utc).strftime('%Y-%m-%d') == date_str)
                
                # 計算Bybit數據
                bybit_ff = sum(float(f['funding']) for f in bybit_funding 
                             if f['symbol'] == symbol and 
                             datetime.fromtimestamp(int(f['transactionTime'])/1000, tz=timezone.utc).strftime('%Y-%m-%d') == date_str)
                
                bybit_tf = sum(-float(f['fee']) for f in bybit_trading 
                             if f['symbol'] == symbol and 
                             datetime.fromtimestamp(int(f['transactionTime'])/1000, tz=timezone.utc).strftime('%Y-%m-%d') == date_str)
                
                # 獲取保證金
                binance_margin = binance_margins.get(symbol)
                bybit_margin = bybit_margins.get(symbol)
                
                # 計算指標
                net_pnl = binance_ff + bybit_ff + binance_tf + bybit_tf
                total_margin = None
                daily_return = None
                roi = None
                
                if binance_margin is not None and bybit_margin is not None:
                    total_margin = binance_margin + bybit_margin
                    if total_margin > 0:
                        daily_return = net_pnl / total_margin
                        roi = daily_return * 365
                
                # 記錄數據（只有活動時才記錄）
                if (binance_ff != 0 or bybit_ff != 0 or binance_tf != 0 or bybit_tf != 0 or
                    binance_margin is not None or bybit_margin is not None):
                    
                    overall_records.append({
                        'Date': date_str,
                        'Symbol': symbol,
                        'Binance FF': binance_ff,
                        'Bybit FF': bybit_ff,
                        'Binance TF': binance_tf,
                        'Bybit TF': bybit_tf,
                        'Net P&L': net_pnl,
                        'Binance M': binance_margin if binance_margin is not None else 'null',
                        'Bybit M': bybit_margin if bybit_margin is not None else 'null',
                        'Total M': total_margin if total_margin is not None else 'null',
                        'Return': daily_return if daily_return is not None else 'null',
                        'ROI': roi if roi is not None else 'null'
                    })
                    
                    if binance_ff != 0 or binance_tf != 0 or binance_margin is not None:
                        binance_records.append({
                            'Date': date_str,
                            'Symbol': symbol,
                            'Funding_Fee': binance_ff,
                            'Trading_Fee': binance_tf,
                            'Position_Margin': binance_margin if binance_margin is not None else 'null',
                            'API_Source': margin_source if binance_margin is not None else 'no_margin_data'
                        })
                    
                    if bybit_ff != 0 or bybit_tf != 0 or bybit_margin is not None:
                        bybit_records.append({
                            'Date': date_str,
                            'Symbol': symbol,
                            'Funding_Fee': bybit_ff,
                            'Trading_Fee': bybit_tf,
                            'Position_Margin': bybit_margin if bybit_margin is not None else 'null',
                            'API_Source': margin_source if bybit_margin is not None else 'no_margin_data'
                        })
        
        return pd.DataFrame(overall_records), pd.DataFrame(binance_records), pd.DataFrame(bybit_records)

    def save_results(self, overall_df, binance_df, bybit_df, start_date, end_date):
        """保存結果"""
        output_dir = "csv/Return"
        os.makedirs(output_dir, exist_ok=True)
        
        start_formatted = start_date.replace('-', '_')
        end_formatted = end_date.replace('-', '_')
        
        if start_date == end_date:
            suffix = start_formatted
        else:
            suffix = f"{start_formatted}_to_{end_formatted}"
        
        overall_file = f"{output_dir}/overall_stat_{suffix}.csv"
        binance_file = f"{output_dir}/binance_stat_{suffix}.csv"
        bybit_file = f"{output_dir}/bybit_stat_{suffix}.csv"
        
        overall_df.to_csv(overall_file, index=False)
        binance_df.to_csv(binance_file, index=False)
        bybit_df.to_csv(bybit_file, index=False)
        
        print(f"\n✅ 結果已保存:")
        print(f"   {overall_file}")
        print(f"   {binance_file}")
        print(f"   {bybit_file}")


def get_user_input_dates():
    """獲取用戶輸入的日期"""
    print("🔍 套利收益分析工具")
    print("=" * 40)
    
    # 顯示常用日期選項
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)
    
    print("\n📅 常用日期選項:")
    print(f"   1. 今日: {today.strftime('%Y-%m-%d')}")
    print(f"   2. 昨日: {yesterday.strftime('%Y-%m-%d')}")
    print(f"   3. 最近7天: {last_week.strftime('%Y-%m-%d')} 至 {yesterday.strftime('%Y-%m-%d')}")
    print(f"   4. 最近30天: {last_month.strftime('%Y-%m-%d')} 至 {yesterday.strftime('%Y-%m-%d')}")
    print(f"   5. 自定義日期範圍")
    print()
    
    while True:
        try:
            choice = input("請選擇選項 (1-5) 或直接輸入開始日期 (YYYY-MM-DD): ").strip()
            
            if choice == '1':
                # 今日
                start_date = today.strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
                break
            elif choice == '2':
                # 昨日
                start_date = yesterday.strftime('%Y-%m-%d')
                end_date = yesterday.strftime('%Y-%m-%d')
                break
            elif choice == '3':
                # 最近7天
                start_date = last_week.strftime('%Y-%m-%d')
                end_date = yesterday.strftime('%Y-%m-%d')
                break
            elif choice == '4':
                # 最近30天
                start_date = last_month.strftime('%Y-%m-%d')
                end_date = yesterday.strftime('%Y-%m-%d')
                break
            elif choice == '5':
                # 自定義日期範圍
                start_date = input("請輸入開始日期 (YYYY-MM-DD): ").strip()
                datetime.strptime(start_date, '%Y-%m-%d')  # 驗證格式
                
                end_date = input("請輸入結束日期 (YYYY-MM-DD): ").strip()
                datetime.strptime(end_date, '%Y-%m-%d')  # 驗證格式
                break
            else:
                # 嘗試解析為日期
                start_date = choice
                datetime.strptime(start_date, '%Y-%m-%d')
                
                end_date = input("請輸入結束日期 (YYYY-MM-DD): ").strip()
                datetime.strptime(end_date, '%Y-%m-%d')
                break
                
        except ValueError:
            print("❌ 輸入格式錯誤，請重新輸入")
        except KeyboardInterrupt:
            print("\n\n👋 已取消操作")
            exit(0)
    
    # 驗證日期邏輯
    if start_date > end_date:
        print("❌ 開始日期不能晚於結束日期")
        return get_user_input_dates()
    
    return start_date, end_date

def main():
    parser = argparse.ArgumentParser(description='套利收益分析工具')
    parser.add_argument('--start', help='開始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', help='結束日期 (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # 如果沒有提供命令行參數，則提示用戶輸入
    if not args.start or not args.end:
        start_date, end_date = get_user_input_dates()
    else:
        start_date = args.start
        end_date = args.end
    
    # 載入API配置
    try:
        from api_config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BYBIT_API_KEY, BYBIT_SECRET_KEY
    except ImportError:
        print("❌ 請創建 api_config.py 並設定API金鑰")
        print("範例內容:")
        print("BINANCE_API_KEY = 'your_binance_api_key'")
        print("BINANCE_SECRET_KEY = 'your_binance_secret_key'")
        print("BYBIT_API_KEY = 'your_bybit_api_key'")
        print("BYBIT_SECRET_KEY = 'your_bybit_secret_key'")
        return
    
    print(f"\n📅 分析期間: {start_date} 至 {end_date}")
    print("🚀 開始分析...")
    
    analyzer = ArbitrageAnalyzer(BINANCE_API_KEY, BINANCE_SECRET_KEY, BYBIT_API_KEY, BYBIT_SECRET_KEY)
    
    try:
        overall_df, binance_df, bybit_df = analyzer.analyze_data(start_date, end_date)
        analyzer.save_results(overall_df, binance_df, bybit_df, start_date, end_date)
        
        print(f"\n📊 統計資訊:")
        print(f"   總記錄數: {len(overall_df)}")
        print(f"   處理日期數: {len(overall_df['Date'].unique()) if not overall_df.empty else 0}")
        print(f"   涉及交易對: {len(overall_df['Symbol'].unique()) if not overall_df.empty else 0}")
        
        if not overall_df.empty:
            total_net_pnl = overall_df['Net P&L'].sum()
            print(f"   總淨損益: ${total_net_pnl:.2f}")
            
            # 計算有效收益率記錄（排除null值）
            valid_returns = overall_df['Return'][overall_df['Return'] != 'null'].dropna()
            if len(valid_returns) > 0:
                # 轉換為數值類型
                valid_returns = pd.to_numeric(valid_returns, errors='coerce')
                valid_returns = valid_returns.dropna()
                
                if len(valid_returns) > 0:
                    avg_return = valid_returns.mean()
                    print(f"   平均日收益率: {avg_return*100:.4f}%")
                    print(f"   平均年化收益率: {avg_return*365*100:.2f}%")
                else:
                    print("   平均收益率: 無有效數據")
            else:
                print("   平均收益率: 無保證金數據")
            
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 