"""
參數空間生成器 - ParameterSpaceGenerator
實現BR-001: 參數空間窮舉功能
"""

import logging
import random
import itertools
from typing import Dict, Any, List, Optional, Iterator
from dataclasses import dataclass
import numpy as np

from ..config import ConfigManager, ParameterConfig

@dataclass
class StrategyConfig:
    """策略配置類"""
    strategy_id: str
    factors: List[str]
    window_size: int
    rebalance_frequency: int
    data_period: int
    selection_count: int
    weight_method: str
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            'strategy_id': self.strategy_id,
            'factors': self.factors,
            'window_size': self.window_size,
            'rebalance_frequency': self.rebalance_frequency,
            'data_period': self.data_period,
            'selection_count': self.selection_count,
            'weight_method': self.weight_method
        }

class ParameterSpaceGenerator:
    """參數空間生成器"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化參數空間生成器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # 獲取參數配置
        self.parameter_configs = config_manager.get_parameter_configs()
        
        # 驗證參數配置
        self._validate_configs()
        
    def _validate_configs(self):
        """驗證參數配置"""
        required_params = {
            'factors', 'window_size', 'rebalance_frequency', 
            'data_period', 'selection_count', 'weight_method'
        }
        
        existing_params = {config.name for config in self.parameter_configs}
        missing_params = required_params - existing_params
        
        if missing_params:
            raise ValueError(f"缺少必需的參數配置: {missing_params}")
            
        self.logger.info("參數配置驗證通過")
        
    def _generate_parameter_values(self, config: ParameterConfig) -> List[Any]:
        """
        生成單個參數的所有可能值
        
        Args:
            config: 參數配置
            
        Returns:
            參數值列表
        """
        if config.type == 'fixed':
            return [config.value]
        elif config.type == 'choice':
            return config.choices
        elif config.type == 'range':
            values = []
            current = config.min_value
            while current <= config.max_value:
                values.append(int(current) if isinstance(config.step, int) else current)
                current += config.step
            return values
        else:
            raise ValueError(f"不支持的參數類型: {config.type}")
            
    def generate_exhaustive(self) -> Iterator[StrategyConfig]:
        """
        生成窮舉式參數組合
        
        Returns:
            策略配置迭代器
        """
        self.logger.info("開始生成窮舉式參數組合")
        
        # 生成所有參數的值空間
        param_spaces = {}
        for config in self.parameter_configs:
            param_spaces[config.name] = self._generate_parameter_values(config)
            
        # 計算總數量
        total_combinations = 1
        for values in param_spaces.values():
            total_combinations *= len(values)
            
        self.logger.info(f"總參數組合數量: {total_combinations:,}")
        
        # 生成所有組合
        param_names = list(param_spaces.keys())
        param_values = list(param_spaces.values())
        
        strategy_count = 0
        for combination in itertools.product(*param_values):
            strategy_count += 1
            
            # 創建參數字典
            params = dict(zip(param_names, combination))
            
            # 創建策略配置
            strategy_config = StrategyConfig(
                strategy_id=f"exhaustive_{strategy_count:08d}",
                factors=params['factors'],
                window_size=params['window_size'],
                rebalance_frequency=params['rebalance_frequency'],
                data_period=params['data_period'],
                selection_count=params['selection_count'],
                weight_method=params['weight_method']
            )
            
            yield strategy_config
            
    def generate_random_sampling(self, sample_size: int, 
                                seed: Optional[int] = None) -> List[StrategyConfig]:
        """
        生成隨機抽樣參數組合
        
        Args:
            sample_size: 抽樣數量
            seed: 隨機種子
            
        Returns:
            策略配置列表
        """
        self.logger.info(f"開始生成隨機抽樣參數組合，樣本數量: {sample_size}")
        
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
        # 生成所有參數的值空間
        param_spaces = {}
        for config in self.parameter_configs:
            param_spaces[config.name] = self._generate_parameter_values(config)
            
        strategies = []
        generated_configs = set()  # 避免重複
        
        max_attempts = sample_size * 10  # 最多嘗試10倍數量
        attempts = 0
        
        while len(strategies) < sample_size and attempts < max_attempts:
            attempts += 1
            
            # 隨機選擇參數值  
            params = {}
            for param_name, param_values in param_spaces.items():
                params[param_name] = random.choice(param_values)
                
            # 創建配置字符串用於去重
            config_str = str(sorted(params.items()))
            if config_str in generated_configs:
                continue
                
            generated_configs.add(config_str)
            
            # 創建策略配置
            strategy_config = StrategyConfig(
                strategy_id=f"sampling_{len(strategies)+1:06d}",
                factors=params['factors'],
                window_size=params['window_size'],
                rebalance_frequency=params['rebalance_frequency'],
                data_period=params['data_period'],
                selection_count=params['selection_count'],
                weight_method=params['weight_method']
            )
            
            strategies.append(strategy_config)
            
        self.logger.info(f"成功生成 {len(strategies)} 個唯一策略配置")
        return strategies
        
    def generate_smart_sampling(self, sample_size: int, 
                               method: str = "latin_hypercube") -> List[StrategyConfig]:
        """
        生成智能抽樣參數組合
        
        Args:
            sample_size: 抽樣數量
            method: 抽樣方法 ("latin_hypercube", "grid", "sobol")
            
        Returns:
            策略配置列表
        """
        self.logger.info(f"開始生成智能抽樣參數組合，方法: {method}")
        
        if method == "latin_hypercube":
            return self._generate_latin_hypercube_sampling(sample_size)
        elif method == "grid":
            return self._generate_grid_sampling(sample_size)
        elif method == "sobol":
            return self._generate_sobol_sampling(sample_size)
        else:
            raise ValueError(f"不支持的抽樣方法: {method}")
            
    def _generate_latin_hypercube_sampling(self, sample_size: int) -> List[StrategyConfig]:
        """拉丁超立方抽樣"""
        try:
            from scipy.stats import qmc
        except ImportError:
            self.logger.warning("scipy未安裝，使用隨機抽樣替代")
            return self.generate_random_sampling(sample_size)
            
        # 只對數值參數進行LHS抽樣
        numeric_params = []
        choice_params = {}
        
        for config in self.parameter_configs:
            if config.type == 'range':
                numeric_params.append(config)
            else:
                choice_params[config.name] = self._generate_parameter_values(config)
                
        strategies = []
        
        if numeric_params:
            # 對數值參數進行LHS抽樣
            sampler = qmc.LatinHypercube(d=len(numeric_params))
            samples = sampler.random(n=sample_size)
            
            for i, sample in enumerate(samples):
                params = {}
                
                # 處理數值參數
                for j, config in enumerate(numeric_params):
                    # 將[0,1]範圍映射到參數範圍
                    value = config.min_value + sample[j] * (config.max_value - config.min_value)
                    # 按步長調整
                    value = config.min_value + round((value - config.min_value) / config.step) * config.step
                    params[config.name] = int(value) if isinstance(config.step, int) else value
                    
                # 處理選擇參數
                for param_name, param_values in choice_params.items():
                    params[param_name] = random.choice(param_values)
                    
                strategy_config = StrategyConfig(
                    strategy_id=f"lhs_{i+1:06d}",
                    factors=params['factors'],
                    window_size=params['window_size'],
                    rebalance_frequency=params['rebalance_frequency'],
                    data_period=params['data_period'],
                    selection_count=params['selection_count'],
                    weight_method=params['weight_method']
                )
                
                strategies.append(strategy_config)
        else:
            # 如果沒有數值參數，使用隨機抽樣
            strategies = self.generate_random_sampling(sample_size)
            
        return strategies
        
    def _generate_grid_sampling(self, sample_size: int) -> List[StrategyConfig]:
        """網格抽樣"""
        # 計算每個參數的抽樣點數
        num_params = len(self.parameter_configs)
        points_per_param = max(2, int(sample_size ** (1/num_params)))
        
        param_samples = {}
        for config in self.parameter_configs:
            param_values = self._generate_parameter_values(config)
            
            if len(param_values) <= points_per_param:
                param_samples[config.name] = param_values
            else:
                # 均勻選擇
                indices = np.linspace(0, len(param_values)-1, points_per_param, dtype=int)
                param_samples[config.name] = [param_values[i] for i in indices]
                
        # 生成網格組合
        param_names = list(param_samples.keys())
        param_values = list(param_samples.values())
        
        strategies = []
        strategy_count = 0
        
        for combination in itertools.product(*param_values):
            if len(strategies) >= sample_size:
                break
                
            strategy_count += 1
            params = dict(zip(param_names, combination))
            
            strategy_config = StrategyConfig(
                strategy_id=f"grid_{strategy_count:06d}",
                factors=params['factors'],
                window_size=params['window_size'],
                rebalance_frequency=params['rebalance_frequency'],
                data_period=params['data_period'],
                selection_count=params['selection_count'],
                weight_method=params['weight_method']
            )
            
            strategies.append(strategy_config)
            
        return strategies
        
    def _generate_sobol_sampling(self, sample_size: int) -> List[StrategyConfig]:
        """Sobol序列抽樣"""
        try:
            from scipy.stats import qmc
        except ImportError:
            self.logger.warning("scipy未安裝，使用隨機抽樣替代")
            return self.generate_random_sampling(sample_size)
            
        # 實現類似於LHS的邏輯，但使用Sobol序列
        numeric_params = []
        choice_params = {}
        
        for config in self.parameter_configs:
            if config.type == 'range':
                numeric_params.append(config)
            else:
                choice_params[config.name] = self._generate_parameter_values(config)
                
        strategies = []
        
        if numeric_params:
            sampler = qmc.Sobol(d=len(numeric_params))
            samples = sampler.random(n=sample_size)
            
            for i, sample in enumerate(samples):
                params = {}
                
                for j, config in enumerate(numeric_params):
                    value = config.min_value + sample[j] * (config.max_value - config.min_value)
                    value = config.min_value + round((value - config.min_value) / config.step) * config.step
                    params[config.name] = int(value) if isinstance(config.step, int) else value
                    
                for param_name, param_values in choice_params.items():
                    params[param_name] = random.choice(param_values)
                    
                strategy_config = StrategyConfig(
                    strategy_id=f"sobol_{i+1:06d}",
                    factors=params['factors'],
                    window_size=params['window_size'],
                    rebalance_frequency=params['rebalance_frequency'],
                    data_period=params['data_period'],
                    selection_count=params['selection_count'],
                    weight_method=params['weight_method']
                )
                
                strategies.append(strategy_config)
        else:
            strategies = self.generate_random_sampling(sample_size)
            
        return strategies
        
    def generate_strategies(self, mode: str = "sampling", size: Optional[int] = None, 
                          method: str = "random", seed: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        生成策略參數組合的主入口
        
        Args:
            mode: 生成模式 ("exhaustive" 或 "sampling")
            size: 抽樣數量（sampling模式下使用）
            method: 抽樣方法 ("random", "latin_hypercube", "grid", "sobol")
            seed: 隨機種子
            
        Returns:
            策略配置字典列表
        """
        self.logger.info(f"開始生成策略參數組合 - 模式: {mode}, 方法: {method}")
        
        if mode == "exhaustive":
            # 窮舉模式
            strategies = []
            for strategy_config in self.generate_exhaustive():
                strategies.append(strategy_config.to_dict())
                
                # 如果指定了size，限制數量
                if size and len(strategies) >= size:
                    break
                    
        elif mode == "sampling":
            if size is None:
                raise ValueError("sampling模式需要指定size參數")
                
            if method == "random":
                strategy_configs = self.generate_random_sampling(size, seed)
            else:
                strategy_configs = self.generate_smart_sampling(size, method)
                
            strategies = [config.to_dict() for config in strategy_configs]
            
        else:
            raise ValueError(f"不支持的生成模式: {mode}")
            
        self.logger.info(f"成功生成 {len(strategies)} 個策略配置")
        return strategies
        
    def get_parameter_space_info(self) -> Dict[str, Any]:
        """獲取參數空間信息"""
        info = {
            'parameter_count': len(self.parameter_configs),
            'parameters': {},
            'total_combinations': 1
        }
        
        for config in self.parameter_configs:
            param_values = self._generate_parameter_values(config)
            info['parameters'][config.name] = {
                'type': config.type,
                'value_count': len(param_values),
                'sample_values': param_values[:5] if len(param_values) > 5 else param_values
            }
            info['total_combinations'] *= len(param_values)
            
        return info
        
    def validate_strategy_config(self, config: Dict[str, Any]) -> List[str]:
        """驗證策略配置的合法性"""
        errors = []
        
        required_fields = ['factors', 'window_size', 'rebalance_frequency', 
                          'data_period', 'selection_count', 'weight_method']
        
        for field in required_fields:
            if field not in config:
                errors.append(f"缺少必需字段: {field}")
                
        # 驗證具體參數值
        if 'factors' in config:
            if not isinstance(config['factors'], list) or not config['factors']:
                errors.append("factors必須是非空列表")
                
        if 'window_size' in config:
            if not isinstance(config['window_size'], int) or config['window_size'] <= 0:
                errors.append("window_size必須是正整數")
                
        if 'selection_count' in config:
            if not isinstance(config['selection_count'], int) or config['selection_count'] < 0:
                errors.append("selection_count必須是非負整數")
                
        return errors 