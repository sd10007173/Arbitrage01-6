"""
因子策略執行腳本 (Run Factor Strategies) - 智能日期偵測版本

此腳本提供完整的命令行界面來執行因子策略系統，具備智能日期偵測功能。
參考 strategy_ranking.py 的設計，支持單日、日期範圍、所有日期等多種處理模式。

使用方法：
    python factor_strategies/run_factor_strategies.py                    # 預設處理所有可用日期
    python factor_strategies/run_factor_strategies.py --date 2025-01-31 # 處理單個日期
    python factor_strategies/run_factor_strategies.py --start_date 2025-01-01 --end_date 2025-01-31 # 日期範圍
    python factor_strategies/run_factor_strategies.py --all             # 明確指定所有日期
    python factor_strategies/run_factor_strategies.py --strategy cerebrum_core # 指定策略

主要特性：
- 智能從 return_metrics 表檢測可用日期範圍
- 支持單日、日期範圍、所有日期的處理模式
- 結果保存到 strategy_ranking 表（與既有系統整合）
- 完整的日期和數據驗證
- 統一的批量處理邏輯
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import argparse

# 添加父目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from factor_strategies.factor_engine import FactorEngine
from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES
from database_operations import DatabaseManager

def print_header():
    """打印程式標題"""
    print("\n" + "="*60)
    print("🧠 因子策略系統 (Factor Strategy System)")
    print("   智能日期偵測版本 - 參考 strategy_ranking.py 設計")
    print("="*60)

def get_available_dates_from_database():
    """
    從數據庫獲取所有可用的日期
    參考 strategy_ranking.py 的實現
    
    Returns:
        list: 可用日期字符串列表 (YYYY-MM-DD 格式)
    """
    try:
        # 使用與 FactorEngine 相同的數據庫路徑
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        db_path = os.path.join(project_root, "data", "funding_rate.db")
        
        db = DatabaseManager(db_path)
        with db.get_connection() as conn:
            query = "SELECT DISTINCT date FROM return_metrics ORDER BY date"
            result = pd.read_sql_query(query, conn)
        
        if result.empty:
            print("📊 數據庫中沒有 return_metrics 數據")
            return []
        
        dates = result['date'].tolist()
        print(f"📊 數據庫中找到 {len(dates)} 個可用日期")
        print(f"   日期範圍: {dates[0]} 到 {dates[-1]}")
        
        return dates
        
    except Exception as e:
        print(f"❌ 獲取可用日期時出錯: {e}")
        return []

def generate_date_range(start_date, end_date):
    """
    生成日期範圍
    參考 strategy_ranking.py 的實現
    
    Args:
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
    
    Returns:
        list: 日期字符串列表
    """
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    dates = []
    current_dt = start_dt
    
    while current_dt <= end_dt:
        dates.append(current_dt.strftime('%Y-%m-%d'))
        current_dt += timedelta(days=1)
    
    return dates

def print_available_strategies():
    """顯示所有可用策略"""
    print("\n📋 可用的因子策略:")
    print("-" * 50)
    for i, (key, config) in enumerate(FACTOR_STRATEGIES.items(), 1):
        print(f"{i:2d}. {key} - {config['name']}")

def select_strategies_interactively():
    """
    交互式選擇策略
    參考 strategy_ranking.py 的邏輯
    
    Returns:
        list: 選中的策略名稱列表
    """
    print_available_strategies()
    
    while True:
        strategy_input = input("\n請選擇要執行的策略 (輸入策略名稱、編號，或 'all' 執行所有策略): ").strip()
        
        if strategy_input.lower() == 'all':
            return list(FACTOR_STRATEGIES.keys())
        elif strategy_input in FACTOR_STRATEGIES:
            return [strategy_input]
        else:
            # 嘗試按編號選擇
            try:
                strategies = list(FACTOR_STRATEGIES.keys())
                choice_num = int(strategy_input)
                if 1 <= choice_num <= len(strategies):
                    return [strategies[choice_num - 1]]
                else:
                    print(f"❌ 請輸入 1-{len(strategies)} 之間的數字，或策略名稱，或 'all'")
            except ValueError:
                print(f"❌ 無效輸入。可用策略: {list(FACTOR_STRATEGIES.keys())} 或 'all'")

def run_strategy_for_date(engine: FactorEngine, strategy_name: str, target_date: str):
    """
    為特定日期執行單個策略
    
    Args:
        engine: FactorEngine 實例
        strategy_name: 策略名稱
        target_date: 目標日期
        
    Returns:
        bool: 是否執行成功
    """
    try:
        # 預檢查數據是否充足
        is_sufficient, message = engine.check_data_sufficiency(strategy_name, target_date)
        
        if not is_sufficient:
            print(f"⚠️ 跳過 {target_date}: {message}")
            return False
        
        # 執行策略
        result = engine.run_strategy(strategy_name, target_date)
        
        if not result.empty:
            print(f"✅ {target_date}: {len(result)} 個交易對")
            return True
        else:
            print(f"❌ {target_date}: 沒有結果")
            return False
            
    except Exception as e:
        print(f"❌ {target_date}: 執行失敗 - {e}")
        return False

def process_date_with_selected_strategies(target_date, selected_strategies):
    """
    處理指定日期的所有選中策略
    參考 strategy_ranking.py 的邏輯
    
    Args:
        target_date: 目標日期
        selected_strategies: 策略列表
        
    Returns:
        int: 成功執行的策略數量
    """
    print(f"\n📅 處理日期: {target_date}")
    
    try:
        engine = FactorEngine()
    except Exception as e:
        print(f"❌ 初始化 FactorEngine 失敗: {e}")
        return 0
    
    success_count = 0
    
    for strategy_name in selected_strategies:
        print(f"🚀 執行策略: {strategy_name}")
        
        if run_strategy_for_date(engine, strategy_name, target_date):
            success_count += 1
    
    if success_count > 0:
        print(f"✅ 日期 {target_date} 完成: {success_count}/{len(selected_strategies)} 個策略成功")
    else:
        print(f"❌ 日期 {target_date}: 沒有策略成功執行")
    
    return success_count

def main():
    """主函數 - 智能日期偵測版本"""
    parser = argparse.ArgumentParser(description='因子策略執行系統 - 智能日期偵測版本')
    parser.add_argument('--date', help='指定日期 (YYYY-MM-DD)')
    parser.add_argument('--start_date', help='開始日期 (YYYY-MM-DD)')
    parser.add_argument('--end_date', help='結束日期 (YYYY-MM-DD)')
    parser.add_argument('--all', action='store_true', help='處理所有可用日期')
    parser.add_argument('--strategy', help='指定策略名稱 (或 "all" 執行所有策略)')
    parser.add_argument('--auto', action='store_true', help='自動模式 (不互動選擇)')
    
    args = parser.parse_args()
    
    print_header()
    
    # 確定要處理的策略
    selected_strategies = []
    
    if args.strategy:
        # 命令行指定策略
        if args.strategy == 'all':
            selected_strategies = list(FACTOR_STRATEGIES.keys())
            print(f"✅ 命令行指定: 所有策略 ({len(selected_strategies)} 個)")
        elif args.strategy in FACTOR_STRATEGIES:
            selected_strategies = [args.strategy]
            print(f"✅ 命令行指定策略: {args.strategy}")
        else:
            print(f"❌ 策略 {args.strategy} 不存在")
            print(f"可用策略: {list(FACTOR_STRATEGIES.keys())}")
            return
    elif args.auto:
        # 自動模式 - 處理所有策略
        selected_strategies = list(FACTOR_STRATEGIES.keys())
        print("🤖 自動模式：處理所有策略")
    else:
        # 互動式選擇策略
        selected_strategies = select_strategies_interactively()
        
        if not selected_strategies:
            return
    
    # 確定要處理的日期
    dates_to_process = []
    
    if args.date:
        dates_to_process = [args.date]
        print(f"📅 指定日期: {args.date}")
    elif args.start_date and args.end_date:
        # 生成日期範圍
        dates_to_process = generate_date_range(args.start_date, args.end_date)
        print(f"📅 生成日期範圍: {args.start_date} 到 {args.end_date} ({len(dates_to_process)} 天)")
    elif args.all:
        dates_to_process = get_available_dates_from_database()
        print(f"📅 處理所有可用日期: {len(dates_to_process)} 天")
    else:
        # 預設處理所有可用日期（參考 strategy_ranking.py 的邏輯）
        print("沒有指定日期參數，預設處理所有可用日期...")
        dates_to_process = get_available_dates_from_database()
        
        if not dates_to_process:
            print("❌ 沒有找到任何 return_metrics 數據")
            print("請先運行 calculate_FR_return_list_v2.py 生成收益數據")
            print("\n可用參數:")
            print("  --date YYYY-MM-DD  (處理單個日期)")
            print("  --start_date YYYY-MM-DD --end_date YYYY-MM-DD  (處理日期範圍)")
            print("  --all  (處理所有可用日期)")
            print("  --strategy 策略名稱  (指定特定策略)")
            print("  --auto  (自動模式，處理所有策略)")
            return
    
    if not dates_to_process:
        print("❌ 沒有找到要處理的日期")
        return
    
    # 執行摘要
    print(f"\n📊 執行摘要:")
    print(f"   日期數: {len(dates_to_process)}")
    print(f"   策略數: {len(selected_strategies)}")
    print(f"   總組合: {len(dates_to_process) * len(selected_strategies)}")
    
    if len(dates_to_process) <= 10:
        print(f"   日期: {', '.join(dates_to_process)}")
    else:
        print(f"   日期範圍: {dates_to_process[0]} 到 {dates_to_process[-1]}")
    
    print(f"   策略: {', '.join(selected_strategies)}")
    
    # 大量處理提醒
    total_combinations = len(dates_to_process) * len(selected_strategies)
    if total_combinations > 50:
        confirm = input(f"\n⚠️ 將處理 {total_combinations} 個(日期,策略)組合，可能需要較長時間。是否繼續? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消執行")
            return
    
    # 處理每個日期
    print(f"\n🚀 開始執行...")
    total_successful = 0
    total_dates_processed = 0
    
    for date in dates_to_process:
        successful = process_date_with_selected_strategies(date, selected_strategies)
        if successful > 0:
            total_dates_processed += 1
            total_successful += successful
    
    print(f"\n🎉 所有處理完成！")
    print(f"   處理了 {total_dates_processed} 個日期")
    print(f"   成功處理 {total_successful} 個策略")
    
    # 顯示最新結果
    if total_successful > 0 and dates_to_process:
        print(f"\n📊 最新結果預覽:")
        try:
            # 使用與 FactorEngine 相同的數據庫路徑
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            db_path = os.path.join(project_root, "data", "funding_rate.db")
            db = DatabaseManager(db_path)
            
            latest_date = dates_to_process[-1]
            latest_strategy = selected_strategies[0]
            
            # 獲取最新結果
            result = db.get_latest_ranking(latest_strategy, top_n=5)
            
            if not result.empty:
                print(f"策略: {latest_strategy} (前5名)")
                print("-" * 50)
                print(f"{'排名':<4} {'交易對':<20} {'分數':<12}")
                print("-" * 50)
                
                for _, row in result.iterrows():
                    print(f"{row['rank_position']:<4} {row['trading_pair']:<20} "
                          f"{row['final_ranking_score']:<12.6f}")
            else:
                print("❌ 沒有找到最新結果")
                
        except Exception as e:
            print(f"❌ 查看結果失敗: {e}")

if __name__ == "__main__":
    main() 