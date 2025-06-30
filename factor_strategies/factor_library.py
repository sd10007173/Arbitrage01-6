"""
因子計算函式庫 (Factor Library) - 數據庫版本

此檔案包含所有因子計算的純數學函式。
每個函式都接收一個 pandas Series (代表時間序列數據) 和可選的參數，
並返回一個單一的浮點數值作為因子分數。

這些函式是無狀態的，且與任何特定的策略或數據源無關。

數據庫版本修改：
- 輸入數據來自 return_metrics 表的各個ROI欄位
- 支持 roi_1d, roi_7d, roi_14d, roi_30d 等不同時間週期的數據
- 函式保持純數學計算，不涉及數據庫操作
"""

import pandas as pd
import numpy as np
from scipy.stats import linregress

def calculate_trend_slope(series: pd.Series, **kwargs) -> float:
    """
    計算累積回報序列的線性回歸斜率。
    用於衡量長期趨勢的方向和強度。

    Args:
        series (pd.Series): 一段時間內的回報率序列 (例如 'roi_1d')。

    Returns:
        float: 計算出的回歸線斜率。正值表示上升趋势，負值表示下降趋势。
               如果數據不足，返回 np.nan。
    
    計算邏輯：
        1. 將回報率序列轉換為累積回報
        2. 對累積回報進行線性回歸
        3. 返回回歸線的斜率
    """
    if len(series) < 2:
        return np.nan
    
    # 確保 series 中的 NaN 值被處理
    series = series.dropna()
    if len(series) < 2:
        return np.nan

    # 計算累積回報
    cumulative_return = series.cumsum()
    time_index = np.arange(len(cumulative_return))
    
    # 使用scipy.stats.linregress計算斜率，它高效且穩定
    slope, _, _, _, _ = linregress(time_index, cumulative_return)
    
    return slope

def calculate_sharpe_ratio(series: pd.Series, annualizing_factor: int = 365, max_sharpe: float = 1000.0, **kwargs) -> float:
    """
    計算年化夏普比率。
    衡量每單位風險的超額回報，是風險調整後收益的重要指標。

    Args:
        series (pd.Series): 回報率序列。
        annualizing_factor (int): 年化係數 (日數據為365，週數據為52等)。
        max_sharpe (float): 夏普比率的上限，避免極值影響標準化。

    Returns:
        float: 年化夏普比率。值越高表示風險調整後收益越好。
               如果標準差為0，返回有限的高值而非無窮大。
    
    計算邏輯：
        1. 計算平均回報率
        2. 計算回報率標準差
        3. 夏普比率 = (平均回報 / 標準差) * sqrt(年化係數)
        4. 限制在合理範圍內，避免極值
    """
    # 確保 series 中的 NaN 值被處理
    series = series.dropna()
    if series.empty:
        return np.nan
        
    mean_return = series.mean()
    std_dev = series.std()

    if std_dev == 0 or np.isnan(std_dev):
        # 如果波動為0，給予有限的高值而非無窮大
        # 避免極值影響Z-Score標準化
        return max_sharpe if mean_return > 0 else -max_sharpe if mean_return < 0 else 0.0

    sharpe_ratio = (mean_return / std_dev) * np.sqrt(annualizing_factor)
    
    # 限制夏普比率在合理範圍內
    return np.clip(sharpe_ratio, -max_sharpe, max_sharpe)

def calculate_inv_std_dev(series: pd.Series, epsilon: float = 1e-9, high_score: float = 1e9, **kwargs) -> float:
    """
    計算回報率標準差的倒數，作為穩定性指標。
    穩定性越高（波動越小），分數越高。

    Args:
        series (pd.Series): 回報率序列。
        epsilon (float): 防止除零的極小值。
        high_score (float): 當標準差極小時給予的高分數。

    Returns:
        float: 穩定性分數。值越高表示越穩定。
    
    計算邏輯：
        1. 如果平均回報為負或零，穩定性無意義，返回0
        2. 如果標準差極小，給予高分數
        3. 否則返回 1/標準差
    """
    series = series.dropna()
    if series.empty:
        return 0.0 # 空數據返回 0

    mean_return = series.mean()
    
    # 如果平均回報為負或零，穩定性無意義，返回 0
    if mean_return <= 0:
        return 0.0

    std_dev = series.std()
    
    # 如果波動為0且平均回報為正，給予極高的、但有限的穩定性分數
    if std_dev < epsilon:
        return high_score

    return 1 / std_dev

def calculate_win_rate(series: pd.Series, **kwargs) -> float:
    """
    計算勝率，即回報大於0的天數所佔的比例。
    衡量策略獲利的頻率。

    Args:
        series (pd.Series): 回報率序列。

    Returns:
        float: 勝率 (介於0和1之間)。1表示100%獲利，0表示從未獲利。
    
    計算邏輯：
        1. 統計回報率大於0的天數
        2. 勝率 = 獲利天數 / 總天數
    """
    # 確保 series 中的 NaN 值被處理
    series = series.dropna()
    if len(series) == 0:
        return 0.0

    winning_days = (series > 0).sum()
    return winning_days / len(series)

def calculate_max_drawdown(series: pd.Series, **kwargs) -> float:
    """
    計算最大回撤。
    衡量從峰值到谷值的最大損失。

    Args:
        series (pd.Series): 回報率序列。

    Returns:
        float: 最大回撤比例（負值）。值越接近0表示回撤越小。
    
    計算邏輯：
        1. 計算累積回報
        2. 計算滾動最大值（峰值）
        3. 計算當前值相對於峰值的回撤
        4. 返回最大回撤值
    """
    series = series.dropna()
    if series.empty:
        return 0.0
    
    # 計算累積回報
    cumulative_return = (1 + series).cumprod()
    
    # 計算滾動最大值
    running_max = cumulative_return.expanding().max()
    
    # 計算回撤
    drawdown = (cumulative_return - running_max) / running_max
    
    # 返回最大回撤（負值）
    return drawdown.min()

