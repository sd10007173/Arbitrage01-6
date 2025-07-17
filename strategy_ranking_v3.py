#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略排行榜生成模組 V3 - 數據完整性檢查版本
從數據庫讀取return_metrics數據，根據不同策略計算排名
輸出到數據庫: strategy_ranking表

=== V3 主要改進 ===
1. return_metrics 依賴檢查：確保依賴數據完整才執行
2. 策略數據完整性檢查：檢查每個策略的排名數據是否完整
3. 智能增量處理：只處理缺失的交易對排名，避免重複計算
4. 錯誤隔離：單個交易對排名失敗不影響其他交易對處理
5. 部分成功保存：成功的結果立即保存，失敗的記錄到日誌
6. 詳細錯誤追蹤：通過日誌文件清楚了解處理狀態
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
from ranking_config import RANKING_STRATEGIES, EXPERIMENTAL_CONFIGS
from ranking_engine import RankingEngine
import time
import os
import sys

# 添加數據庫支持
from database_operations import DatabaseManager

# 確保日誌目錄存在
os.makedirs("logs", exist_ok=True)

def log_error(message):
    """記錄錯誤信息到專用日誌文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "logs/strategy_ranking_v3_errors.log"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {message}\n")
    
    print(f"❌ {message}")

def log_info(message):
    """記錄一般信息到主日誌文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "logs/strategy_ranking_v3.log"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {message}\n")
    
    print(f"ℹ️ {message}")

def get_expected_pairs_from_return_metrics(date):
    """
    從 return_metrics 表獲取指定日期應該存在的交易對
    Args:
        date: 日期字符串 (YYYY-MM-DD)
    Returns:
        set: 交易對集合
    """
    try:
        db = DatabaseManager()
        
        query = """
            SELECT DISTINCT trading_pair
            FROM return_metrics 
            WHERE date = ?
        """
        
        with db.get_connection() as conn:
            result = pd.read_sql_query(query, conn, params=[date])
        
        if result.empty:
            return set()
        
        return set(result['trading_pair'].tolist())
        
    except Exception as e:
        log_error(f"獲取 {date} return_metrics 交易對失敗: {e}")
        return set()

def get_existing_strategy_pairs(strategy_name, date):
    """
    從 strategy_ranking 表獲取指定策略和日期實際存在的交易對
    Args:
        strategy_name: 策略名稱
        date: 日期字符串 (YYYY-MM-DD)
    Returns:
        set: 交易對集合
    """
    try:
        db = DatabaseManager()
        
        query = """
            SELECT DISTINCT trading_pair
            FROM strategy_ranking 
            WHERE strategy_name = ? AND date = ?
        """
        
        with db.get_connection() as conn:
            result = pd.read_sql_query(query, conn, params=[strategy_name, date])
        
        if result.empty:
            return set()
        
        return set(result['trading_pair'].tolist())
        
    except Exception as e:
        log_error(f"獲取 {strategy_name} {date} 現有策略交易對失敗: {e}")
        return set()

def validate_return_metrics_dependency(start_date, end_date):
    """
    驗證 return_metrics 數據是否完整，作為前置條件
    Args:
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
    Returns:
        bool: 是否通過依賴檢查
    """
    print("🔍 檢查 return_metrics 依賴完整性...")
    
    # 導入 v3 版本的完整性檢查函數
    try:
        from calculate_FR_return_list_v3 import check_data_completeness, generate_date_range
    except ImportError:
        log_error("無法導入 calculate_FR_return_list_v3 模組")
        return False
    
    incomplete_dates = []
    all_dates = generate_date_range(start_date, end_date)
    
    for date in all_dates:
        completeness = check_data_completeness(date)
        
        if not completeness['is_complete']:
            incomplete_dates.append({
                'date': date,
                'expected': completeness['expected_count'],
                'existing': completeness['existing_count'],
                'missing': completeness['missing_count']
            })
        else:
            print(f"   {date}: ✅ 完整 ({completeness['expected_count']} 個交易對)")
    
    if incomplete_dates:
        print("❌ return_metrics 數據不完整:")
        for item in incomplete_dates:
            print(f"   {item['date']}: {item['existing']}/{item['expected']} 個交易對 (缺失 {item['missing']} 個)")
        
        print(f"\n💡 請先運行: python calculate_FR_return_list_v3.py --start-date {start_date} --end-date {end_date}")
        print("🚫 由於依賴數據不完整，strategy_ranking_v3 停止執行")
        print("📋 修復步驟:")
        print("   1. 先運行 calculate_FR_return_list_v3.py 補充缺失數據")
        print("   2. 然後再運行 strategy_ranking_v3.py")
        return False
    
    print("✅ return_metrics 依賴檢查通過")
    return True

