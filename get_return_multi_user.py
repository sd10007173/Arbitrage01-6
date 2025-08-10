#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多用戶套利收益分析工具 v1.0
基於 get_return_v2.py 修改，支援讀取不同用戶的環境檔案
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
from dotenv import load_dotenv
import sys


class TelegramNotifier:
    """Telegram通知器"""
    
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, message):
        """發送消息到Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=30)
            if response.status_code == 200:
                print(f"✅ Telegram通知已發送")
                return True
            else:
                print(f"❌ Telegram發送失敗: {response.status_code}")
                print(f"回應內容: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Telegram通知異常: {str(e)}")
            return False

    def send_start_notification(self, date_str, user_name=None):
        """發送開始執行通知"""
        user_info = f" - 用戶: {user_name}" if user_name else ""
        message = f"""🚀 <b>套利收益分析開始</b>{user_info}
📅 分析日期: {date_str}
⏰ 開始時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

正在獲取數據中..."""
        self.send_message(message)

    def format_amount(self, amount):
        """格式化金額：小數太小時無條件進位到小數點後2位"""
        import math
        if abs(amount) < 0.01 and amount != 0:
            # 對於小於0.01的非零數字，無條件進位到小數點後2位
            return f"{math.ceil(abs(amount) * 100) / 100:.2f}" if amount > 0 else f"-{math.ceil(abs(amount) * 100) / 100:.2f}"
        else:
            return f"{amount:.2f}"

    def send_success_notification(self, date_str, total_pnl, symbol_count, avg_return=None, binance_pnl=None, bybit_pnl=None, symbol_details=None, total_margin=None, roi=None, user_name=None):
        """發送成功完成通知"""
        user_info = f" [{user_name}]" if user_name else ""
        message = f"""<b>套利收益統計{user_info}：</b>
• 日期: {date_str}
• 交易對: {symbol_count}"""
        
        if binance_pnl is not None and bybit_pnl is not None:
            message += f"""
• Binance收益: ${self.format_amount(binance_pnl)}
• Bybit收益: ${self.format_amount(bybit_pnl)}"""
        
        # 添加總倉位保證金
        if total_margin is not None and total_margin != 'null':
            message += f"""
• 總倉位保證金: ${self.format_amount(total_margin)}"""
        
        # 添加等效年化
        if roi is not None and roi != 'null':
            message += f"""
• 等效年化: {roi*100:.2f}%"""
        
        message += f"""
• 淨收益: ${self.format_amount(total_pnl)}"""
        
        # 添加倉位總覽
        if symbol_details:
            message += f"""
• 倉位總覽:"""
            for symbol, pnl in symbol_details.items():
                message += f"""
   • {symbol} 淨收益: ${self.format_amount(pnl)}"""
        
        self.send_message(message)

    def send_error_notification(self, date_str, error_msg, user_name=None):
        """發送錯誤通知"""
        user_info = f" - 用戶: {user_name}" if user_name else ""
        message = f"""❌ <b>套利收益分析失敗</b>{user_info}
📅 分析日期: {date_str}
━━━━━━━━━━━━━━━━━━━━
🔍 錯誤信息: {error_msg}
⏰ 發生時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

