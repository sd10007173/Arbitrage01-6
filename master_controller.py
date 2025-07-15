#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資金費率分析系統總控程式
=============================

功能：自動化執行完整的資金費率分析流程
包含：市值數據更新 → 交易所支持檢查 → 資金費率獲取 → 差異計算 → 收益計算 → 策略排名 → 收益圖表生成

使用方式：
- 交互式模式：python master_controller.py
- 命令行模式：python master_controller.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09 --strategy 1

V2.0 更新：
- 添加策略選擇功能
- 支持策略編號或名稱選擇
- 完全自動化流程，無需中途用戶輸入

V2.1 更新：
- 添加收益圖表生成功能
- 7步驟完整流程，包含視覺化圖表輸出
- 圖表保存到 data/picture/ 目錄

V2.2 更新：
- 添加市值數據更新步驟
- 整合 market_cap_trading_pair.py 作為第一步
- 統一使用 top_n 參數控制市值排名範圍
"""

import subprocess
import argparse
import sys
import time
import sqlite3
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional

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

class MasterController:
    """資金費率分析系統總控制器"""
    
    def __init__(self):
        self.supported_exchanges = ['binance', 'bybit', 'okx', 'gate']
        self.available_strategies = self._load_available_strategies()
        self.notifier = self._init_telegram_notifier()
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
                'script': 'calculate_FR_return_list_v2.py',
                'description': '計算資金費率收益指標'
            },
            {
                'name': '策略排名',
                'script': 'strategy_ranking_v2.py',
                'description': '基於選定策略進行交易對排名'
            },
            {
                'name': '收益圖表生成',
                'script': 'draw_return_metrics_v3.py',
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
        
        # 驗證市值排名（V2.2 更新：top_n 必須是正整數，不能是 "all"）
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
    
    def display_execution_plan(self, exchanges: List[str], top_n, start_date: str, end_date: str, strategy: str):
        """顯示執行計劃"""
        print("\n" + "="*60)
        print("📋 執行計劃確認")
        print("="*60)
        print(f"🏛️  交易所: {', '.join(exchanges)}")
        print(f"📊 市值排名: 前{top_n}名")
        print(f"📅 日期範圍: {start_date} 至 {end_date}")
        
        if strategy == 'all':
            print(f"🎯 策略: 全部策略 ({len(self.available_strategies)}個)")
        else:
            strategy_name = dict(self.available_strategies)[strategy]
            print(f"🎯 策略: {strategy} - {strategy_name}")
        
        print("\n📝 執行步驟:")
        for i, step in enumerate(self.steps, 1):
            print(f"   {i}. {step['name']}")
            print(f"      └─ {step['description']}")
        
        print("="*60)
    
    def run_step(self, step_index: int, exchanges: List[str], top_n: int, start_date: str, end_date: str, strategy: str) -> bool:
        """執行單個步驟"""
        step = self.steps[step_index]
        script = step['script']
        
        print(f"\n🔄 執行步驟 {step_index + 1}/{len(self.steps)}: {step['name']}")
        print(f"   📝 {step['description']}")
        print(f"   📄 腳本: {script}")
        
        start_time = time.time()
        
        try:
            if script == 'market_cap_trading_pair.py':
                # 步驟0: 市值數據更新
                cmd = [sys.executable, script, '--top_n', str(top_n)]
                
            elif script == 'exchange_trading_pair_v10.py':
                # 步驟1: 交易所支持檢查
                cmd = [sys.executable, script, '--exchanges'] + exchanges + ['--top_n', str(top_n)]
                
            elif script == 'fetch_FR_history_group_v2.py':
                # 步驟2: 資金費率獲取
                cmd = [sys.executable, script, '--exchanges'] + exchanges + ['--top_n', str(top_n), '--start_date', start_date, '--end_date', end_date]
                
            elif script == 'calculate_FR_diff_v3.py':
                # 步驟3: 差異計算
                cmd = [sys.executable, script, '--start-date', start_date, '--end-date', end_date, '--exchanges'] + exchanges
                
            elif script == 'calculate_FR_return_list_v2.py':
                # 步驟4: 收益計算
                cmd = [sys.executable, script, '--start-date', start_date, '--end-date', end_date]
                
            elif script == 'strategy_ranking_v2.py':
                # 步驟5: 策略排名
                cmd = [sys.executable, script, '--start_date', start_date, '--end_date', end_date]
                if strategy == 'all':
                    # 不添加 --strategies 參數，會自動選擇全部策略
                    pass
                else:
                    cmd.extend(['--strategies', strategy])
                    
            elif script == 'draw_return_metrics_v3.py':
                # 步驟6: 收益圖表生成
                cmd = [sys.executable, script, '--output-dir', 'data/picture']
                    
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
        
        # 發送開始通知
        if args and not args.no_telegram:
            start_time_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            message = f"🎛️ master_controller開始執行\n⏰ 開始時間: {start_time_utc}"
            self.send_telegram_notification(message)
        
        print("\n🚀 開始執行完整的資金費率分析流程")
        print("=" * 60)
        
        overall_start_time = time.time()
        
        for i in range(len(self.steps)):
            success = self.run_step(i, exchanges, top_n, start_date, end_date, strategy)
            
            if not success:
                print(f"\n❌ 步驟 {i + 1} 失敗，流程中斷")
                
                # 發送失敗通知
                if args and not args.no_telegram:
                    end_time_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                    message = f"❌ master_controller執行失敗\n⏰ 失敗時間: {end_time_utc}"
                    self.send_telegram_notification(message)
                
                return False
        
        overall_end_time = time.time()
        total_elapsed = overall_end_time - overall_start_time
        
        # 發送完成通知
        if args and not args.no_telegram:
            end_time_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            elapsed_minutes = total_elapsed / 60
            message = f"🎉 master_controller執行完成\n⏰ 完成時間: {end_time_utc}\n⏱️ 總耗時: {elapsed_minutes:.1f}分鐘"
            self.send_telegram_notification(message)
        
        print("\n" + "="*60)
        print("🎉 流程完成!")
        print(f"⏱️  總耗時: {total_elapsed:.2f}秒 ({total_elapsed/60:.1f}分鐘)")
        print("="*60)
        
        return True

def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description='資金費率分析系統總控程式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用範例:
  python master_controller.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09 --strategy 1
  python master_controller.py --exchanges binance bybit --top_n 500 --start_date 2025-07-01 --end_date 2025-07-09 --strategy original
  python master_controller.py --exchanges binance bybit --top_n 1000 --start_date 2025-07-01 --end_date 2025-07-09 --strategy all
  python master_controller.py --exchanges binance bybit --top_n 100 --start_date up_to_date --end_date up_to_date --strategy 1
  python master_controller.py --exchanges binance bybit --top_n 750 --start_date up_to_date --end_date up_to_date --strategy all --yes

注意事項:
- top_n 參數必須是正整數，不能是 'all'，因為需要調用 CoinGecko API
- 系統會先更新市值數據，然後依序執行7個步驟的完整流程
- 使用 --yes 參數可跳過確認步驟，適用於 crontab 自動化執行
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
    
    args = parser.parse_args()
    
    # 創建控制器
    controller = MasterController()
    
    print("🎛️  資金費率分析系統總控程式 V2.1")
    print("=" * 50)
    
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
    controller.display_execution_plan(exchanges, top_n, start_date, end_date, strategy)
    
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
        print("\n🎊 資金費率分析完成！")
        print("💡 你可以使用 view_database_simple.py 查看結果")
        print("📊 收益圖表已保存到 data/picture/ 目錄")
    else:
        print("\n💥 分析過程中出現錯誤，請檢查日誌")

if __name__ == "__main__":
    main() 