def check_strategy_data_completeness(strategy_name, date):
    """
    檢查指定策略和日期的數據完整性
    Args:
        strategy_name: 策略名稱
        date: 日期字符串 (YYYY-MM-DD)
    Returns:
        dict: {
            'date': str,
            'strategy_name': str,
            'expected_pairs': set,
            'existing_pairs': set,
            'missing_pairs': set,
            'is_complete': bool,
            'expected_count': int,
            'existing_count': int,
            'missing_count': int
        }
    """
    expected_pairs = get_expected_pairs_from_return_metrics(date)
    existing_pairs = get_existing_strategy_pairs(strategy_name, date)
    missing_pairs = expected_pairs - existing_pairs
    
    return {
        'date': date,
        'strategy_name': strategy_name,
        'expected_pairs': expected_pairs,
        'existing_pairs': existing_pairs,
        'missing_pairs': missing_pairs,
        'is_complete': len(missing_pairs) == 0,
        'expected_count': len(expected_pairs),
        'existing_count': len(existing_pairs),
        'missing_count': len(missing_pairs)
    }

def find_incomplete_strategy_data(strategy_name, start_date, end_date):
    """
    找到需要處理的策略排名數據
    Args:
        strategy_name: 策略名稱
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
    Returns:
        dict: {
            'date1': ['pair1', 'pair2'],  # 需要補充的交易對
            'date2': ['pair3', 'pair4'],  # 需要補充的交易對
        }
    """
    print(f"🔍 檢查策略 {strategy_name} 數據完整性...")
    
    # 導入必要的函數
    try:
        from calculate_FR_return_list_v3 import generate_date_range
    except ImportError:
        log_error("無法導入 calculate_FR_return_list_v3 模組")
        return {}
    
    incomplete_data = {}
    all_dates = generate_date_range(start_date, end_date)
    
    for date in all_dates:
        completeness = check_strategy_data_completeness(strategy_name, date)
        
        if not completeness['is_complete']:
            incomplete_data[date] = list(completeness['missing_pairs'])
            print(f"   {date}: {completeness['existing_count']}/{completeness['expected_count']} 個交易對 (缺失 {completeness['missing_count']} 個)")
        else:
            print(f"   {date}: ✅ 完整 ({completeness['expected_count']} 個交易對)")
    
    if incomplete_data:
        total_missing = sum(len(pairs) for pairs in incomplete_data.values())
        print(f"📊 策略 {strategy_name} 發現 {len(incomplete_data)} 個不完整日期，共缺失 {total_missing} 個交易對排名")
    else:
        print(f"✅ 策略 {strategy_name} 所有日期數據完整，無需處理")
    
    return incomplete_data

