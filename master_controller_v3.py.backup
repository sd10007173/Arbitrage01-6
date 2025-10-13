#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資金費率分析系統總控程式 V3.0
=============================

功能：自動化執行完整的資金費率分析流程
包含：市值數據更新 → 交易所支持檢查 → 資金費率獲取 → 差異計算 → 收益計算 → 策略排名 → 收益圖表生成

使用方式：
- 交互式模式：python master_controller_v3.py
- 命令行模式：python master_controller_v3.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09 --strategy 1

V3.0 更新：
- 基於 V2.0 版本功能
- 新增 --telegram_send 參數，可自定義發送前後N名圖片（默認3名）
- 設定為0時不發送任何圖片
- 改進 Telegram 圖片發送邏輯的可配置性

V3.0 特色：
- 可配置的 Telegram 圖片發送數量
- 默認發送前後3名（而非之前的15名）
- 支援設定0來完全跳過圖片發送
- 保持 V2.0 的所有智能增量處理功能
"""

import subprocess
import argparse
import sys
import time
import sqlite3
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional
import os # Added for os.path.exists

# 導入策略配置
try:
    from ranking_config import RANKING_STRATEGIES, EXPERIMENTAL_CONFIGS
except ImportError:
    print("❌ 無法導入策略配置，請確保 ranking_config.py 存在")
    sys.exit(1)

# 添加數據庫相關函數
DB_PATH = "data/funding_rate.db"

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
            datetime.strptime(date_input, '%Y-%m-%d')
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
        bool: 驗證是否通過
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # 如果是自動模式，允許相同日期
        if is_auto_mode:
            if start_date > end_date:
                print("❌ 開始日期不能晚於結束日期")
                return False
        else:
            # 非自動模式，開始日期必須早於結束日期
            if start_date >= end_date:
                print("❌ 開始日期必須早於結束日期")
                return False
        
        # 檢查日期範圍是否合理
        date_diff = (end_date - start_date).days
        if date_diff > 365:
            print(f"⚠️  日期範圍為{date_diff}天，超過1年，處理時間可能很長")
        
        return True
        
    except ValueError:
        print("❌ 日期格式錯誤")
        return False

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

    def send_photo(self, photo_path, caption=""):
        """發送圖片到Telegram"""
        try:
            url = f"{self.base_url}/sendPhoto"
            
            # 檢查圖片是否存在
            if not os.path.exists(photo_path):
                print(f"圖片不存在: {photo_path}")
                return False
            
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption
                }
                response = requests.post(url, files=files, data=data, timeout=30)
                
            if response.status_code == 200:
                print(f"圖片已發送: {os.path.basename(photo_path)}")
                return True
            else:
                print(f"圖片發送失敗: {response.status_code}")
                print(f"回應內容: {response.text}")
                return False
        except Exception as e:
            print(f"圖片發送異常: {str(e)}")
            return False

class MasterControllerV3:
    """資金費率分析系統總控制器 V3.0"""
    
    def __init__(self, telegram_send_count=3):
        self.supported_exchanges = ['binance', 'bybit', 'okx', 'gate']
        self.available_strategies = self._load_available_strategies()
        self.notifier = self._init_telegram_notifier()
        self.telegram_send_count = telegram_send_count  # V3.0: 新增可配置的發送數量
        self.steps = [
            {
                'name': '市值數據更新',
                'script': 'market_cap_trading_pair.py',
                'description': '從 CoinGecko API 獲取市值排名前N的幣種數據並更新資料庫'
            },
            {
                'name': '交易所支持檢查',
                'script': 'exchange_trading_pair_v10.py',
                'description': '檢查交易對在各交易所的支持狀態和上市日期'
            },
            {
                'name': '資金費率獲取',
                'script': 'fetch_FR_history_group_v2.py',
                'description': '獲取指定時間範圍內的資金費率歷史數據'
            },
            {
                'name': '差異計算',
                'script': 'calculate_FR_diff_v3.py',
                'description': '計算交易所間的資金費率差異'
            },
            {
                'name': '收益計算',
                'script': 'calculate_FR_return_list_v3.py',  # V2.0: 升級到 v3
                'description': '計算資金費率收益指標 (數據完整性檢查版本)'
            },
            {
                'name': '策略排名',
                'script': 'strategy_ranking_v3.py',  # V2.0: 升級到 v3
                'description': '基於選定策略進行交易對排名 (數據完整性檢查版本)'
            },
            {
                'name': '收益圖表生成',
                'script': 'draw_return_metrics_v4.py',
                'description': '生成交易對收益圖表（累積收益圖和每日收益圖）'
            }
        ]
    
    def _init_telegram_notifier(self):
        """初始化Telegram通知器"""
        try:
            from api_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
            return TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        except ImportError:
            print("ℹ️ 未找到 Telegram 配置，跳過通知功能")
            return None
        except Exception as e:
            print(f"⚠️ Telegram 配置載入失敗: {e}")
            return None
    
    def send_telegram_notification(self, message):
        """發送Telegram通知（帶錯誤處理）"""
        if self.notifier:
            self.notifier.send_message(message)
    
    def send_ranking_charts(self, target_date: str, strategy: str = 'original'):
        """
        發送策略排名圖片到Telegram - V3.0 可配置版本
        
        Args:
            target_date: 目標日期（用於查詢排名）
            strategy: 策略名稱，默認為 'original'
        """
        if not self.notifier:
            print("Telegram通知器未配置，跳過圖片發送")
            return
        
        # V3.0: 檢查是否設定為0（不發送圖片）
        if self.telegram_send_count <= 0:
            print("📱 Telegram發送數量設定為0，跳過圖片發送")
            return
        
        print(f"\n開始發送策略排名圖片...")
        print(f"   策略: {strategy}")
        print(f"   排名日期: {target_date}")
        print(f"   圖片類型: 全歷史數據")
        print(f"   發送數量: 前{self.telegram_send_count}名和後{self.telegram_send_count}名")  # V3.0: 顯示配置的數量
        
        try:
            # 查詢策略排名數據
            conn = get_connection()
            cursor = conn.cursor()
            
            # 使用目標日期的排名
            query = """
            SELECT trading_pair, rank_position 
            FROM strategy_ranking 
            WHERE strategy_name = ? AND date = ?
            ORDER BY rank_position
            """
            
            cursor.execute(query, (strategy, target_date))
            ranking_data = cursor.fetchall()
            conn.close()
            
            if not ranking_data:
                print(f"找不到策略 {strategy} 在 {target_date} 的排名數據")
                return
            
            print(f"找到 {len(ranking_data)} 個交易對的排名數據")
            
            # V3.0: 使用可配置的發送數量
            top_n = ranking_data[:self.telegram_send_count]
            bottom_n = ranking_data[-self.telegram_send_count:] if len(ranking_data) >= self.telegram_send_count else []
            
            # 生成圖片路徑
            picture_dir = "data/picture"
            
            # 發送前N名
            print(f"\n發送前{self.telegram_send_count}名圖片...")
            for i, (trading_pair, rank_position) in enumerate(top_n):
                # 使用全歷史圖片命名
                image_filename = f"{trading_pair}_full_history_return_pic.png"
                image_path = os.path.join(picture_dir, image_filename)
                
                if os.path.exists(image_path):
                    caption = f"【第{rank_position}名】{trading_pair}"
                    success = self.notifier.send_photo(image_path, caption)
                    if success:
                        print(f"   第{rank_position}名: {trading_pair}")
                    else:
                        print(f"   第{rank_position}名發送失敗: {trading_pair}")
                    
                    # 避免發送太快
                    time.sleep(1)
                else:
                    print(f"   第{rank_position}名圖片不存在: {image_filename}")
            
            # 發送後N名
            if bottom_n:
                print(f"\n發送後{self.telegram_send_count}名圖片...")
                for i, (trading_pair, rank_position) in enumerate(bottom_n):
                    # 使用全歷史圖片命名
                    image_filename = f"{trading_pair}_full_history_return_pic.png"
                    image_path = os.path.join(picture_dir, image_filename)
                    
                    if os.path.exists(image_path):
                        caption = f"【第{rank_position}名】{trading_pair}"
                        success = self.notifier.send_photo(image_path, caption)
                        if success:
                            print(f"   第{rank_position}名: {trading_pair}")
                        else:
                            print(f"   第{rank_position}名發送失敗: {trading_pair}")
                        
                        # 避免發送太快
                        time.sleep(1)
                    else:
                        print(f"   第{rank_position}名圖片不存在: {image_filename}")
            
            print(f"\n策略排名圖片發送完成")
            
        except Exception as e:
            print(f"發送策略排名圖片時出錯: {e}")
    
    def _load_available_strategies(self) -> List[Tuple[str, str]]:
        """加載可用策略列表"""
        strategies = []
        
        # 添加主要策略
        for key, config in RANKING_STRATEGIES.items():
            strategies.append((key, config['name']))
        
        # 添加實驗性策略
        for key, config in EXPERIMENTAL_CONFIGS.items():
            strategies.append((key, config['name']))
        
        return strategies
    
    def display_available_strategies(self):
        """顯示可用策略"""
        print("\n🎯 可用策略:")
        print("="*50)
        
        # 顯示主要策略
        main_count = 0
        for key, name in self.available_strategies:
            if key in RANKING_STRATEGIES:
                main_count += 1
                print(f"{main_count}. {key:20s} - {name}")
        
        # 顯示實驗性策略
        print("\n🧪 實驗性策略:")
        print("-" * 30)
        exp_count = main_count
        for key, name in self.available_strategies:
            if key in EXPERIMENTAL_CONFIGS:
                exp_count += 1
                print(f"{exp_count}. {key:20s} - {name}")
        
        print(f"{len(self.available_strategies)+1}. 全部策略 (all)")
        print("0. 退出")
    
    def get_strategy_by_number(self, strategy_num: int) -> Optional[str]:
        """根據編號獲取策略名稱"""
        if strategy_num == 0:
            return None
        elif strategy_num == len(self.available_strategies) + 1:
            return 'all'
        elif 1 <= strategy_num <= len(self.available_strategies):
            return self.available_strategies[strategy_num - 1][0]
        else:
            return None
    
    def get_strategy_by_name(self, strategy_name: str) -> Optional[str]:
        """根據名稱獲取策略名稱（驗證存在性）"""
        if strategy_name.lower() == 'all':
            return 'all'
        
        for key, _ in self.available_strategies:
            if key == strategy_name:
                return strategy_name
        
        return None
    
    def interactive_strategy_selection(self) -> Optional[str]:
        """交互式策略選擇"""
        self.display_available_strategies()
        
        while True:
            try:
                choice = input(f"\n請選擇策略 (1-{len(self.available_strategies)+1}, 或 0 退出): ").strip()
                
                if choice == '0':
                    print("👋 用戶選擇退出")
                    return None
                
                # 嘗試按編號選擇
                if choice.isdigit():
                    strategy_num = int(choice)
                    strategy = self.get_strategy_by_number(strategy_num)
                    if strategy is not None:
                        if strategy == 'all':
                            print("✅ 選擇全部策略")
                            return 'all'
                        else:
                            strategy_name = dict(self.available_strategies)[strategy]
                            print(f"✅ 選擇策略: {strategy} - {strategy_name}")
                            return strategy
                    else:
                        print(f"❌ 無效的策略編號: {strategy_num}")
                else:
                    # 嘗試按名稱選擇
                    strategy = self.get_strategy_by_name(choice)
                    if strategy is not None:
                        if strategy == 'all':
                            print("✅ 選擇全部策略")
                            return 'all'
                        else:
                            strategy_name = dict(self.available_strategies)[strategy]
                            print(f"✅ 選擇策略: {strategy} - {strategy_name}")
                            return strategy
                    else:
                        print(f"❌ 無效的策略名稱: {choice}")
                
            except ValueError:
                print("❌ 請輸入有效的數字或策略名稱")
            except KeyboardInterrupt:
                print("\n👋 用戶中斷，退出程式")
                return None
    
    def validate_inputs(self, exchanges: List[str], top_n, start_date: str, end_date: str, strategy: str) -> bool:
        """驗證輸入參數"""
        # 驗證交易所
        invalid_exchanges = [ex for ex in exchanges if ex not in self.supported_exchanges]
        if invalid_exchanges:
            print(f"❌ 不支持的交易所: {invalid_exchanges}")
            print(f"✅ 支持的交易所: {self.supported_exchanges}")
            return False
        
        # 驗證市值排名（V2.0: top_n 必須是正整數，不能是 "all"）
        if not isinstance(top_n, int) or top_n <= 0:
            print("❌ 市值排名必須是大於0的正整數")
            print("💡 提示：因為需要調用 CoinGecko API，top_n 不能是 'all'")
            return False
        
        # 驗證日期格式
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            if start_dt > end_dt:
                print("❌ 開始日期不能晚於結束日期")
                return False
            
            # 檢查日期範圍是否合理（不超過1年）
            if (end_dt - start_dt).days > 365:
                print("⚠️ 日期範圍超過1年，處理時間可能很長")
        except ValueError:
            print("❌ 無效的日期格式，請使用 YYYY-MM-DD 格式")
            return False
        
        # 驗證策略
        if strategy != 'all' and self.get_strategy_by_name(strategy) is None:
            print(f"❌ 無效的策略: {strategy}")
            print("✅ 可用策略:", [key for key, _ in self.available_strategies])
            return False
        
        return True
    
    def get_interactive_inputs(self) -> Tuple[List[str], int, str, str, str]:
        """獲取交互式輸入"""
        print("\n📋 請輸入分析參數:")
        print("=" * 40)
        
        # 獲取交易所
        while True:
            exchanges_input = input("請輸入交易所，用空格分隔 (例如: binance bybit): ").strip().lower()
            exchanges = [ex.strip() for ex in exchanges_input.split() if ex.strip()]
            
            if not exchanges:
                print("❌ 請輸入至少一個交易所")
                continue
            
            invalid_exchanges = [ex for ex in exchanges if ex not in self.supported_exchanges]
            if invalid_exchanges:
                print(f"❌ 不支持的交易所: {invalid_exchanges}")
                print(f"✅ 支持的交易所: {self.supported_exchanges}")
                continue
            
            break
        
        # 獲取市值排名
        while True:
            try:
                user_input = input("請輸入市值排名前N名 (例如: 100，必須為正整數): ").strip()
                top_n = int(user_input)
                if top_n <= 0:
                    print("❌ 市值排名必須大於0")
                    continue
                break
            except ValueError:
                print("❌ 請輸入有效的數字")
                print("💡 提示：因為需要調用 CoinGecko API，不支持 'all' 選項")
        
        # 獲取開始日期
        while True:
            start_date_input = input("請輸入開始日期 (YYYY-MM-DD) 或輸入 'up_to_date' 從最新數據開始: ").strip()
            try:
                start_date = process_date_input(start_date_input, "start")
                break
            except ValueError as e:
                print(f"❌ {e}")
        
        # 獲取結束日期
        while True:
            end_date_input = input("請輸入結束日期 (YYYY-MM-DD) 或輸入 'up_to_date' 更新到昨天: ").strip()
            try:
                end_date = process_date_input(end_date_input, "end")
                break
            except ValueError as e:
                print(f"❌ {e}")
        
        # 檢查日期邏輯
        is_auto_mode = (start_date_input == "up_to_date" or end_date_input == "up_to_date")
        if not validate_date_range(start_date, end_date, is_auto_mode):
            print("❌ 日期範圍驗證失敗")
            return None, None, None, None, None
        
        # 獲取策略
        strategy = self.interactive_strategy_selection()
        if strategy is None:
            return None, None, None, None, None
        
        return exchanges, top_n, start_date, end_date, strategy
    
    def display_execution_plan(self, exchanges: List[str], top_n, start_date: str, end_date: str, strategy: str, use_legacy: bool = False):
        """顯示執行計劃"""
        print("\n" + "="*60)
        print("📋 執行計劃確認 (V3.0)")
        print("="*60)
        print(f"🏛️  交易所: {', '.join(exchanges)}")
        print(f"📊 市值排名: 前{top_n}名")
        print(f"📅 日期範圍: {start_date} 至 {end_date}")
        
        if strategy == 'all':
            print(f"🎯 策略: 全部策略 ({len(self.available_strategies)}個)")
        else:
            strategy_name = dict(self.available_strategies)[strategy]
            print(f"🎯 策略: {strategy} - {strategy_name}")
        
        # V3.0: 顯示 Telegram 發送設定
        if self.telegram_send_count <= 0:
            print("📱 Telegram圖片: 不發送圖片 (設定為0)")
        else:
            print(f"📱 Telegram圖片: 前{self.telegram_send_count}名和後{self.telegram_send_count}名")
        
        if use_legacy:
            print("⚠️  執行模式: 舊版兼容模式 (--use-legacy)")
        else:
            print("🚀 執行模式: 數據完整性檢查模式 (V3)")
        
        print("\n📝 執行步驟:")
        for i, step in enumerate(self.steps, 1):
            # 標記升級的步驟
            if step['script'] in ['calculate_FR_return_list_v3.py', 'strategy_ranking_v3.py']:
                version_info = " (V3 數據完整性檢查)" if not use_legacy else " (V2 兼容模式)"
                print(f"   {i}. {step['name']}{version_info}")
            else:
                print(f"   {i}. {step['name']}")
            print(f"      └─ {step['description']}")
        
        print("="*60)
    
    def run_step(self, step_index: int, exchanges: List[str], top_n: int, start_date: str, end_date: str, strategy: str, use_legacy: bool = False) -> bool:
        """執行單個步驟"""
        step = self.steps[step_index]
        script = step['script']
        
        print(f"\n🔄 執行步驟 {step_index + 1}/{len(self.steps)}: {step['name']}")
        print(f"   📝 {step['description']}")
        print(f"   📄 腳本: {script}")
        
        if use_legacy and script in ['calculate_FR_return_list_v3.py', 'strategy_ranking_v3.py']:
            print(f"   ⚠️  使用舊版兼容模式")
        
        start_time = time.time()
        
        try:
            if script == 'market_cap_trading_pair.py':
                # 步驟1: 市值數據更新
                cmd = [sys.executable, script, '--top_n', str(top_n)]
                
            elif script == 'exchange_trading_pair_v10.py':
                # 步驟2: 交易所支持檢查
                cmd = [sys.executable, script, '--exchanges'] + exchanges + ['--top_n', str(top_n)]
                
            elif script == 'fetch_FR_history_group_v2.py':
                # 步驟3: 資金費率獲取
                cmd = [sys.executable, script, '--exchanges'] + exchanges + ['--top_n', str(top_n), '--start_date', start_date, '--end_date', end_date]
                
            elif script == 'calculate_FR_diff_v3.py':
                # 步驟4: 差異計算
                cmd = [sys.executable, script, '--start-date', start_date, '--end-date', end_date, '--exchanges'] + exchanges
                
            elif script == 'calculate_FR_return_list_v3.py':
                # 步驟5: 收益計算 (V2.0: 升級到 v3)
                if use_legacy:
                    # 使用舊版兼容模式
                    cmd = [sys.executable, 'calculate_FR_return_list_v2.py', '--start-date', start_date, '--end-date', end_date]
                else:
                    # 使用新版 v3 (數據完整性檢查)
                    cmd = [sys.executable, script, '--start-date', start_date, '--end-date', end_date]
                
            elif script == 'strategy_ranking_v3.py':
                # 步驟6: 策略排名 (V2.0: 升級到 v3)
                if use_legacy:
                    # 使用舊版兼容模式
                    cmd = [sys.executable, 'strategy_ranking_v2.py', '--start_date', start_date, '--end_date', end_date]
                else:
                    # 使用新版 v3 (數據完整性檢查)
                    cmd = [sys.executable, script, '--start_date', start_date, '--end_date', end_date]
                
                # 添加策略參數
                if strategy == 'all':
                    # 不添加 --strategies 參數，會自動選擇全部策略
                    pass
                else:
                    cmd.extend(['--strategies', strategy])
                    
            elif script == 'draw_return_metrics_v4.py':
                # 步驟7: 收益圖表生成 (全歷史數據)
                cmd = [sys.executable, script, '--output-dir', 'data/picture']
                # 不傳遞 start_date 和 end_date 參數，生成全歷史圖片
                    
            else:
                print(f"❌ 未知腳本: {script}")
                return False
            
            print(f"   🔧 執行命令: {' '.join(cmd)}")
            
            # 執行命令
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            if result.returncode == 0:
                print(f"   ✅ 完成! 耗時: {elapsed:.2f}秒")
                if result.stdout:
                    print(f"   📤 輸出: {result.stdout[-200:]}")  # 顯示最後200字符
                return True
            else:
                print(f"   ❌ 失敗! 耗時: {elapsed:.2f}秒")
                print(f"   📤 錯誤: {result.stderr}")
                return False
                
        except Exception as e:
            end_time = time.time()
            elapsed = end_time - start_time
            print(f"   ❌ 異常! 耗時: {elapsed:.2f}秒")
            print(f"   📤 錯誤: {str(e)}")
            return False
    
    def run_complete_process(self, exchanges: List[str], top_n: int, start_date: str, end_date: str, strategy: str, args=None):
        """執行完整流程"""
        
        # 檢查是否使用舊版兼容模式
        use_legacy = args and args.use_legacy
        
        # 發送開始通知
        if args and not args.no_telegram:
            start_time_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            mode_info = " (舊版兼容模式)" if use_legacy else " (V3 數據完整性檢查)"
            # V3.0: 在通知中包含發送數量信息
            telegram_info = f", Telegram圖片: 前後{self.telegram_send_count}名" if self.telegram_send_count > 0 else ", Telegram圖片: 不發送"
            message = f"master_controller_v3 開始執行{mode_info}{telegram_info}\n開始時間: {start_time_utc}"
            self.send_telegram_notification(message)
        
        print("\n🚀 開始執行完整的資金費率分析流程 (V3.0)")
        print("=" * 60)
        
        overall_start_time = time.time()
        
        for i in range(len(self.steps)):
            # 檢查是否跳過收益圖表生成（第7步，索引6）
            if i == 6 and args and args.no_charts:
                print(f"\n⏭️  跳過步驟 {i + 1}/7: {self.steps[i]['name']}")
                print(f"   📝 已通過 --no-charts 參數跳過")
                continue
            
            success = self.run_step(i, exchanges, top_n, start_date, end_date, strategy, use_legacy)
            
            if not success:
                print(f"\n❌ 步驟 {i + 1} 失敗，流程中斷")
                
                # 發送失敗通知
                if args and not args.no_telegram:
                    end_time_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                    mode_info = " (舊版兼容模式)" if use_legacy else " (V3 數據完整性檢查)"
                    message = f"master_controller_v3 執行失敗{mode_info}\n失敗時間: {end_time_utc}"
                    self.send_telegram_notification(message)
                
                return False
        
        overall_end_time = time.time()
        total_elapsed = overall_end_time - overall_start_time
        
        # 發送策略排名圖片（當圖表生成完成且telegram未禁用時）
        if args and not args.no_charts and not args.no_telegram:
            self.send_ranking_charts(target_date=end_date, strategy='original')
        
        # 發送完成通知
        if args and not args.no_telegram:
            end_time_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            elapsed_minutes = total_elapsed / 60
            mode_info = " (舊版兼容模式)" if use_legacy else " (V3 數據完整性檢查)"
            message = f"master_controller_v3 執行完成{mode_info}\n完成時間: {end_time_utc}\n總耗時: {elapsed_minutes:.1f}分鐘"
            self.send_telegram_notification(message)
        
        print("\n" + "="*60)
        print("🎉 流程完成! (V3.0)")
        print(f"⏱️  總耗時: {total_elapsed:.2f}秒 ({total_elapsed/60:.1f}分鐘)")
        if use_legacy:
            print("⚠️  使用了舊版兼容模式")
        else:
            print("🚀 使用了 V3 數據完整性檢查模式")
        # V3.0: 顯示 Telegram 發送設定
        if self.telegram_send_count > 0:
            print(f"📱 已發送前{self.telegram_send_count}名和後{self.telegram_send_count}名圖片到 Telegram")
        else:
            print("📱 未發送 Telegram 圖片（設定為0）")
        print("="*60)
        
        return True

def main():
    """主函數"""
    # 記錄程式開始時間
    program_start_time = time.time()
    start_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"========== 開始執行: {start_time_str} ==========")
    
    parser = argparse.ArgumentParser(
        description='資金費率分析系統總控程式 V3.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用範例:
  python master_controller_v3.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09 --strategy 1
  python master_controller_v3.py --exchanges binance bybit --top_n 500 --start_date 2025-07-01 --end_date 2025-07-09 --strategy original
  python master_controller_v3.py --exchanges binance bybit --top_n 1000 --start_date 2025-07-01 --end_date 2025-07-09 --strategy all
  python master_controller_v3.py --exchanges binance bybit --top_n 100 --start_date up_to_date --end_date up_to_date --strategy 1
  python master_controller_v3.py --exchanges binance bybit --top_n 750 --start_date up_to_date --end_date up_to_date --strategy all --yes
  python master_controller_v3.py --exchanges binance bybit --top_n 750 --start_date up_to_date --end_date up_to_date --strategy all --yes --no-charts
  python master_controller_v3.py --exchanges binance bybit --top_n 750 --start_date up_to_date --end_date up_to_date --strategy all --yes --use-legacy
  python master_controller_v3.py --exchanges binance bybit --top_n 750 --start_date up_to_date --end_date up_to_date --strategy all --yes --telegram_send 10
  python master_controller_v3.py --exchanges binance bybit --top_n 750 --start_date up_to_date --end_date up_to_date --strategy all --yes --telegram_send 0

V3.0 新功能:
- 基於 V2.0 的所有功能
- 新增 --telegram_send 參數，可自定義發送前後N名圖片（默認3名）
- 設定為0時不發送任何圖片
- 改進 Telegram 圖片發送邏輯的可配置性

注意事項:
- top_n 參數必須是正整數，不能是 'all'，因為需要調用 CoinGecko API
- 系統會先更新市值數據，然後依序執行7個步驟的完整流程
- 使用 --yes 參數可跳過確認步驟，適用於 crontab 自動化執行
- V3 版本會自動檢查數據完整性並只處理缺失的數據
- telegram_send 默認為3，表示發送前3名和後3名，設定為0則不發送圖片
        '''
    )
    
    parser.add_argument('--exchanges', nargs='+', choices=['binance', 'bybit', 'okx', 'gate'],
                        help='要分析的交易所 (可選多個)')
    parser.add_argument('--top_n', type=int, help='市值排名前N名 (必須為正整數，用於CoinGecko API和分析)')
    parser.add_argument('--start_date', help='開始日期 (YYYY-MM-DD) 或 up_to_date (從最新數據開始)')
    parser.add_argument('--end_date', help='結束日期 (YYYY-MM-DD) 或 up_to_date (更新到昨天)')
    parser.add_argument('--strategy', help='策略選擇 (策略名稱、編號或 all)')
    parser.add_argument('--yes', action='store_true', help='自動確認執行，跳過手動確認步驟（適用於crontab自動化）')
    parser.add_argument('--no-telegram', action='store_true', help='禁用 Telegram 通知')
    parser.add_argument('--no-charts', action='store_true', help='跳過收益圖表生成')
    parser.add_argument('--use-legacy', action='store_true', help='使用舊版 v2 處理方式（向後兼容）')
    # V3.0: 新增 telegram_send 參數
    parser.add_argument('--telegram_send', type=int, default=3, 
                        help='Telegram 發送前後N名圖片數量 (默認3，設定為0則不發送圖片)')
    
    args = parser.parse_args()
    
    # V3.0: 驗證 telegram_send 參數
    if args.telegram_send < 0:
        print("❌ --telegram_send 參數不能為負數")
        return
    
    # 創建控制器 - V3.0: 傳入 telegram_send_count
    controller = MasterControllerV3(telegram_send_count=args.telegram_send)
    
    print("🎛️  資金費率分析系統總控程式 V3.0")
    print("=" * 50)
    
    # V3.0: 顯示 Telegram 發送設定
    if args.telegram_send > 0:
        print(f"📱 Telegram圖片發送: 前{args.telegram_send}名和後{args.telegram_send}名")
    else:
        print("📱 Telegram圖片發送: 已禁用 (設定為0)")
    
    # 獲取參數
    if all([args.exchanges, args.top_n, args.start_date, args.end_date, args.strategy]):
        # 命令行模式
        print("🖥️  命令行模式")
        exchanges = args.exchanges
        top_n = args.top_n
        
        # 處理日期參數
        try:
            start_date = process_date_input(args.start_date, "start")
            end_date = process_date_input(args.end_date, "end")
            
            # 檢查日期邏輯
            is_auto_mode = (args.start_date == "up_to_date" or args.end_date == "up_to_date")
            if not validate_date_range(start_date, end_date, is_auto_mode):
                print("❌ 日期範圍驗證失敗")
                return
        except ValueError as e:
            print(f"❌ 日期處理錯誤: {e}")
            return
        
        # 處理策略參數
        if args.strategy.isdigit():
            strategy = controller.get_strategy_by_number(int(args.strategy))
        else:
            strategy = controller.get_strategy_by_name(args.strategy)
        
        if strategy is None:
            print(f"❌ 無效的策略: {args.strategy}")
            controller.display_available_strategies()
            return
        
    else:
        # 交互式模式
        print("🎮 交互式模式")
        inputs = controller.get_interactive_inputs()
        
        if inputs[0] is None:
            print("👋 用戶選擇退出")
            return
        
        exchanges, top_n, start_date, end_date, strategy = inputs
    
    # 驗證輸入
    if not controller.validate_inputs(exchanges, top_n, start_date, end_date, strategy):
        return
    
    # 顯示執行計劃
    controller.display_execution_plan(exchanges, top_n, start_date, end_date, strategy, args.use_legacy if args else False)
    
    # 獲取用戶確認（如果有 --yes 參數則跳過確認）
    if not args.yes:
        confirm = input("\n是否繼續執行? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes', '是']:
            print("👋 用戶取消執行")
            return
    else:
        print("\n✅ 自動確認執行（--yes 參數）")
    
    # 執行完整流程
    success = controller.run_complete_process(exchanges, top_n, start_date, end_date, strategy, args)
    
    if success:
        print("\n🎊 資金費率分析完成！(V3.0)")
        print("💡 你可以使用 view_database_simple.py 查看結果")
        if not args.no_charts:
            print("📊 收益圖表已保存到 data/picture/ 目錄")
        else:
            print("📊 已跳過收益圖表生成")
        if args.use_legacy:
            print("⚠️  使用了舊版兼容模式")
        else:
            print("🚀 使用了 V3 數據完整性檢查模式")
        # V3.0: 顯示最終的 Telegram 發送設定
        if args.telegram_send > 0:
            print(f"📱 已通過 Telegram 發送前{args.telegram_send}名和後{args.telegram_send}名圖片")
        else:
            print("📱 未發送 Telegram 圖片（設定為0）")
    else:
        print("\n💥 分析過程中出現錯誤，請檢查日誌")
    
    # 記錄程式結束時間並計算耗時
    program_end_time = time.time()
    total_elapsed = program_end_time - program_start_time
    end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 計算耗時的分鐘和秒數
    elapsed_minutes = int(total_elapsed // 60)
    elapsed_seconds = int(total_elapsed % 60)
    
    if elapsed_minutes > 0:
        elapsed_str = f"{elapsed_minutes}分{elapsed_seconds}秒"
    else:
        elapsed_str = f"{elapsed_seconds}秒"
    
    print(f"========== 結束執行: {end_time_str} (耗時: {elapsed_str}) ==========")

if __name__ == "__main__":
    main() 