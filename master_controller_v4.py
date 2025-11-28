#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資金費率分析系統總控程式 V4.0
=============================

功能：自動化執行完整的資金費率分析流程
包含：市值數據更新 → 交易所支持檢查 → 資金費率獲取 → 差異計算 → 收益計算 → 策略排名 → 收益圖表生成

V4.0 更新：
- 支援新的 DEX 交易所 (EdgeX, Hyperliquid, Aster)
- 整合 exchange_trading_pair_v11.py
- 整合 fetch_FR_history_group_v3.py
- 默認 Telegram 發送數量調整為 15
"""

import subprocess
import argparse
import sys
import time
import sqlite3
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional
import os

# 導入策略配置
try:
    from ranking_config import RANKING_STRATEGIES, EXPERIMENTAL_CONFIGS
except ImportError:
    print("❌ 無法導入策略配置，請確保 ranking_config.py 存在")
    sys.exit(1)

DB_PATH = "data/funding_rate.db"

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
            datetime.strptime(date_input, '%Y-%m-%d')
            return date_input
        except ValueError: raise ValueError(f"無效日期: {date_input}")

def validate_date_range(start_date_str, end_date_str, is_auto_mode=False):
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        if is_auto_mode:
            if start_date > end_date: return False
        else:
            if start_date >= end_date: return False
        return True
    except ValueError: return False

class TelegramNotifier:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, message):
        try:
            url = f"{self.base_url}/sendMessage"
            data = {'chat_id': self.chat_id, 'text': message, 'parse_mode': 'HTML'}
            requests.post(url, data=data, timeout=30)
        except Exception as e: print(f"❌ Telegram通知異常: {e}")

    def send_photo(self, photo_path, caption=""):
        try:
            if not os.path.exists(photo_path): return False
            url = f"{self.base_url}/sendPhoto"
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': self.chat_id, 'caption': caption}
                response = requests.post(url, files=files, data=data, timeout=30)
            return response.status_code == 200
        except Exception as e:
            print(f"圖片發送異常: {e}")
            return False

class MasterControllerV4:
    def __init__(self, telegram_send_count=15): # V4 Default: 15
        self.supported_exchanges = ['binance', 'bybit', 'okx', 'gate', 'edgex', 'hyperliquid', 'aster']
        self.available_strategies = self._load_available_strategies()
        self.notifier = self._init_telegram_notifier()
        self.telegram_send_count = telegram_send_count
        self.steps = [
            {
                'name': '市值數據更新',
                'script': 'market_cap_trading_pair.py',
                'description': '從 CoinGecko API 獲取市值排名前N的幣種數據'
            },
            {
                'name': '交易所支持檢查 (V11)',
                'script': 'exchange_trading_pair_v11.py',
                'description': '檢查交易對在各交易所 (含 DEX) 的支持狀態'
            },
            {
                'name': '資金費率獲取 (V3)',
                'script': 'fetch_FR_history_group_v3.py',
                'description': '獲取資金費率歷史數據 (含 DEX Settlement)'
            },
            {
                'name': '差異計算 (V3)',
                'script': 'calculate_FR_diff_v3.py',
                'description': '計算交易所間的資金費率差異'
            },
            {
                'name': '收益計算 (V3)',
                'script': 'calculate_FR_return_list_v3.py',
                'description': '計算資金費率收益指標'
            },
            {
                'name': '策略排名 (V3)',
                'script': 'strategy_ranking_v3.py',
                'description': '基於選定策略進行交易對排名'
            },
            {
                'name': '收益圖表生成 (V4)',
                'script': 'draw_return_metrics_v4.py',
                'description': '生成交易對收益圖表'
            }
        ]
    
    def _init_telegram_notifier(self):
        try:
            from api_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
            return TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        except: return None
    
    def send_telegram_notification(self, message):
        if self.notifier: self.notifier.send_message(message)
    
    def send_ranking_charts(self, target_date: str, strategy: str = 'original'):
        if not self.notifier or self.telegram_send_count <= 0: return
        
        print(f"\n開始發送策略排名圖片 (前{self.telegram_send_count}名)...")
        try:
            conn = get_connection()
            cursor = conn.cursor()
            query = "SELECT trading_pair, rank_position FROM strategy_ranking WHERE strategy_name = ? AND date = ? ORDER BY rank_position"
            cursor.execute(query, (strategy, target_date))
            ranking_data = cursor.fetchall()
            conn.close()
            
            if not ranking_data: return
            
            top_n = ranking_data[:self.telegram_send_count]
            bottom_n = ranking_data[-self.telegram_send_count:] if len(ranking_data) >= self.telegram_send_count else []
            picture_dir = "data/picture"
            
            for trading_pair, rank_position in top_n:
                image_path = os.path.join(picture_dir, f"{trading_pair}_full_history_return_pic.png")
                if os.path.exists(image_path):
                    self.notifier.send_photo(image_path, f"【第{rank_position}名】{trading_pair}")
                    time.sleep(1)
            
            if bottom_n:
                for trading_pair, rank_position in bottom_n:
                    image_path = os.path.join(picture_dir, f"{trading_pair}_full_history_return_pic.png")
                    if os.path.exists(image_path):
                        self.notifier.send_photo(image_path, f"【第{rank_position}名】{trading_pair}")
                        time.sleep(1)
                        
        except Exception as e: print(f"發送圖片錯誤: {e}")
    
    def _load_available_strategies(self):
        strategies = []
        for key, config in RANKING_STRATEGIES.items(): strategies.append((key, config['name']))
        for key, config in EXPERIMENTAL_CONFIGS.items(): strategies.append((key, config['name']))
        return strategies

    def run_step(self, step_index, exchanges, top_n, start_date, end_date, strategy):
        step = self.steps[step_index]
        script = step['script']
        print(f"\n🔄 執行步驟 {step_index + 1}/{len(self.steps)}: {step['name']}")
        
        cmd = [sys.executable, script]
        
        if script == 'market_cap_trading_pair.py':
            cmd.extend(['--top_n', str(top_n)])
        elif script == 'exchange_trading_pair_v11.py':
            cmd.extend(['--exchanges'] + exchanges + ['--top_n', str(top_n)])
        elif script == 'fetch_FR_history_group_v3.py':
            cmd.extend(['--exchanges'] + exchanges + ['--top_n', str(top_n), '--start_date', start_date, '--end_date', end_date])
        elif script == 'calculate_FR_diff_v3.py':
            cmd.extend(['--start-date', start_date, '--end-date', end_date, '--exchanges'] + exchanges)
        elif script == 'calculate_FR_return_list_v3.py':
            cmd.extend(['--start-date', start_date, '--end-date', end_date])
        elif script == 'strategy_ranking_v3.py':
            cmd.extend(['--start_date', start_date, '--end_date', end_date])
            if strategy != 'all': cmd.extend(['--strategies', strategy])
        elif script == 'draw_return_metrics_v4.py':
            cmd.extend(['--output-dir', 'data/picture'])
            
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"   ✅ 完成!")
                if result.stdout: print(f"   📤 輸出: {result.stdout[-200:]}")
                return True
            else:
                print(f"   ❌ 失敗!")
                print(f"   📤 錯誤: {result.stderr}")
                return False
        except Exception as e:
            print(f"   ❌ 異常: {e}")
            return False

    def run_complete_process(self, exchanges, top_n, start_date, end_date, strategy, args=None):
        if args and not args.no_telegram:
            self.send_telegram_notification(f"MasterController V4 開始執行\n日期: {start_date} ~ {end_date}")
            
        print("\n🚀 開始執行完整的資金費率分析流程 (V4.0)")
        
        for i in range(len(self.steps)):
            if not self.run_step(i, exchanges, top_n, start_date, end_date, strategy):
                if args and not args.no_telegram:
                    self.send_telegram_notification(f"MasterController V4 執行失敗於步驟: {self.steps[i]['name']}")
                return False
        
        if args and not args.no_charts and not args.no_telegram:
            self.send_ranking_charts(target_date=end_date, strategy='original')
            
        if args and not args.no_telegram:
            self.send_telegram_notification(f"MasterController V4 執行完成")
            
        print("\n🎉 流程完成! (V4.0)")
        return True

def main():
    parser = argparse.ArgumentParser(description='資金費率分析系統總控程式 V4.0')
    parser.add_argument('--exchanges', nargs='+', required=True)
    parser.add_argument('--top_n', type=int, required=True)
    parser.add_argument('--start_date', type=str, required=True)
    parser.add_argument('--end_date', type=str, required=True)
    parser.add_argument('--strategy', type=str, default='original')
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--no-charts', action='store_true')
    parser.add_argument('--no-telegram', action='store_true')
    parser.add_argument('--telegram_send', type=int, default=15) # V4 Default
    
    args = parser.parse_args()
    
    controller = MasterControllerV4(telegram_send_count=args.telegram_send)
    
    # 簡單的參數處理
    start_date = process_date_input(args.start_date, "start")
    end_date = process_date_input(args.end_date, "end")
    
    controller.run_complete_process(args.exchanges, args.top_n, start_date, end_date, args.strategy, args)

if __name__ == "__main__":
    main()
