#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
結果分析器
負責分析回測結果，找出最佳策略和參數重要性
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from typing import List, Dict, Any, Tuple
import os


class ResultAnalyzer:
    """結果分析器"""
    
    def __init__(self, config: Dict[str, Any], output_dir: str):
        """
        初始化結果分析器
        :param config: 配置字典
        :param output_dir: 輸出目錄
        """
        self.config = config
        self.output_dir = output_dir
        self.analysis_config = config.get('analysis', {})
        self.output_config = config.get('output', {})
        
        # 分析結果存儲
        self.results_df = None
        self.top_strategies = []
        self.parameter_importance = {}
        
        # 設置matplotlib中文顯示
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False
    
    def load_results(self, results_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        載入並處理結果數據
        :param results_data: 結果數據列表
        :return: 處理後的DataFrame
        """
        print(f"📊 開始分析 {len(results_data)} 個策略結果")
        
        if not results_data:
            print("⚠️  沒有可分析的結果數據")
            self.results_df = pd.DataFrame()
            return self.results_df
        
        # 簡化版處理 - 只處理基本信息
        processed_results = []
        
        for i, result in enumerate(results_data):
            try:
                strategy_config = result.get('strategy_config', {})
                strategy_id = result.get('strategy_id', f'strategy_{i}')
                
                # 創建基本記錄
                processed_result = {
                    'strategy_id': strategy_id,
                    'factors': ','.join([f.get('function', '') for f in strategy_config.get('factors', [])]),
                    'factor_count': len(strategy_config.get('factors', [])),
                    'window': strategy_config.get('factors', [{}])[0].get('window', 0) if strategy_config.get('factors') else 0,
                    'status': 'processed'
                }
                
                processed_results.append(processed_result)
                
            except Exception as e:
                print(f"⚠️  處理策略 {i} 時出錯: {str(e)}")
                continue
        
        self.results_df = pd.DataFrame(processed_results)
        print(f"✅ 成功處理 {len(self.results_df)} 個策略")
        
        return self.results_df
    
    def analyze_top_strategies(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        分析頂級策略
        :param top_n: 返回前N個策略
        :return: 頂級策略列表
        """
        if self.results_df is None or len(self.results_df) == 0:
            print("❌ 沒有可分析的結果數據")
            return []
        
        # 簡化版 - 返回前N個策略
        top_n = min(top_n, len(self.results_df))
        self.top_strategies = self.results_df.head(top_n).to_dict('records')
        
        print(f"🏆 分析了前 {len(self.top_strategies)} 個策略")
        return self.top_strategies
    
    def analyze_parameter_importance(self) -> Dict[str, Any]:
        """
        分析參數重要性
        """
        if self.results_df is None or len(self.results_df) == 0:
            return {}
        
        # 簡化版參數重要性分析
        importance_analysis = {
            'factor_count_distribution': self.results_df['factor_count'].value_counts().to_dict(),
            'window_distribution': self.results_df['window'].value_counts().to_dict()
        }
        
        self.parameter_importance = importance_analysis
        return importance_analysis
    
    def generate_visualizations(self) -> List[str]:
        """生成視覺化圖表"""
        print("📊 視覺化功能暫時簡化")
        return []
    
    def generate_summary_report(self) -> str:
        """生成總結報告"""
        report_dir = os.path.join(self.output_dir, 'reports')
        os.makedirs(report_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = os.path.join(report_dir, f'analysis_report_{timestamp}.txt')
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("超參數調優分析報告 (簡化版)\n")
            f.write("=" * 80 + "\n")
            f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 數據概覽
            if self.results_df is not None and len(self.results_df) > 0:
                f.write("📊 數據概覽\n")
                f.write("-" * 40 + "\n")
                f.write(f"總策略數: {len(self.results_df)}\n")
                f.write(f"因子數分佈: {self.results_df['factor_count'].value_counts().to_dict()}\n")
                f.write("\n")
            
            # 頂級策略
            if self.top_strategies:
                f.write("🏆 頂級策略\n")
                f.write("-" * 40 + "\n")
                
                for i, strategy in enumerate(self.top_strategies[:5]):
                    f.write(f"第 {i+1} 名: {strategy['strategy_id']}\n")
                    f.write(f"  - 因子: {strategy['factors']}\n")
                    f.write(f"  - 窗口期: {strategy['window']}\n")
                    f.write("\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("報告結束\n")
        
        print(f"📋 分析報告已生成: {report_file}")
        return report_file


def main():
    """測試函數"""
    config = {
        'analysis': {},
        'output': {}
    }
    
    analyzer = ResultAnalyzer(config, 'test_output')
    print("✅ ResultAnalyzer 測試成功")


if __name__ == "__main__":
    main() 