def load_fr_return_data_from_database(start_date=None, end_date=None, symbol=None):
    """
    從數據庫載入指定時間範圍內的return_metrics數據
    
    Args:
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        symbol: 交易對符號 (可選)
    
    Returns:
        pandas.DataFrame: 包含收益數據的DataFrame
    """
    try:
        print(f"🗄️ 正在從數據庫載入收益數據...")
        print(f"   時間範圍: {start_date or '所有'} 到 {end_date or '所有'}")
        if symbol:
            print(f"   交易對: {symbol}")
            
        db = DatabaseManager()
        
        # 一次性獲取所有數據
        df = db.get_return_metrics(start_date=start_date, end_date=end_date, trading_pair=symbol)
        
        if df.empty:
            print(f"📊 數據庫中沒有找到匹配的收益數據")
            return pd.DataFrame()
        
        # 直接在SQL查詢層面處理好欄位名是更優的做法，但為保持db_operations不變，這裡暫時保留
        db_to_csv_mapping = {
            'trading_pair': 'Trading_Pair',
            'date': 'Date',
            'return_1d': '1d_return', 'roi_1d': '1d_ROI',
            'return_2d': '2d_return', 'roi_2d': '2d_ROI',
            'return_7d': '7d_return', 'roi_7d': '7d_ROI',
            'return_14d': '14d_return', 'roi_14d': '14d_ROI',
            'return_30d': '30d_return', 'roi_30d': '30d_ROI',
            'return_all': 'all_return', 'roi_all': 'all_ROI'
        }
        df.rename(columns=db_to_csv_mapping, inplace=True)
        
        print(f"✅ 數據庫載入成功: {len(df)} 筆記錄")
        return df
        
    except Exception as e:
        print(f"❌ 從數據庫載入收益數據時出錯: {e}")
        return pd.DataFrame()

def generate_strategy_ranking_batch(df, strategy_name, strategy_config):
    """
    批量計算單個策略在多個日期上的排名
    
    Args:
        df: 包含多天return_metrics數據的DataFrame
        strategy_name: 策略名稱
        strategy_config: 策略配置
    
    Returns:
        DataFrame: 包含所有日期排名的DataFrame
    """
    if df.empty:
        return pd.DataFrame()
    
    print(f"📊 正在批量計算策略: {strategy_name}")

    ranking_engine = RankingEngine(strategy_name)

    # 定義每日計算函數
    def calculate_daily_ranking(daily_df):
        # 創建一個副本以避免 SettingWithCopyWarning
        daily_df_copy = daily_df.copy()
        
        # 使用RankingEngine計算排名
        ranked_df = ranking_engine.calculate_final_ranking(daily_df_copy)
        
        if ranked_df.empty:
            return None
        
        # 按分數降序排序並添加排名
        ranked_df = ranked_df.sort_values('final_ranking_score', ascending=False).reset_index(drop=True)
        ranked_df['Rank'] = range(1, len(ranked_df) + 1)
        return ranked_df

    # 按日期分組並應用每日計算函數
    # 使用 .copy() 確保我們操作的是數據副本
    all_rankings = df.copy().groupby('Date').apply(calculate_daily_ranking, include_groups=False).reset_index()
    
    # 刪除由 groupby 產生的 level_1 索引
    if 'level_1' in all_rankings.columns:
        all_rankings = all_rankings.drop(columns=['level_1'])
        
    print(f"   ✅ 策略 {strategy_name} 批量計算完成，共處理 {all_rankings['Date'].nunique()} 天, {len(all_rankings)} 條排名記錄")
    
    return all_rankings

