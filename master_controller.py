#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資金費率分析系統總控程式
=============================

功能：自動化執行完整的資金費率分析流程
包含：交易所支持檢查 → 資金費率獲取 → 差異計算 → 收益計算 → 策略排名

使用方式：
- 交互式模式：python master_controller.py
- 命令行模式：python master_controller.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09
"""

import subprocess
import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

class MasterController:
    """資金費率分析系統總控制器"""
    
    def __init__(self):
        self.supported_exchanges = ['binance', 'bybit', 'okx', 'gate']
        self.steps = [
            {
                'name': '交易所支持檢查',
                'script': 'exchange_trading_pair_v10.py',
                'description': '檢查交易對在各交易所的支持狀態和上市日期'
            },
            {
                'name': '資金費率歷史獲取',
                'script': 'fetch_FR_history_group_v2.py',
                'description': '批量獲取交易對的資金費率歷史數據'
            },
            {
                'name': '資金費率差異計算',
                'script': 'calculate_FR_diff_v3.py',
                'description': '計算不同交易所間的資金費率差異'
            },
            {
                'name': '收益指標計算',
                'script': 'calculate_FR_return_list_v2.py',
                'description': '計算多時間框架的收益指標'
            },
            {
                'name': '策略排名生成',
                'script': 'strategy_ranking_v2.py',
                'description': '基於收益指標生成策略排名'
            }
        ]
        
    def print_header(self):
        """打印程式標題"""
        print("=" * 80)
        print("🚀 資金費率分析系統總控程式")
        print("=" * 80)
        print("📋 功能：自動化執行完整的資金費率分析流程")
        print("🔄 包含：交易所支持 → 資金費率獲取 → 差異計算 → 收益計算 → 策略排名")
        print("=" * 80)
        
    def validate_inputs(self, exchanges: List[str], start_date: str, end_date: str, top_n: int) -> Tuple[bool, str]:
        """驗證用戶輸入參數"""
        
        # 驗證交易所
        invalid_exchanges = [ex for ex in exchanges if ex not in self.supported_exchanges]
        if invalid_exchanges:
            return False, f"不支持的交易所: {invalid_exchanges}。支持的交易所: {self.supported_exchanges}"
        
        # 驗證日期格式
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return False, "日期格式錯誤，請使用 YYYY-MM-DD 格式"
        
        # 驗證日期邏輯
        if start_dt >= end_dt:
            return False, "開始日期必須早於結束日期"
        
        # 驗證日期範圍（不能太遠的未來）
        today = datetime.now()
        if end_dt > today + timedelta(days=1):
            return False, "結束日期不能超過明天"
        
        # 驗證市值排名
        if top_n <= 0 or top_n > 1000:
            return False, "市值排名必須在 1-1000 之間"
        
        return True, "參數驗證通過"
    
    def get_interactive_input(self) -> Tuple[List[str], str, str, int]:
        """交互式獲取用戶輸入"""
        print("\n🎯 請輸入分析參數：")
        print("-" * 40)
        
        # 獲取交易所
        exchanges = []
        while not exchanges:
            print(f"\n📋 支持的交易所: {', '.join(self.supported_exchanges)}")
            exchanges_input = input("請選擇交易所（用空格分隔，例如：binance bybit）: ").strip().lower()
            input_list = [ex.strip() for ex in exchanges_input.split() if ex.strip()]
            
            if not input_list:
                print("❌ 請至少選擇一個交易所")
                continue
                
            invalid_exchanges = [ex for ex in input_list if ex not in self.supported_exchanges]
            if invalid_exchanges:
                print(f"❌ 不支持的交易所: {invalid_exchanges}")
                continue
                
            exchanges = input_list
        
        # 獲取市值排名
        top_n = 0
        while top_n <= 0:
            try:
                top_n = int(input("\n📊 請輸入市值排名前幾名（例如：100）: ").strip())
                if top_n <= 0:
                    print("❌ 請輸入大於0的數字")
                elif top_n > 1000:
                    print("❌ 建議不超過1000，避免處理時間過長")
                    confirm = input("是否繼續？(y/n): ").strip().lower()
                    if confirm != 'y':
                        top_n = 0
            except ValueError:
                print("❌ 請輸入有效的數字")
        
        # 獲取日期範圍
        start_date = ""
        while not start_date:
            start_input = input("\n📅 請輸入開始日期（YYYY-MM-DD，例如：2025-07-01）: ").strip()
            try:
                datetime.strptime(start_input, '%Y-%m-%d')
                start_date = start_input
            except ValueError:
                print("❌ 日期格式錯誤，請使用 YYYY-MM-DD 格式")
        
        end_date = ""
        while not end_date:
            end_input = input("📅 請輸入結束日期（YYYY-MM-DD，例如：2025-07-09）: ").strip()
            try:
                end_dt = datetime.strptime(end_input, '%Y-%m-%d')
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                if end_dt <= start_dt:
                    print("❌ 結束日期必須晚於開始日期")
                    continue
                end_date = end_input
            except ValueError:
                print("❌ 日期格式錯誤，請使用 YYYY-MM-DD 格式")
        
        return exchanges, start_date, end_date, top_n
    
    def run_command(self, cmd: str, step_name: str) -> bool:
        """執行系統命令並處理結果"""
        print(f"\n🔄 執行中：{step_name}")
        print(f"📜 命令：{cmd}")
        print("-" * 60)
        
        start_time = time.time()
        
        try:
            # 執行命令
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=False,  # 讓輸出直接顯示
                text=True,
                cwd='.'  # 確保在當前目錄執行
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result.returncode == 0:
                print(f"\n✅ {step_name} 完成！耗時：{duration:.1f}秒")
                return True
            else:
                print(f"\n❌ {step_name} 失敗！退出碼：{result.returncode}")
                return False
                
        except Exception as e:
            print(f"\n❌ {step_name} 執行時發生錯誤：{e}")
            return False
    
    def confirm_execution(self, exchanges: List[str], start_date: str, end_date: str, top_n: int) -> bool:
        """確認執行參數"""
        print("\n" + "=" * 60)
        print("📋 執行計劃確認")
        print("=" * 60)
        print(f"🏢 交易所：{', '.join(exchanges)}")
        print(f"📊 市值排名：前 {top_n} 名")
        print(f"📅 日期範圍：{start_date} 到 {end_date}")
        
        days = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days
        print(f"⏱️  分析天數：{days} 天")
        
        print(f"\n🔄 將執行以下 {len(self.steps)} 個步驟：")
        for i, step in enumerate(self.steps, 1):
            print(f"  {i}. {step['name']} - {step['description']}")
        
        print("\n⚠️  注意事項：")
        print("• 整個過程可能需要較長時間，請耐心等待")
        print("• 執行過程中請勿中斷，避免數據不一致")
        print("• 建議在網絡穩定的環境下執行")
        
        while True:
            confirm = input("\n確認執行？(y/n): ").strip().lower()
            if confirm in ['y', 'yes']:
                return True
            elif confirm in ['n', 'no']:
                return False
            else:
                print("請輸入 y 或 n")
    
    def execute_pipeline(self, exchanges: List[str], start_date: str, end_date: str, top_n: int) -> bool:
        """執行完整的分析流程"""
        
        # 驗證參數
        is_valid, message = self.validate_inputs(exchanges, start_date, end_date, top_n)
        if not is_valid:
            print(f"❌ 參數驗證失敗：{message}")
            return False
        
        print(f"✅ {message}")
        
        # 確認執行
        if not self.confirm_execution(exchanges, start_date, end_date, top_n):
            print("❌ 用戶取消執行")
            return False
        
        print("\n" + "=" * 80)
        print("🚀 開始執行資金費率分析流程")
        print("=" * 80)
        
        pipeline_start_time = time.time()
        
        # 步驟1：交易所支持檢查
        cmd1 = f"python {self.steps[0]['script']} --exchanges {' '.join(exchanges)} --top_n {top_n}"
        if not self.run_command(cmd1, self.steps[0]['name']):
            print(f"❌ 流程在步驟1失敗，終止執行")
            return False
        
        # 步驟2：資金費率歷史獲取  
        cmd2 = f"python {self.steps[1]['script']} --exchanges {' '.join(exchanges)} --top_n {top_n} --start_date {start_date} --end_date {end_date}"
        if not self.run_command(cmd2, self.steps[1]['name']):
            print(f"❌ 流程在步驟2失敗，終止執行")
            return False
        
        # 步驟3：資金費率差異計算
        cmd3 = f"python {self.steps[2]['script']} --start-date {start_date} --end-date {end_date} --exchanges {' '.join(exchanges)}"
        if not self.run_command(cmd3, self.steps[2]['name']):
            print(f"❌ 流程在步驟3失敗，終止執行")
            return False
        
        # 步驟4：收益指標計算
        cmd4 = f"python {self.steps[3]['script']} --start-date {start_date} --end-date {end_date}"
        if not self.run_command(cmd4, self.steps[3]['name']):
            print(f"❌ 流程在步驟4失敗，終止執行")
            return False
        
        # 步驟5：策略排名生成
        cmd5 = f"python {self.steps[4]['script']} --start_date {start_date} --end_date {end_date}"
        if not self.run_command(cmd5, self.steps[4]['name']):
            print(f"❌ 流程在步驟5失敗，終止執行")
            return False
        
        # 流程完成
        pipeline_end_time = time.time()
        total_duration = pipeline_end_time - pipeline_start_time
        
        print("\n" + "=" * 80)
        print("🎉 資金費率分析流程執行完成！")
        print("=" * 80)
        print(f"⏱️  總耗時：{total_duration/60:.1f} 分鐘")
        print(f"🏢 交易所：{', '.join(exchanges)}")
        print(f"📊 交易對：市值前 {top_n} 名")
        print(f"📅 分析期間：{start_date} 到 {end_date}")
        print("\n💡 下一步建議：")
        print("• 查看 strategy_ranking 表獲取策略排名結果")
        print("• 使用 backtest_v5.py 進行策略回測")
        print("• 使用 draw_return_metrics.py 生成視覺化圖表")
        print("=" * 80)
        
        return True

def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description='資金費率分析系統總控程式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 交互式模式
  python master_controller.py
  
  # 命令行模式
  python master_controller.py --exchanges binance bybit --top_n 100 --start_date 2025-07-01 --end_date 2025-07-09
  
  # 單個交易所
  python master_controller.py --exchanges binance --top_n 50 --start_date 2025-07-01 --end_date 2025-07-03
        """
    )
    
    parser.add_argument('--exchanges', nargs='+',
                       choices=['binance', 'bybit', 'okx', 'gate'],
                       help='指定要分析的交易所（空格分隔）')
    
    parser.add_argument('--top_n', type=int,
                       help='市值排名前N名')
    
    parser.add_argument('--start_date', type=str,
                       help='開始日期，格式：YYYY-MM-DD')
    
    parser.add_argument('--end_date', type=str,
                       help='結束日期，格式：YYYY-MM-DD')
    
    args = parser.parse_args()
    
    # 創建控制器
    controller = MasterController()
    controller.print_header()
    
    # 檢查參數模式
    cmd_params = [args.exchanges, args.top_n, args.start_date, args.end_date]
    has_any_param = any(param is not None for param in cmd_params)
    has_all_params = all(param is not None for param in cmd_params)
    
    if has_any_param and not has_all_params:
        print("❌ 命令行模式需要提供所有參數：--exchanges, --top_n, --start_date, --end_date")
        print("💡 或者不提供任何參數使用交互式模式")
        parser.print_help()
        return
    
    try:
        if has_all_params:
            # 命令行模式
            print("🚀 命令行模式")
            success = controller.execute_pipeline(
                exchanges=args.exchanges,
                start_date=args.start_date,
                end_date=args.end_date,
                top_n=args.top_n
            )
        else:
            # 交互式模式
            print("🚀 交互式模式")
            exchanges, start_date, end_date, top_n = controller.get_interactive_input()
            success = controller.execute_pipeline(exchanges, start_date, end_date, top_n)
        
        # 設置退出碼
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用戶中斷執行")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程式執行時發生錯誤：{e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 