def calculate_sortino_ratio(series: pd.Series, annualizing_factor: int = 365, max_sortino: float = 1000.0, **kwargs) -> float:
    """
    計算索提諾比率。
    類似夏普比率，但只考慮下行風險（負回報的標準差）。

    Args:
        series (pd.Series): 回報率序列。
        annualizing_factor (int): 年化係數。
        max_sortino (float): 索提諾比率的上限，避免極值影響標準化。

    Returns:
        float: 索提諾比率。值越高表示風險調整後收益越好。
    
    計算邏輯：
        1. 計算平均回報率
        2. 計算負回報的標準差（下行風險）
        3. 索提諾比率 = (平均回報 / 下行標準差) * sqrt(年化係數)
        4. 限制在合理範圍內，避免極值
    """
    series = series.dropna()
    if series.empty:
        return np.nan
    
    mean_return = series.mean()
    
    # 只考慮負回報
    negative_returns = series[series < 0]
    
    if len(negative_returns) == 0:
        # 沒有負回報，給予有限的高值而非無窮大
        return max_sortino if mean_return > 0 else -max_sortino if mean_return < 0 else 0.0
    
    downside_std = negative_returns.std()
    
    if downside_std == 0 or np.isnan(downside_std):
        return max_sortino if mean_return > 0 else -max_sortino if mean_return < 0 else 0.0
    
    sortino_ratio = (mean_return / downside_std) * np.sqrt(annualizing_factor)
    
    # 限制索提諾比率在合理範圍內
    return np.clip(sortino_ratio, -max_sortino, max_sortino)

# ==========================================
# Z-Score 標準化相關函數
# ==========================================

def calculate_mean_std(values: list) -> tuple[float, float]:
    """
    計算數值列表的平均值和標準差，處理極值情況
    
    Args:
        values (list): 數值列表
        
    Returns:
        tuple[float, float]: (平均值, 標準差)
    """
    if not values:
        return 0.0, 1.0
    
    # 過濾掉 NaN 值和無窮大值
    valid_values = [v for v in values if not (np.isnan(v) or np.isinf(v))]
    
    if not valid_values:
        return 0.0, 1.0
        
    mean_val = np.mean(valid_values)
    std_val = np.std(valid_values)
    
    # 檢查結果是否為有限值
    if not np.isfinite(mean_val):
        mean_val = 0.0
    
    if not np.isfinite(std_val) or std_val == 0:
        std_val = 1.0
        
    return mean_val, std_val

def apply_zscore(raw_value: float, mean_val: float, std_val: float) -> float:
    """
    對單一數值應用Z-Score標準化
    
    Args:
        raw_value (float): 原始數值
        mean_val (float): 平均值
        std_val (float): 標準差
        
    Returns:
        float: 標準化後的Z-Score值
    """
    if np.isnan(raw_value):
        return 0.0
        
    if std_val == 0:
        return 0.0
        
    return (raw_value - mean_val) / std_val

def standardize_factor_scores(all_factor_scores: dict) -> tuple[dict, dict]:
    """
    對所有交易對的各因子分數進行Z-Score標準化
    
    Args:
        all_factor_scores (dict): 格式為 {trading_pair: {factor_name: score}}
        
    Returns:
        tuple[dict, dict]: (標準化後的分數字典, 各因子統計信息字典)
        
    格式：
        標準化分數: {trading_pair: {factor_name: {'raw': raw_value, 'z_score': z_value}}}
        統計信息: {factor_name: {'mean': mean_val, 'std': std_val}}
    """
    if not all_factor_scores:
        return {}, {}
    
    # 獲取所有因子名稱
    factor_names = set()
    for scores in all_factor_scores.values():
        factor_names.update(scores.keys())
    
    # 計算各因子的統計特徵
    factor_stats = {}
    for factor_name in factor_names:
        values = []
        for scores in all_factor_scores.values():
            if factor_name in scores:
                values.append(scores[factor_name])
        
        mean_val, std_val = calculate_mean_std(values)
        factor_stats[factor_name] = {'mean': mean_val, 'std': std_val}
    
    # 標準化各交易對的各因子分數
    standardized_scores = {}
    for trading_pair, scores in all_factor_scores.items():
        standardized_scores[trading_pair] = {}
        
        for factor_name in factor_names:
            if factor_name in scores:
                raw_value = scores[factor_name]
                mean_val = factor_stats[factor_name]['mean']
                std_val = factor_stats[factor_name]['std']
                z_score = apply_zscore(raw_value, mean_val, std_val)
                
                standardized_scores[trading_pair][factor_name] = {
                    'raw': raw_value,
                    'z_score': z_score
                }
            else:
                # 如果該交易對缺少該因子，設為0
                standardized_scores[trading_pair][factor_name] = {
                    'raw': np.nan,
                    'z_score': 0.0
                }
    
    return standardized_scores, factor_stats

# --- 您未來可以在此處添加更多因子計算函式 ---
# 例如: Calmar Ratio, Information Ratio, Beta, Alpha 等
#
# def calculate_calmar_ratio(series: pd.Series, **kwargs) -> float:
#     """計算卡瑪比率 = 年化收益率 / 最大回撤"""
#     ...
#
# def calculate_information_ratio(series: pd.Series, benchmark_series: pd.Series, **kwargs) -> float:
#     """計算信息比率 = 超額收益 / 跟踪誤差"""
#     ... 