def generate_strategy_ranking_for_specific_pairs(strategy_name, strategy_config, date, missing_pairs):
    """
    為指定日期的指定交易對生成策略排名
    Args:
        strategy_name: 策略名稱
        strategy_config: 策略配置
        date: 目標日期 (YYYY-MM-DD)
        missing_pairs: 要處理的交易對列表
    Returns:
        DataFrame: 排名結果
    """
    if not missing_pairs:
        return pd.DataFrame()
    
    print(f"   📊 處理 {len(missing_pairs)} 個交易對: {date}")
    
    # 獲取該日期的所有 return_metrics 數據
    try:
        db = DatabaseManager()
        
        query = """
            SELECT *
            FROM return_metrics 
            WHERE date = ?
        """
        
        with db.get_connection() as conn:
            daily_data = pd.read_sql_query(query, conn, params=[date])
        
        if daily_data.empty:
            log_error(f"{date} 沒有 return_metrics 數據")
            return pd.DataFrame()
        
        # 重命名列以匹配現有邏輯
        db_to_csv_mapping = {
            'trading_pair': 'Trading_Pair',
            'date': 'Date',
            'return_1d': '1d_return', 'roi_1d': '1d_ROI',
            'return_2d': '2d_return', 'roi_2d': '2d_ROI',
            'return_7d': '7d_return', 'roi_7d': '7d_ROI',
            'return_14d': '14d_return', 'roi_14d': '14d_ROI',
            'return_30d': '30d_return', 'roi_30d': '30d_ROI',
            'return_all': 'all_return', 'roi_all': 'all_ROI'
        }
        daily_data.rename(columns=db_to_csv_mapping, inplace=True)
        
        # 過濾出需要處理的交易對
        daily_data = daily_data[daily_data['Trading_Pair'].isin(missing_pairs)]
        
        if daily_data.empty:
            log_error(f"{date} 沒有需要處理的交易對數據")
            return pd.DataFrame()
        
        # 使用 RankingEngine 計算排名 - 批量處理所有缺失的交易對
        ranking_engine = RankingEngine(strategy_name)
        
        try:
            # 批量處理所有缺失的交易對，這樣 RankingEngine 能正確進行標準化
            ranked_df = ranking_engine.calculate_final_ranking(daily_data)
            
            if ranked_df.empty:
                log_error(f"{date} 排名計算結果為空")
                return pd.DataFrame()
            
            # 添加排名位置
            ranked_df['Rank'] = range(1, len(ranked_df) + 1)
            
            final_result = ranked_df
            successful_pairs = ranked_df['Trading_Pair'].tolist()
            failed_pairs = [pair for pair in missing_pairs if pair not in successful_pairs]
            
            print(f"   ✅ 成功處理 {len(successful_pairs)} 個交易對")
            
            if failed_pairs:
                print(f"   ❌ 失敗 {len(failed_pairs)} 個交易對: {failed_pairs}")
                log_info(f"{strategy_name} {date} 失敗的交易對: {failed_pairs}")
                
        except Exception as e:
            log_error(f"{date} 排名計算失敗: {e}")
            return pd.DataFrame()
        
        return final_result
        
    except Exception as e:
        log_error(f"處理 {strategy_name} {date} 時出錯: {e}")
        return pd.DataFrame()

