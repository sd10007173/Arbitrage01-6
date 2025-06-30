"""
因子計算引擎 (Factor Engine) - 數據庫版本

此檔案是因子策略系統的核心引擎，負責：
1. 從數據庫讀取 return_metrics 數據
2. 根據策略配置計算各個因子分數
3. 組合因子分數生成最終排名
4. 將結果寫入數據庫

數據庫版本修改：
- 數據來源：return_metrics 表
- 數據輸出：strategy_ranking 表
- 使用 database_operations.py 進行數據庫操作
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import sys
import os

# 添加父目錄到 Python 路徑，以便導入核心模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_operations import DatabaseManager
from factor_strategies.factor_library import *
from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES

class FactorEngine:
    """因子計算引擎"""
    
    def __init__(self, db_path: str = None):
        # 如果沒有指定路徑，使用項目根目錄下的數據庫
        if db_path is None:
            # 獲取項目根目錄路徑
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            db_path = os.path.join(project_root, "data", "funding_rate.db")
        """
        初始化因子引擎
        
        Args:
            db_path: 數據庫文件路徑
        """
        self.db_manager = DatabaseManager(db_path)
        self.factor_functions = self._load_factor_functions()
        print(f"✅ 因子引擎初始化完成，數據庫: {db_path}")
    
    def _load_factor_functions(self) -> Dict[str, callable]:
        """載入所有可用的因子計算函數"""
        return {
            'calculate_trend_slope': calculate_trend_slope,
            'calculate_sharpe_ratio': calculate_sharpe_ratio,
            'calculate_inv_std_dev': calculate_inv_std_dev,
            'calculate_win_rate': calculate_win_rate,
            'calculate_max_drawdown': calculate_max_drawdown,
            'calculate_sortino_ratio': calculate_sortino_ratio,
        }
    
    def get_strategy_data(self, strategy_config: Dict[str, Any], target_date: str = None) -> pd.DataFrame:
        """
        獲取策略計算所需的數據
        
        Args:
            strategy_config: 策略配置
            target_date: 目標日期，None則使用最新日期
            
        Returns:
            包含所需數據的 DataFrame
        """
        # 獲取數據要求
        data_req = strategy_config['data_requirements']
        min_days = data_req['min_data_days']
        skip_days = data_req['skip_first_n_days']
        
        # 如果沒有指定日期，獲取最新日期
        if target_date is None:
            start_date, end_date = self.db_manager.get_return_metrics_date_range()
            if not end_date:
                raise ValueError("數據庫中沒有 return_metrics 數據")
            target_date = end_date
        
        # 計算需要的日期範圍
        target_date_obj = pd.to_datetime(target_date)
        start_date_obj = target_date_obj - pd.Timedelta(days=min_days + skip_days + 30)  # 額外緩衝
        start_date_str = start_date_obj.strftime('%Y-%m-%d')
        
        # 從數據庫獲取數據
        df = self.db_manager.get_return_metrics(
            start_date=start_date_str,
            end_date=target_date
        )
        
        if df.empty:
            raise ValueError(f"沒有找到日期範圍 {start_date_str} 到 {target_date} 的數據")
        
        # 轉換日期格式
        df['date'] = pd.to_datetime(df['date'])
        
        # 過濾掉新上線的幣種（跳過前N天）
        if skip_days > 0:
            # 獲取每個交易對的首次出現日期
            first_dates = df.groupby('trading_pair')['date'].min()
            valid_pairs = []
            
            for pair, first_date in first_dates.items():
                days_since_first = (target_date_obj - first_date).days
                if days_since_first >= skip_days:
                    valid_pairs.append(pair)
            
            df = df[df['trading_pair'].isin(valid_pairs)]
            print(f"📊 過濾後剩餘 {len(valid_pairs)} 個交易對 (跳過上線少於{skip_days}天的)")
        
        return df
    
    def calculate_factor_for_trading_pair(self, pair_data: pd.DataFrame, factor_config: Dict[str, Any]) -> float:
        """
        為單個交易對計算因子分數
        
        Args:
            pair_data: 單個交易對的歷史數據
            factor_config: 因子配置
            
        Returns:
            因子分數
        """
        function_name = factor_config['function']
        window = factor_config['window']
        input_col = factor_config['input_col']
        params = factor_config.get('params', {})
        
        # 檢查函數是否存在
        if function_name not in self.factor_functions:
            raise ValueError(f"未知的因子函數: {function_name}")
        
        # 檢查輸入列是否存在
        if input_col not in pair_data.columns:
            raise ValueError(f"數據中缺少列: {input_col}")
        
        # 獲取最近的數據窗口
        recent_data = pair_data.tail(window)
        
        # 檢查數據點數量，至少需要2個數據點才能計算趨勢
        min_required_points = max(2, min(window // 4, 3))  # 動態調整最小數據點要求
        if len(recent_data) < min_required_points:
            return np.nan
        
        # 獲取輸入序列
        input_series = recent_data[input_col]
        
        # 調用因子計算函數
        factor_function = self.factor_functions[function_name]
        score = factor_function(input_series, **params)
        
        return score
    
    def calculate_strategy_ranking(self, strategy_name: str, target_date: str = None) -> pd.DataFrame:
        """
        計算策略排名
        
        Args:
            strategy_name: 策略名稱
            target_date: 目標日期
            
        Returns:
            包含排名結果的 DataFrame
        """
        if strategy_name not in FACTOR_STRATEGIES:
            raise ValueError(f"未知的策略: {strategy_name}")
        
        strategy_config = FACTOR_STRATEGIES[strategy_name]
        print(f"🧮 開始計算因子策略: {strategy_config['name']}")
        
        # 獲取數據
        df = self.get_strategy_data(strategy_config, target_date)
        
        if target_date is None:
            target_date = df['date'].max().strftime('%Y-%m-%d')
        
        # 獲取所有交易對
        trading_pairs = df['trading_pair'].unique()
        print(f"📊 計算 {len(trading_pairs)} 個交易對的因子分數...")
        
        # 計算每個交易對的因子分數
        results = []
        
        for pair in trading_pairs:
            pair_data = df[df['trading_pair'] == pair].sort_values('date')
            
            # 計算所有因子分數
            factor_scores = {}
            component_scores = {}
            
            for factor_name, factor_config in strategy_config['factors'].items():
                try:
                    score = self.calculate_factor_for_trading_pair(pair_data, factor_config)
                    factor_scores[factor_name] = score
                    component_scores[factor_name] = score
                except Exception as e:
                    print(f"⚠️ 計算 {pair} 的因子 {factor_name} 時出錯: {e}")
                    factor_scores[factor_name] = np.nan
                    component_scores[factor_name] = np.nan
            
            # 檢查是否有有效的因子分數
            valid_scores = [s for s in factor_scores.values() if not np.isnan(s)]
            if not valid_scores:
                continue
            
            # 計算最終排名分數
            final_score, calculation_record = self._calculate_final_score(factor_scores, strategy_config['ranking_logic'])
            
            results.append({
                'trading_pair': pair,
                'date': target_date,
                'final_ranking_score': final_score,
                'component_scores': component_scores,
                'long_term_score': final_score,  # 暫時使用最終分數
                'short_term_score': final_score,  # 暫時使用最終分數
                'combined_roi_z_score': final_score,  # 暫時使用最終分數
                'final_combination_value': calculation_record
            })
        
        # 轉換為 DataFrame
        result_df = pd.DataFrame(results)
        
        if result_df.empty:
            print("⚠️ 沒有計算出任何有效的因子分數")
            return result_df
        
        # 排序並添加排名
        result_df = result_df.sort_values('final_ranking_score', ascending=False)
        result_df['rank_position'] = range(1, len(result_df) + 1)
        
        print(f"✅ 完成因子策略計算，共 {len(result_df)} 個交易對")
        return result_df
    
    def _calculate_final_score(self, factor_scores: Dict[str, float], ranking_logic: Dict[str, Any]) -> tuple[float, str]:
        """
        計算最終排名分數並生成計算過程記錄
        
        Args:
            factor_scores: 各因子分數字典
            ranking_logic: 排名邏輯配置
            
        Returns:
            (最終分數, 計算過程記錄)
        """
        indicators = ranking_logic['indicators']
        weights = ranking_logic['weights']
        
        if len(indicators) != len(weights):
            raise ValueError("因子數量與權重數量不匹配")
        
        # 計算加權分數和生成計算記錄
        weighted_sum = 0.0
        total_weight = 0.0
        calculation_parts = []
        
        for indicator, weight in zip(indicators, weights):
            if indicator in factor_scores:
                score = factor_scores[indicator]
                if not np.isnan(score):
                    weighted_value = score * weight
                    weighted_sum += weighted_value
                    total_weight += weight
                    
                    # 生成計算記錄部分
                    calculation_parts.append(f"{indicator}: {score:.5f} × {weight:.2f} = {weighted_value:.5f}")
                else:
                    calculation_parts.append(f"{indicator}: NaN × {weight:.2f} = 0.0")
            else:
                calculation_parts.append(f"{indicator}: Missing × {weight:.2f} = 0.0")
        
        if total_weight == 0:
            calculation_record = " | ".join(calculation_parts) + " | Final: No valid factors"
            return np.nan, calculation_record
        
        # 正規化權重
        final_score = weighted_sum / total_weight
        
        # 生成最終的計算記錄
        calculation_record = " | ".join(calculation_parts) + f" | Final: {' + '.join([p.split(' = ')[1] for p in calculation_parts if 'NaN' not in p and 'Missing' not in p])} = {final_score:.5f}"
        
        return final_score, calculation_record
    
    def check_data_sufficiency(self, strategy_name: str, target_date: str = None) -> tuple[bool, str]:
        """
        檢查策略所需的數據是否充足
        
        Args:
            strategy_name: 策略名稱
            target_date: 目標日期
            
        Returns:
            (是否充足, 詳細信息)
        """
        if strategy_name not in FACTOR_STRATEGIES:
            return False, f"未知的策略: {strategy_name}"
        
        strategy_config = FACTOR_STRATEGIES[strategy_name]
        data_req = strategy_config['data_requirements']
        min_days = data_req['min_data_days']
        skip_days = data_req['skip_first_n_days']
        
        # 獲取目標日期
        if target_date is None:
            start_date, end_date = self.db_manager.get_return_metrics_date_range()
            if not end_date:
                return False, "數據庫中沒有 return_metrics 數據"
            target_date = end_date
        
        target_date_obj = pd.to_datetime(target_date)
        
        # 檢查數據庫中的數據範圍
        start_date, end_date = self.db_manager.get_return_metrics_date_range()
        if not end_date:
            return False, "數據庫中沒有 return_metrics 數據"
        
        earliest_date = pd.to_datetime(start_date)
        latest_date = pd.to_datetime(end_date)
        
        # 檢查目標日期是否在數據範圍內
        if target_date_obj > latest_date:
            return False, f"目標日期 {target_date} 超出數據範圍 (最新: {end_date})"
        
        # 檢查是否有足夠的歷史數據
        # 計算實際可用天數（包含起始和結束日期）
        available_days = (target_date_obj - earliest_date).days + 1
        required_days = min_days + skip_days
        
        if available_days < required_days:
            return False, f"數據量不足：策略需要 {required_days} 天數據，但只有 {available_days} 天可用 (從 {start_date} 到 {target_date})"
        
        # 檢查是否有交易對符合skip_days條件
        if skip_days > 0:
            # 快速檢查：計算從數據開始日期到目標日期的天數
            days_from_start = (target_date_obj - earliest_date).days + 1
            if days_from_start <= skip_days:
                return False, f"無交易對符合條件：所有交易對上線時間不足 {skip_days} 天 (實際: {days_from_start} 天)"
        
        # 檢查各因子所需的最大窗口
        max_window = 0
        factor_windows = []
        for factor_name, factor_config in strategy_config['factors'].items():
            window = factor_config['window']
            max_window = max(max_window, window)
            factor_windows.append(f"{factor_name}({window}天)")
        
        # 檢查是否有足夠的數據來計算最大窗口的因子
        total_required_days = max_window + skip_days
        if available_days < total_required_days:
            return False, f"因子計算數據不足：最大因子窗口需要 {total_required_days} 天，但只有 {available_days} 天可用。因子窗口: {', '.join(factor_windows)}"
        
        return True, f"數據充足：可用數據 {available_days} 天，滿足策略要求"

    def run_strategy(self, strategy_name: str, target_date: str = None, save_to_db: bool = True) -> pd.DataFrame:
        """
        執行策略計算並保存結果
        
        Args:
            strategy_name: 策略名稱
            target_date: 目標日期
            save_to_db: 是否保存到數據庫
            
        Returns:
            排名結果 DataFrame
        """
        print(f"\n🚀 執行因子策略: {strategy_name}")
        
        # 預檢查數據是否充足
        is_sufficient, message = self.check_data_sufficiency(strategy_name, target_date)
        if not is_sufficient:
            print(f"❌ 數據量檢查失敗: {message}")
            print("💡 建議:")
            print("   • 使用較晚的日期 (如最新日期)")
            print("   • 選擇數據要求較低的策略 (如 test_factor_simple)")
            print("   • 確保有足夠的歷史數據")
            return pd.DataFrame()  # 返回空的 DataFrame
        
        print(f"✅ 數據量檢查通過: {message}")
        
        # 計算排名
        result_df = self.calculate_strategy_ranking(strategy_name, target_date)
        
        if result_df.empty:
            print("❌ 策略計算失敗，沒有結果")
            return result_df
        
        # 保存到數據庫 (使用既有的 strategy_ranking 表)
        if save_to_db:
            count = self.db_manager.insert_strategy_ranking(result_df, strategy_name)
            print(f"💾 已保存 {count} 條記錄到 strategy_ranking 表")
        
        # 顯示前10名
        print(f"\n📊 {strategy_name} 策略前10名:")
        print("排名 | 交易對 | 最終分數")
        print("-" * 40)
        for _, row in result_df.head(10).iterrows():
            print(f"{row['rank_position']:2d}   | {row['trading_pair']:<20} | {row['final_ranking_score']:.6f}")
        
        return result_df
    
    def run_all_strategies(self, target_date: str = None) -> Dict[str, pd.DataFrame]:
        """
        執行所有策略
        
        Args:
            target_date: 目標日期
            
        Returns:
            所有策略結果的字典
        """
        results = {}
        
        for strategy_name in FACTOR_STRATEGIES.keys():
            try:
                result = self.run_strategy(strategy_name, target_date)
                results[strategy_name] = result
            except Exception as e:
                print(f"❌ 策略 {strategy_name} 執行失敗: {e}")
                results[strategy_name] = pd.DataFrame()
        
        return results

if __name__ == "__main__":
    # 測試因子引擎
    engine = FactorEngine()
    
    # 測試簡單策略
    try:
        result = engine.run_strategy('test_factor_simple')
        print(f"\n✅ 測試完成，得到 {len(result)} 個結果")
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc() 