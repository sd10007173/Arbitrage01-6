#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資金費率分析系統總控程式
=============================

功能：自動化執行完整的資金費率分析流程
包含：交易所支持檢查 → 資金費率獲取 → 差異計算 → 收益計算 → 策略排名 → 收益圖表生成

使用方式：
- 交互式模式：python master_controller.py
- 命令行模式：python master_controller.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09 --strategy 1

V2.0 更新：
- 添加策略選擇功能
- 支持策略編號或名稱選擇
- 完全自動化流程，無需中途用戶輸入

V2.1 更新：
- 添加收益圖表生成功能
- 6步驟完整流程，包含視覺化圖表輸出
- 圖表保存到 data/picture/ 目錄
"""

import subprocess
import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

# 導入策略配置
try:
    from ranking_config import RANKING_STRATEGIES, EXPERIMENTAL_CONFIGS
except ImportError:
    print("❌ 無法導入策略配置，請確保 ranking_config.py 存在")
    sys.exit(1)

class MasterController:
    """資金費率分析系統總控制器"""
    
    def __init__(self):
        self.supported_exchanges = ['binance', 'bybit', 'okx', 'gate']
        self.available_strategies = self._load_available_strategies()
        self.steps = [
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
    
    def validate_inputs(self, exchanges: List[str], top_n: int, start_date: str, end_date: str, strategy: str) -> bool:
        """驗證輸入參數"""
        # 驗證交易所
        invalid_exchanges = [ex for ex in exchanges if ex not in self.supported_exchanges]
        if invalid_exchanges:
            print(f"❌ 不支持的交易所: {invalid_exchanges}")
            print(f"✅ 支持的交易所: {self.supported_exchanges}")
            return False
        
        # 驗證市值排名
        if top_n <= 0:
            print("❌ 市值排名必須大於0")
            return False
        
        # 驗證日期格式
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            if start_dt >= end_dt:
                print("❌ 開始日期必須早於結束日期")
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
                top_n = int(input("請輸入市值排名前N名 (例如: 100): ").strip())
                if top_n <= 0:
                    print("❌ 市值排名必須大於0")
                    continue
                break
            except ValueError:
                print("❌ 請輸入有效的數字")
        
        # 獲取開始日期
        while True:
            start_date = input("請輸入開始日期 (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                break
            except ValueError:
                print("❌ 無效的日期格式，請使用 YYYY-MM-DD 格式")
        
        # 獲取結束日期
        while True:
            end_date = input("請輸入結束日期 (YYYY-MM-DD): ").strip()
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                
                if start_dt >= end_dt:
                    print("❌ 結束日期必須晚於開始日期")
                    continue
                break
            except ValueError:
                print("❌ 無效的日期格式，請使用 YYYY-MM-DD 格式")
        
        # 獲取策略
        strategy = self.interactive_strategy_selection()
        if strategy is None:
            return None, None, None, None, None
        
        return exchanges, top_n, start_date, end_date, strategy
    
    def display_execution_plan(self, exchanges: List[str], top_n: int, start_date: str, end_date: str, strategy: str):
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
            if script == 'exchange_trading_pair_v10.py':
                # 步驟1: 交易所支持檢查
                cmd = ['python', script, '--exchanges'] + exchanges + ['--top_n', str(top_n)]
                
            elif script == 'fetch_FR_history_group_v2.py':
                # 步驟2: 資金費率獲取
                cmd = ['python', script, '--exchanges'] + exchanges + ['--top_n', str(top_n), '--start_date', start_date, '--end_date', end_date]
                
            elif script == 'calculate_FR_diff_v3.py':
                # 步驟3: 差異計算
                cmd = ['python', script, '--start-date', start_date, '--end-date', end_date, '--exchanges'] + exchanges
                
            elif script == 'calculate_FR_return_list_v2.py':
                # 步驟4: 收益計算
                cmd = ['python', script, '--start-date', start_date, '--end-date', end_date]
                
            elif script == 'strategy_ranking_v2.py':
                # 步驟5: 策略排名
                cmd = ['python', script, '--start_date', start_date, '--end_date', end_date]
                if strategy == 'all':
                    # 不添加 --strategies 參數，會自動選擇全部策略
                    pass
                else:
                    cmd.extend(['--strategies', strategy])
                    
            elif script == 'draw_return_metrics_v3.py':
                # 步驟6: 收益圖表生成
                cmd = ['python', script, '--output-dir', 'data/picture']
                    
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
    
    def run_complete_process(self, exchanges: List[str], top_n: int, start_date: str, end_date: str, strategy: str):
        """執行完整流程"""
        print("\n🚀 開始執行完整的資金費率分析流程")
        print("=" * 60)
        
        overall_start_time = time.time()
        
        for i in range(len(self.steps)):
            success = self.run_step(i, exchanges, top_n, start_date, end_date, strategy)
            
            if not success:
                print(f"\n❌ 步驟 {i + 1} 失敗，流程中斷")
                return False
        
        overall_end_time = time.time()
        total_elapsed = overall_end_time - overall_start_time
        
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
  python master_controller.py --exchanges binance bybit --top_n 50 --start_date 2025-07-01 --end_date 2025-07-09 --strategy original
  python master_controller.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09 --strategy all
        '''
    )
    
    parser.add_argument('--exchanges', nargs='+', choices=['binance', 'bybit', 'okx', 'gate'],
                        help='要分析的交易所 (可選多個)')
    parser.add_argument('--top_n', type=int, help='市值排名前N名')
    parser.add_argument('--start_date', help='開始日期 (YYYY-MM-DD)')
    parser.add_argument('--end_date', help='結束日期 (YYYY-MM-DD)')
    parser.add_argument('--strategy', help='策略選擇 (策略名稱、編號或 all)')
    
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
        start_date = args.start_date
        end_date = args.end_date
        
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
    
    # 獲取用戶確認
    confirm = input("\n是否繼續執行? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes', '是']:
        print("👋 用戶取消執行")
        return
    
    # 執行完整流程
    success = controller.run_complete_process(exchanges, top_n, start_date, end_date, strategy)
    
    if success:
        print("\n🎊 資金費率分析完成！")
        print("💡 你可以使用 view_database_simple.py 查看結果")
        print("📊 收益圖表已保存到 data/picture/ 目錄")
    else:
        print("\n💥 分析過程中出現錯誤，請檢查日誌")

if __name__ == "__main__":
    main() 