def process_incomplete_strategy_data_v3(strategy_name, strategy_config, incomplete_data):
    """
    處理不完整的策略排名數據，支持錯誤隔離和部分成功保存
    Args:
        strategy_name: 策略名稱
        strategy_config: 策略配置
        incomplete_data: {date: [missing_pairs]} 格式的字典
    Returns:
        dict: 處理結果統計
    """
    if not incomplete_data:
        print(f"✅ 策略 {strategy_name} 沒有需要處理的不完整數據")
        return {'total_dates': 0, 'successful_dates': 0, 'partial_dates': 0, 'failed_dates': 0}
    
    print(f"🔄 開始處理策略 {strategy_name} 的 {len(incomplete_data)} 個不完整日期...")
    
    db = DatabaseManager()
    summary = {
        'total_dates': len(incomplete_data),
        'successful_dates': 0,
        'partial_dates': 0,
        'failed_dates': 0,
        'details': {}
    }
    
    for date, missing_pairs in incomplete_data.items():
        print(f"\n📅 處理日期: {date} ({len(missing_pairs)} 個缺失交易對)")
        
        # 處理該日期的缺失交易對
        results_df = generate_strategy_ranking_for_specific_pairs(
            strategy_name, strategy_config, date, missing_pairs
        )
        
        # 統計處理結果
        success_count = len(results_df) if not results_df.empty else 0
        fail_count = len(missing_pairs) - success_count
        
        # 保存成功的結果 - 使用直接插入避免覆蓋現有數據
        if not results_df.empty:
            try:
                # 準備數據庫插入格式
                db_df = results_df.copy()
                db_df['strategy_name'] = strategy_name
                
                # 列名映射
                column_mapping = {
                    'Trading_Pair': 'trading_pair',
                    'Rank': 'rank_position',
                    'Date': 'date'
                }
                db_df.rename(columns=column_mapping, inplace=True)
                
                # 確保必需列存在
                required_cols = ['strategy_name', 'trading_pair', 'date', 'final_ranking_score', 'rank_position']
                if not all(col in db_df.columns for col in required_cols):
                    log_error(f"缺少必需的數據庫列。需要: {required_cols}, 實際: {db_df.columns.tolist()}")
                    fail_count = len(missing_pairs)
                    success_count = 0
                else:
                    # 添加缺失列的默認值
                    if 'final_combination_value' not in db_df.columns:
                        db_df['final_combination_value'] = ''
                    
                    # 直接插入到數據庫，使用 INSERT OR REPLACE 避免衝突
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        
                        # 準備插入數據
                        records = []
                        for _, row in db_df.iterrows():
                            records.append((
                                row['strategy_name'],
                                row['trading_pair'],
                                row['date'],
                                row['final_ranking_score'],
                                row['rank_position'],
                                row.get('final_combination_value', '')
                            ))
                        
                        # 使用 INSERT OR REPLACE 避免重複
                        insert_query = """
                            INSERT OR REPLACE INTO strategy_ranking 
                            (strategy_name, trading_pair, date, final_ranking_score, rank_position, final_combination_value)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """
                        cursor.executemany(insert_query, records)
                        conn.commit()
                        
                        log_info(f"{strategy_name} {date} 成功保存 {len(records)} 個交易對排名")
                        
            except Exception as e:
                log_error(f"{strategy_name} {date} 保存數據時出錯: {e}")
                fail_count = len(missing_pairs)
                success_count = 0
        
        # 更新統計
        if fail_count == 0:
            summary['successful_dates'] += 1
            summary['details'][date] = f'完全成功 ({success_count}/{len(missing_pairs)})'
        elif success_count > 0:
            summary['partial_dates'] += 1
            summary['details'][date] = f'部分成功 ({success_count}/{len(missing_pairs)})'
        else:
            summary['failed_dates'] += 1
            summary['details'][date] = f'完全失敗 (0/{len(missing_pairs)})'
        
        print(f"   📊 {date} 結果: 成功 {success_count}, 失敗 {fail_count}")
    
    return summary

def save_strategy_ranking_to_database(ranked_df, strategy_name):
    """
    將策略排行榜批量保存到數據庫
    
    Args:
        ranked_df: 包含多天排名的DataFrame
        strategy_name: 策略名稱
    
    Returns:
        保存的記錄數
    """
    if ranked_df.empty:
        print("⚠️ 排行榜數據為空，無法保存")
        return 0
    
    try:
        db = DatabaseManager()
        
        print(f"💾 準備將 {len(ranked_df)} 條策略排行記錄插入數據庫...")
        
        db_df = ranked_df.copy()
        db_df['strategy_name'] = strategy_name
        
        # 列名映射
        column_mapping = {
            'Trading_Pair': 'trading_pair',
            'Rank': 'rank_position',
            'Date': 'date'
        }
        db_df.rename(columns=column_mapping, inplace=True)
        
        # 確保必需列存在
        required_cols = ['strategy_name', 'trading_pair', 'date', 'final_ranking_score', 'rank_position']
        if not all(col in db_df.columns for col in required_cols):
            print(f"❌ 缺少必需的數據庫列。需要: {required_cols}, 實際: {db_df.columns.tolist()}")
            return 0
        
        # 保存到數據庫 (假設 db 操作支持批量)
        inserted_count = db.insert_strategy_ranking(db_df, strategy_name)
        print(f"✅ 數據庫插入成功: {inserted_count} 條記錄")
        
        return inserted_count
        
    except Exception as e:
        print(f"❌ 保存策略排行榜到數據庫時出錯: {e}")
        return 0

