"""
配置管理器 - ConfigManager
負責讀取和管理系統配置文件
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class ParameterConfig:
    """參數配置類"""
    name: str
    type: str  # "range", "choice", "fixed"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Any]] = None
    value: Optional[Any] = None

@dataclass
class SystemConfig:
    """系統配置類"""
    database_path: str = "../../data/funding_rate.db"
    max_parallel: int = 4
    timeout_minutes: int = 30
    cleanup_failed: bool = True
    results_retention_days: int = 30

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果為空則使用默認配置
        """
        self.logger = logging.getLogger(__name__)
        
        if config_path is None:
            # 使用默認配置文件
            config_path = Path(__file__).parent.parent / "config.yaml"
            
        self.config_path = Path(config_path)
        self.config_data = {}
        self.parameter_configs = []
        self.system_config = SystemConfig()
        
        # 載入配置
        self._load_config()
        
    def _load_config(self):
        """載入配置文件"""
        try:
            if self.config_path.exists():
                self.logger.info(f"載入配置文件: {self.config_path}")
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f)
            else:
                self.logger.warning(f"配置文件不存在: {self.config_path}，使用默認配置")
                self._create_default_config()
                
            # 解析配置
            self._parse_config()
            
        except Exception as e:
            self.logger.error(f"載入配置文件失敗: {e}")
            self.logger.info("使用默認配置")
            self._create_default_config()
            self._parse_config()
            
    def _create_default_config(self):
        """創建默認配置"""
        self.config_data = {
            'system': {
                'database_path': '../../data/funding_rate.db',
                'max_parallel': 4,
                'timeout_minutes': 30,
                'cleanup_failed': True,
                'results_retention_days': 30
            },
            'parameters': {
                'factors': {
                    'type': 'choice',
                    'choices': [
                        ['SR'], ['ST'], ['DD'], ['WR'], ['SO'], ['TR'],
                        ['SR', 'ST'], ['SR', 'DD'], ['ST', 'DD'], 
                        ['SR', 'ST', 'DD']
                    ]
                },
                'window_size': {
                    'type': 'choice',
                    'choices': [5, 10, 20, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300]
                },
                'rebalance_frequency': {
                    'type': 'choice', 
                    'choices': [1, 2, 7, 14, 30]
                },
                'data_period': {
                    'type': 'choice',
                    'choices': [10, 15, 20, 30, 45, 60, 90, 120, 150, 180, 210, 240, 270, 300]
                },
                'selection_count': {
                    'type': 'range',
                    'min_value': 0,
                    'max_value': 15,
                    'step': 1
                },
                'weight_method': {
                    'type': 'choice',
                    'choices': ['EQ', 'IC', 'FS']
                }
            }
        }
        
    def _parse_config(self):
        """解析配置數據"""
        # 解析系統配置
        system_cfg = self.config_data.get('system', {})
        self.system_config = SystemConfig(
            database_path=system_cfg.get('database_path', '../../data/funding_rate.db'),
            max_parallel=system_cfg.get('max_parallel', 4),
            timeout_minutes=system_cfg.get('timeout_minutes', 30),
            cleanup_failed=system_cfg.get('cleanup_failed', True),
            results_retention_days=system_cfg.get('results_retention_days', 30)
        )
        
        # 解析參數配置
        parameters = self.config_data.get('parameters', {})
        self.parameter_configs = []
        
        for param_name, param_config in parameters.items():
            param_type = param_config.get('type', 'fixed')
            
            config = ParameterConfig(
                name=param_name,
                type=param_type
            )
            
            if param_type == 'range':
                config.min_value = param_config.get('min_value')
                config.max_value = param_config.get('max_value')
                config.step = param_config.get('step', 1)
            elif param_type == 'choice':
                config.choices = param_config.get('choices', [])
            elif param_type == 'fixed':
                config.value = param_config.get('value')
                
            self.parameter_configs.append(config)
            
        self.logger.info(f"成功解析 {len(self.parameter_configs)} 個參數配置")
        
    def get_parameter_configs(self) -> List[ParameterConfig]:
        """獲取參數配置列表"""
        return self.parameter_configs
        
    def get_system_config(self) -> SystemConfig:
        """獲取系統配置"""
        return self.system_config
        
    def get_parameter_space_size(self) -> int:
        """計算參數空間大小"""
        total_size = 1
        
        for config in self.parameter_configs:
            if config.type == 'range':
                if config.min_value is not None and config.max_value is not None:
                    size = int((config.max_value - config.min_value) / config.step) + 1
                    total_size *= size
            elif config.type == 'choice':
                if config.choices:
                    total_size *= len(config.choices)
            # fixed type不影響空間大小
            
        return total_size
        
    def validate_config(self) -> List[str]:
        """驗證配置合法性"""
        errors = []
        
        # 驗證參數配置
        for config in self.parameter_configs:
            if config.type == 'range':
                if config.min_value is None or config.max_value is None:
                    errors.append(f"參數 {config.name}: range類型需要設置min_value和max_value")
                elif config.min_value >= config.max_value:
                    errors.append(f"參數 {config.name}: min_value必須小於max_value")
                elif config.step is None or config.step <= 0:
                    errors.append(f"參數 {config.name}: step必須大於0")
                    
            elif config.type == 'choice':
                if not config.choices:
                    errors.append(f"參數 {config.name}: choice類型需要設置choices列表")
                    
            elif config.type == 'fixed':
                if config.value is None:
                    errors.append(f"參數 {config.name}: fixed類型需要設置value")
                    
        # 驗證系統配置
        if self.system_config.max_parallel <= 0:
            errors.append("max_parallel必須大於0")
            
        if self.system_config.timeout_minutes <= 0:
            errors.append("timeout_minutes必須大於0")
            
        return errors
        
    def save_config(self, path: str = None):
        """保存配置到文件"""
        if path is None:
            path = self.config_path
            
        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config_data, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            self.logger.info(f"配置已保存到: {path}")
        except Exception as e:
            self.logger.error(f"保存配置失敗: {e}")
            raise
            
    def get_config_summary(self) -> Dict[str, Any]:
        """獲取配置摘要"""
        return {
            'config_path': str(self.config_path),
            'parameter_count': len(self.parameter_configs),
            'parameter_space_size': self.get_parameter_space_size(),
            'max_parallel': self.system_config.max_parallel,
            'timeout_minutes': self.system_config.timeout_minutes,
            'database_path': self.system_config.database_path
        } 