請檢查程式和API連接狀態"""
        self.send_message(message)


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
    
    def __init__(self, binance_api_key, binance_secret, bybit_api_key, bybit_secret, user_name=None):
        self.binance = BinanceDataCollector(binance_api_key, binance_secret)
        self.bybit = BybitDataCollector(bybit_api_key, bybit_secret)
        self.user_name = user_name
        
        # 根據用戶名設定輸出目錄
        if user_name:
            self.output_base_dir = f"csv/Return_{user_name}"
            self.margin_history_file = f"{self.output_base_dir}/margin_history.json"
            self.margin_history_csv = f"{self.output_base_dir}/margin_history.csv"
        else:
            self.output_base_dir = "csv/Return"
            self.margin_history_file = f"{self.output_base_dir}/margin_history.json"
            self.margin_history_csv = f"{self.output_base_dir}/margin_history.csv"
        
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
        if self.user_name:
            print(f"用戶: {self.user_name}")
        
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
        output_dir = self.output_base_dir
        os.makedirs(output_dir, exist_ok=True)
        
        start_formatted = start_date.replace('-', '_')
        end_formatted = end_date.replace('-', '_')
        
        if start_date == end_date:
            suffix = start_formatted
        else:
            suffix = f"{start_formatted}_to_{end_formatted}"
        
        # 新命名規則
        total_detail_file = f"{output_dir}/Total_detail_{suffix}.csv"
        binance_detail_file = f"{output_dir}/binance_detail_{suffix}.csv"
        bybit_detail_file = f"{output_dir}/bybit_detail_{suffix}.csv"
        total_daily_file = f"{output_dir}/Total_daily_{suffix}.csv"
        
        # 保存明細檔案
        overall_df.to_csv(total_detail_file, index=False)
        binance_df.to_csv(binance_detail_file, index=False)
        bybit_df.to_csv(bybit_detail_file, index=False)
        
        # 生成 Total_daily 檔案
        daily_df = self.generate_total_daily(overall_df)
        daily_df.to_csv(total_daily_file, index=False)
        
        print(f"\n✅ 結果已保存:")
        print(f"   {total_detail_file}")
        print(f"   {binance_detail_file}")
        print(f"   {bybit_detail_file}")
        print(f"   {total_daily_file}")

    def generate_total_daily(self, overall_df):
        """生成 Total_daily 檔案"""
        if overall_df.empty:
            return pd.DataFrame()
        
        # 按日期分組並計算加總
        daily_records = []
        
        for date in overall_df['Date'].unique():
            date_data = overall_df[overall_df['Date'] == date]
            
            # 計算各項目的加總
            trading_pair_number = len(date_data)
            binance_ff = date_data['Binance FF'].sum()
            bybit_ff = date_data['Bybit FF'].sum()
            net_pnl = date_data['Net P&L'].sum()
            
            # 計算保證金加總（排除 null 值）
            binance_m = 0
            bybit_m = 0
            total_m = 0
            
            # 處理可能的 null 值
            for _, row in date_data.iterrows():
                if row['Binance M'] != 'null' and pd.notnull(row['Binance M']):
                    binance_m += float(row['Binance M'])
                if row['Bybit M'] != 'null' and pd.notnull(row['Bybit M']):
                    bybit_m += float(row['Bybit M'])
                if row['Total M'] != 'null' and pd.notnull(row['Total M']):
                    total_m += float(row['Total M'])
            
            # 計算收益率
            return_rate = net_pnl / total_m if total_m > 0 else 0
            roi = return_rate * 365
            
            daily_records.append({
                'Date': date,
                'Trading pair number': trading_pair_number,
                'Binance FF': binance_ff,
                'Bybit FF': bybit_ff,
                'Net P&L': net_pnl,
                'Binance M': binance_m if binance_m > 0 else 'null',
                'Bybit M': bybit_m if bybit_m > 0 else 'null',
                'Total M': total_m if total_m > 0 else 'null',
                'Return': return_rate if total_m > 0 else 'null',
                'ROI': roi if total_m > 0 else 'null'
            })
        
        return pd.DataFrame(daily_records)


def load_user_config(env_file):
    """載入用戶環境檔案"""
    if not os.path.exists(env_file):
        print(f"❌ 環境檔案不存在: {env_file}")
        return None
    
    # 載入環境變數
    load_dotenv(env_file)
    
    # 從環境變數讀取配置
    config = {
        'USER_NAME': os.getenv('USER_NAME'),
        'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY'),
        'BINANCE_SECRET_KEY': os.getenv('BINANCE_SECRET_KEY'),
        'BYBIT_API_KEY': os.getenv('BYBIT_API_KEY'),
        'BYBIT_SECRET_KEY': os.getenv('BYBIT_SECRET_KEY'),
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID')
    }
    
    # 檢查必要配置
    required_keys = ['BINANCE_API_KEY', 'BINANCE_SECRET_KEY', 'BYBIT_API_KEY', 'BYBIT_SECRET_KEY']
    for key in required_keys:
        if not config[key]:
            print(f"❌ 環境檔案缺少必要配置: {key}")
            return None
    
    return config


def get_user_input_dates():
    """獲取用戶輸入的日期"""
    print("🔍 套利收益分析工具 (多用戶版)")
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
    parser = argparse.ArgumentParser(description='多用戶套利收益分析工具 v1.0')
    parser.add_argument('--start', help='開始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', help='結束日期 (YYYY-MM-DD)')
    parser.add_argument('--auto', action='store_true', help='自動模式：計算今天的收益')
    parser.add_argument('--env', help='用戶環境檔案路徑 (例如: .env.user1)', required=False)
    parser.add_argument('--user', help='用戶名稱 (當未指定env時，會尋找 .env.{user} 檔案)', required=False)
    
    args = parser.parse_args()
    
    # 決定環境檔案路徑
    if args.env:
        env_file = args.env
    elif args.user:
        env_file = f".env.{args.user}"
    else:
        # 預設使用 .env 檔案
        env_file = ".env"
        
        # 如果預設 .env 不存在，嘗試從 api_config.py 載入（向後兼容）
        if not os.path.exists(env_file):
            print("⚠️ 未找到 .env 檔案，嘗試從 api_config.py 載入...")
            try:
                from api_config import (
                    BINANCE_API_KEY, BINANCE_SECRET_KEY, 
                    BYBIT_API_KEY, BYBIT_SECRET_KEY,
                    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
                )
                config = {
                    'USER_NAME': 'default',
                    'BINANCE_API_KEY': BINANCE_API_KEY,
                    'BINANCE_SECRET_KEY': BINANCE_SECRET_KEY,
                    'BYBIT_API_KEY': BYBIT_API_KEY,
                    'BYBIT_SECRET_KEY': BYBIT_SECRET_KEY,
                    'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
                    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
                }
                print("✅ 已從 api_config.py 載入配置")
            except ImportError:
                print("❌ 請創建 .env 檔案或 api_config.py 並設定API金鑰")
                print("\n範例 .env 檔案內容:")
                print("USER_NAME=user1")
                print("BINANCE_API_KEY=your_binance_api_key")
                print("BINANCE_SECRET_KEY=your_binance_secret_key")
                print("BYBIT_API_KEY=your_bybit_api_key")
                print("BYBIT_SECRET_KEY=your_bybit_secret_key")
                print("TELEGRAM_BOT_TOKEN=your_telegram_bot_token")
                print("TELEGRAM_CHAT_ID=your_telegram_chat_id")
                return
    
    # 載入環境檔案
    if 'config' not in locals():
        config = load_user_config(env_file)
        if not config:
            return
    
    print(f"📁 使用環境檔案: {env_file}")
    if config.get('USER_NAME'):
        print(f"👤 用戶: {config['USER_NAME']}")
    
    # 創建分析器
    analyzer = ArbitrageAnalyzer(
        config['BINANCE_API_KEY'], 
        config['BINANCE_SECRET_KEY'], 
        config['BYBIT_API_KEY'], 
        config['BYBIT_SECRET_KEY'],
        config.get('USER_NAME')
    )
    
    # 處理自動模式
    if args.auto:
        # 自動計算今天的日期
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        start_date = end_date = today
        
        print(f"🤖 自動模式：分析 {today} 的收益")
        
        # 創建Telegram通知器（如果有配置）
        notifier = None
        if config.get('TELEGRAM_BOT_TOKEN') and config.get('TELEGRAM_CHAT_ID'):
            notifier = TelegramNotifier(config['TELEGRAM_BOT_TOKEN'], config['TELEGRAM_CHAT_ID'])
        
        try:
            # 執行分析
            overall_df, binance_df, bybit_df = analyzer.analyze_data(start_date, end_date)
            analyzer.save_results(overall_df, binance_df, bybit_df, start_date, end_date)
            
            # 從 Total_daily 檔案讀取統計資料
            output_dir = analyzer.output_base_dir
            suffix = today.replace('-', '_')
            total_daily_file = f"{output_dir}/Total_daily_{suffix}.csv"
            
            # 讀取 Total_daily 檔案
            daily_df = pd.read_csv(total_daily_file)
            daily_row = daily_df[daily_df['Date'] == today].iloc[0]
            
            # 從 Total_daily 取得資料
            symbol_count = int(daily_row['Trading pair number'])
            binance_pnl = float(daily_row['Binance FF'])
            bybit_pnl = float(daily_row['Bybit FF'])
            total_pnl = float(daily_row['Net P&L'])
            total_margin = daily_row['Total M']
            roi = daily_row['ROI']
            
            # 處理可能的 null 值
            if total_margin == 'null':
                total_margin = None
            else:
                total_margin = float(total_margin)
                
            if roi == 'null':
                roi = None
            else:
                roi = float(roi)
            
            # 從 Total_detail 檔案計算倉位總覽
            symbol_details = {}
            if not overall_df.empty:
                for symbol in overall_df['Symbol'].unique():
                    symbol_data = overall_df[overall_df['Symbol'] == symbol]
                    symbol_pnl = symbol_data['Net P&L'].sum()
                    symbol_details[symbol] = symbol_pnl
                
                # 按淨收益降序排序
                symbol_details = dict(sorted(symbol_details.items(), key=lambda x: x[1], reverse=True))
            
            # 發送成功通知
            if notifier:
                notifier.send_success_notification(
                    today, total_pnl, symbol_count, None, binance_pnl, bybit_pnl, 
                    symbol_details, total_margin, roi, config.get('USER_NAME')
                )
            
            print(f"\n📊 統計資訊:")
            print(f"   總記錄數: {len(overall_df)}")
            print(f"   涉及交易對: {symbol_count}")
            print(f"   總淨損益: ${total_pnl:.2f}")
            
            if total_margin is not None:
                print(f"   總倉位保證金: ${total_margin:.2f}")
            
            if roi is not None:
                print(f"   等效年化收益率: {roi*100:.2f}%")
            
        except Exception as e:
            # 發送錯誤通知
            if notifier:
                notifier.send_error_notification(today, str(e), config.get('USER_NAME'))
            print(f"❌ 執行錯誤: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    else:
        # 手動模式：如果沒有提供命令行參數，則提示用戶輸入
        if not args.start or not args.end:
            start_date, end_date = get_user_input_dates()
        else:
            start_date = args.start
            end_date = args.end
        
        print(f"\n📅 分析期間: {start_date} 至 {end_date}")
        print("🚀 開始分析...")
        
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