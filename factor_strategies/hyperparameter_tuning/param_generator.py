#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
參數組合生成器
負責根據配置文件生成策略配置組合
"""

import itertools
import random
import json
import os
from datetime import datetime
from typing import List, Dict, Any


class ParameterGenerator:
    """參數組合生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化參數生成器
        :param config: 配置字典
        """
        self.config = config
        self.parameters = config['parameters']
        self.execution = config['execution']
        
        # 計算參數空間大小
        self.total_combinations = self._calculate_total_combinations()
        
    def _calculate_total_combinations(self) -> int:
        """計算總組合數"""
        factors_count = len(self.parameters['available_factors'])
        windows_count = len(self.parameters['windows'])
        input_cols_count = len(self.parameters['input_columns'])
        min_data_count = len(self.parameters['min_data_days'])
        skip_days_count = len(self.parameters['skip_first_n_days'])
        weight_methods_count = len(self.parameters['weight_methods'])
        
        # 計算因子組合數（1個因子 + 2個因子組合 + 3個因子組合）
        min_factors = self.parameters['min_factors_per_strategy']
        max_factors = self.parameters['max_factors_per_strategy']
        
        factor_combinations = 0
        for n in range(min_factors, max_factors + 1):
            # 計算 C(factors_count, n) - 組合數學
            factor_combinations += self._combination_count(factors_count, n)
        
        total = (factor_combinations * 
                windows_count * 
                input_cols_count * 
                min_data_count * 
                skip_days_count * 
                weight_methods_count)
        
        return total
    
    def _combination_count(self, n: int, k: int) -> int:
        """計算組合數 C(n,k)"""
        if k > n or k < 0:
            return 0
        if k == 0 or k == n:
            return 1
        
        # 使用動態規劃計算組合數
        result = 1
        for i in range(min(k, n - k)):
            result = result * (n - i) // (i + 1)
        return result
    
    def generate_all_combinations(self) -> List[Dict[str, Any]]:
        """生成所有可能的參數組合"""
        all_combinations = []
        
        # 生成因子組合
        factors = self.parameters['available_factors']
        min_factors = self.parameters['min_factors_per_strategy']
        max_factors = self.parameters['max_factors_per_strategy']
        
        factor_combinations = []
        for n in range(min_factors, max_factors + 1):
            factor_combinations.extend(itertools.combinations(factors, n))
        
        # 生成所有參數組合
        for factor_combo in factor_combinations:
            for window in self.parameters['windows']:
                for input_col in self.parameters['input_columns']:
                    for min_data in self.parameters['min_data_days']:
                        for skip_days in self.parameters['skip_first_n_days']:
                            for weight_method in self.parameters['weight_methods']:
                                
                                # 創建策略配置
                                strategy_config = self._create_strategy_config(
                                    factors=list(factor_combo),
                                    window=window,
                                    input_column=input_col,
                                    min_data_days=min_data,
                                    skip_first_n_days=skip_days,
                                    weight_method=weight_method
                                )
                                
                                all_combinations.append(strategy_config)
        
        return all_combinations
    
    def generate_sample_combinations(self, n_samples: int) -> List[Dict[str, Any]]:
        """生成隨機抽樣的參數組合"""
        if n_samples >= self.total_combinations:
            print(f"⚠️  請求的樣本數 ({n_samples}) 大於等於總組合數 ({self.total_combinations})")
            print("🔄 改為生成所有組合...")
            return self.generate_all_combinations()
        
        # 生成所有組合後隨機抽樣
        all_combinations = self.generate_all_combinations()
        return random.sample(all_combinations, n_samples)
    
    def _create_strategy_config(self, factors: List[str], window: int, 
                              input_column: str, min_data_days: int,
                              skip_first_n_days: int, weight_method: str) -> Dict[str, Any]:
        """創建單個策略配置"""
        
        # 生成策略ID
        strategy_id = self._generate_strategy_id(factors, window, input_column, 
                                               min_data_days, skip_first_n_days, weight_method)
        
        # 創建因子配置
        factor_configs = []
        for factor in factors:
            factor_config = {
                'function': factor,
                'window': window,
                'input_column': input_column
            }
            factor_configs.append(factor_config)
        
        # 創建完整的策略配置
        strategy_config = {
            'strategy_id': strategy_id,
            'strategy_name': f"HyperTuned_{strategy_id}",
            'data_requirements': {
                'min_data_days': min_data_days,
                'skip_first_n_days': skip_first_n_days
            },
            'factors': factor_configs,
            'scoring': {
                'method': weight_method,
                'weights': 'auto'  # 根據method自動計算
            },
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'generator_version': '1.0',
                'total_factors': len(factors),
                'window': window,
                'input_column': input_column
            }
        }
        
        return strategy_config
    
    def _generate_strategy_id(self, factors: List[str], window: int, 
                            input_column: str, min_data_days: int,
                            skip_first_n_days: int, weight_method: str) -> str:
        """生成策略ID"""
        
        # 簡化因子名稱
        factor_abbr = []
        for factor in factors:
            if 'trend' in factor:
                factor_abbr.append('TR')
            elif 'sharpe' in factor:
                factor_abbr.append('SR')
            elif 'std' in factor:
                factor_abbr.append('ST')
            elif 'win' in factor:
                factor_abbr.append('WR')
            elif 'drawdown' in factor:
                factor_abbr.append('DD')
            elif 'sortino' in factor:
                factor_abbr.append('SO')
            else:
                factor_abbr.append(factor[:2].upper())
        
        factor_str = '_'.join(factor_abbr)
        
        # 簡化權重方法
        weight_abbr = {
            'equal': 'EQ',
            'factor_score_weighted': 'FS',
            'inverse_correlation': 'IC'
        }.get(weight_method, 'UK')
        
        # 簡化輸入列
        input_abbr = input_column.replace('roi_', '').upper()
        
        strategy_id = f"{factor_str}_W{window}_{input_abbr}_D{min_data_days}_S{skip_first_n_days}_{weight_abbr}"
        
        return strategy_id
    
    def save_strategies_to_files(self, strategies: List[Dict[str, Any]], 
                               output_dir: str) -> List[str]:
        """將策略配置保存到文件"""
        os.makedirs(output_dir, exist_ok=True)
        saved_files = []
        
        for i, strategy in enumerate(strategies):
            filename = f"strategy_{strategy['strategy_id']}.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(strategy, f, indent=2, ensure_ascii=False)
            
            saved_files.append(filepath)
            
            # 每100個策略輸出一次進度
            if (i + 1) % 100 == 0:
                print(f"📝 已保存 {i + 1}/{len(strategies)} 個策略配置...")
        
        return saved_files
    
    def get_space_info(self) -> Dict[str, Any]:
        """獲取參數空間信息"""
        return {
            'total_combinations': self.total_combinations,
            'factors_count': len(self.parameters['available_factors']),
            'windows_count': len(self.parameters['windows']),
            'input_columns_count': len(self.parameters['input_columns']),
            'min_data_days_count': len(self.parameters['min_data_days']),
            'skip_days_count': len(self.parameters['skip_first_n_days']),
            'weight_methods_count': len(self.parameters['weight_methods']),
            'factor_combination_range': f"{self.parameters['min_factors_per_strategy']}-{self.parameters['max_factors_per_strategy']}"
        }


def main():
    """測試函數"""
    import yaml
    
    # 載入配置
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 創建生成器
    generator = ParameterGenerator(config)
    
    # 顯示參數空間信息
    space_info = generator.get_space_info()
    print("📊 參數空間信息:")
    for key, value in space_info.items():
        print(f"  - {key}: {value}")
    
    # 生成策略配置
    if config['execution']['mode'] == 'exhaustive':
        strategies = generator.generate_all_combinations()
        print(f"🎯 窮舉模式: 生成了 {len(strategies)} 個策略配置")
    else:
        n_strategies = config['execution']['n_strategies']
        strategies = generator.generate_sample_combinations(n_strategies)
        print(f"🎲 抽樣模式: 生成了 {len(strategies)} 個策略配置")
    
    # 顯示前3個策略示例
    print("\n📋 策略配置示例:")
    for i, strategy in enumerate(strategies[:3]):
        print(f"\n策略 {i+1}: {strategy['strategy_id']}")
        print(f"  - 因子: {[f['function'] for f in strategy['factors']]}")
        print(f"  - 窗口: {strategy['factors'][0]['window']}")
        print(f"  - 輸入列: {strategy['factors'][0]['input_column']}")
        print(f"  - 最小數據天數: {strategy['data_requirements']['min_data_days']}")


if __name__ == "__main__":
    main() 