def select_strategies_interactively():
    """
    互動式選擇策略
    
    Returns:
        list: 選擇的策略名稱列表
    """
    # 合併主要策略和實驗性策略
    all_strategies = {**RANKING_STRATEGIES, **EXPERIMENTAL_CONFIGS}
    available_strategies = list(all_strategies.keys())
    
    print("\n🎯 可用策略:")
    print("="*50)
    
    # 顯示主要策略
    main_count = 0
    for i, strategy in enumerate(RANKING_STRATEGIES.keys(), 1):
        strategy_info = RANKING_STRATEGIES[strategy]
        print(f"{i}. {strategy:20s} - {strategy_info['name']}")
        main_count = i
    
    # 顯示實驗性策略
    if EXPERIMENTAL_CONFIGS:
        print("\n🧪 實驗性策略:")
        print("-" * 30)
        for i, strategy in enumerate(EXPERIMENTAL_CONFIGS.keys(), main_count + 1):
            strategy_info = EXPERIMENTAL_CONFIGS[strategy]
            print(f"{i}. {strategy:20s} - {strategy_info['name']}")
    
    print(f"{len(available_strategies)+1}. 全部策略 (all)")
    print("0. 退出")
    
    while True:
        try:
            choice = input(f"\n請輸入策略編號 (1-{len(available_strategies)+1}, 或 0 退出): ").strip()
            
            if choice == '0':
                print("已取消執行")
                return []
            elif choice == str(len(available_strategies)+1) or choice.lower() == 'all':
                print(f"✅ 已選擇全部 {len(available_strategies)} 個策略")
                return available_strategies
            elif choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(available_strategies):
                    selected_strategy = available_strategies[choice_num-1]
                    # 檢查策略在哪個配置中
                    if selected_strategy in RANKING_STRATEGIES:
                        strategy_info = RANKING_STRATEGIES[selected_strategy]
                    else:
                        strategy_info = EXPERIMENTAL_CONFIGS[selected_strategy]
                    print(f"✅ 已選擇策略: {selected_strategy} - {strategy_info['name']}")
                    return [selected_strategy]
                else:
                    print(f"無效的編號: {choice_num}")
            else:
                print(f"無效的輸入: {choice}")
        except ValueError:
            print("請輸入數字。")

def main():
    """主執行程序 - 數據完整性檢查版本 v3"""
    start_time = time.time()
    
    parser = argparse.ArgumentParser(description="策略排行榜生成模組 V3 - 數據完整性檢查版本")
    parser.add_argument("--start_date", help="開始日期 (YYYY-MM-DD)")
    parser.add_argument("--end_date", help="結束日期 (YYYY-MM-DD)")
    parser.add_argument("--symbol", help="指定單一交易對 (可選)")
    parser.add_argument("--strategies", help="指定策略，用逗號分隔 (可選)")
    parser.add_argument("--check-only", action='store_true', help="只檢查完整性，不進行處理")
    parser.add_argument("--use-legacy", action='store_true', help="使用舊版處理方式 (不推薦)")
    
    args = parser.parse_args()
    
    # 1. 確定日期範圍
    start_date = args.start_date
    end_date = args.end_date

    # 如果用戶沒有指定日期，則從數據庫自動檢測範圍
    if not start_date or not end_date:
        print("ℹ️ 未指定日期範圍，正在從數據庫自動檢測...")
        db = DatabaseManager()
        db_start, db_end = db.get_return_metrics_date_range()
        
        if db_start and db_end:
            start_date = start_date or db_start
            end_date = end_date or db_end
            print(f"   ✅ 自動檢測到日期範圍: {start_date} 到 {end_date}")
        else:
            print("⚠️ 無法自動檢測日期範圍，且未手動指定。請檢查 return_metrics 表中是否有數據。")
            # 使用過去30天作為備用方案
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=29)).strftime('%Y-%m-%d')
            print(f"   -> 將使用預設備用範圍: {start_date} 到 {end_date}")
    
    print("="*50)
    print("🚀 策略排行榜生成器 V3 啟動 🚀")
    print(f"時間範圍: {start_date} 到 {end_date}")
    print("="*50)
    
    # V3 新增：依賴檢查
    if not validate_return_metrics_dependency(start_date, end_date):
        sys.exit(1)  # 依賴檢查失敗，退出程序
    
    # 2. 確定要運行的策略
    if args.strategies:
        selected_strategies = [s.strip() for s in args.strategies.split(',')]
    else:
        selected_strategies = select_strategies_interactively()

    if not selected_strategies:
        return # 用戶選擇退出

    # 3. 使用舊版邏輯（向後兼容）
    if args.use_legacy:
        print("⚠️ 使用舊版處理方式 (性能較低)")
        print("💡 建議移除 --use-legacy 參數以使用 v3 數據完整性檢查")
        
        # 一次性加載所有需要的數據
        all_data = load_fr_return_data_from_database(start_date=start_date, end_date=end_date, symbol=args.symbol)

        if all_data.empty:
            print("沒有數據可供處理，腳本終止。")
            return

        # 4. 逐一計算並保存每個策略的排名
        for strategy_name in selected_strategies:
            # 檢查策略在哪個配置中
            if strategy_name in RANKING_STRATEGIES:
                strategy_config = RANKING_STRATEGIES[strategy_name]
            elif strategy_name in EXPERIMENTAL_CONFIGS:
                strategy_config = EXPERIMENTAL_CONFIGS[strategy_name]
            else:
                print(f"⚠️ 找不到名為 '{strategy_name}' 的策略配置，跳過。")
                continue

            # 批量計算排名
            ranked_df = generate_strategy_ranking_batch(all_data, strategy_name, strategy_config)

            # 批量保存到數據庫
            if not ranked_df.empty:
                save_strategy_ranking_to_database(ranked_df, strategy_name)
            
            print("-"*50)
    else:
        # V3 新邏輯：數據完整性檢查處理
        print("🚀 使用 v3 數據完整性檢查版本")
        
        # 4. 逐一處理每個策略
        for strategy_name in selected_strategies:
            print(f"\n🎯 處理策略: {strategy_name}")
            
            # 檢查策略在哪個配置中
            if strategy_name in RANKING_STRATEGIES:
                strategy_config = RANKING_STRATEGIES[strategy_name]
            elif strategy_name in EXPERIMENTAL_CONFIGS:
                strategy_config = EXPERIMENTAL_CONFIGS[strategy_name]
            else:
                log_error(f"找不到名為 '{strategy_name}' 的策略配置")
                continue

            # 檢查該策略的數據完整性
            incomplete_data = find_incomplete_strategy_data(strategy_name, start_date, end_date)
            
            if not incomplete_data:
                print(f"✅ 策略 {strategy_name} 數據完整，無需處理")
                continue
            
            # 如果只是檢查完整性
            if args.check_only:
                total_missing = sum(len(pairs) for pairs in incomplete_data.values())
                print(f"📋 策略 {strategy_name} 完整性檢查結果:")
                print(f"   不完整日期: {len(incomplete_data)} 個")
                print(f"   缺失交易對排名: {total_missing} 個")
                
                for date, missing_pairs in incomplete_data.items():
                    print(f"   {date}: 缺失 {len(missing_pairs)} 個交易對")
                continue
            
            # 處理不完整的數據
            summary = process_incomplete_strategy_data_v3(strategy_name, strategy_config, incomplete_data)
            
            print(f"📊 策略 {strategy_name} 處理完成:")
            print(f"   完全成功: {summary['successful_dates']} 個日期")
            print(f"   部分成功: {summary['partial_dates']} 個日期")
            print(f"   完全失敗: {summary['failed_dates']} 個日期")
            
            if summary['details']:
                print(f"   📋 詳細結果:")
                for date, detail in summary['details'].items():
                    print(f"      {date}: {detail}")
            
            print("-"*50)
        
        # 如果只是檢查完整性，提示用戶
        if args.check_only:
            print("\n💡 如需修復，請移除 --check-only 參數重新運行")

    end_time_val = time.time()
    print(f"\n🎉 所有策略處理完成！總耗時: {end_time_val - start_time:.2f} 秒")

if __name__ == "__main__":
    main() 