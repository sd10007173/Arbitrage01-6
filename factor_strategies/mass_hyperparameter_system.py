#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏭 大规模超参数调优系统 (Mass Hyperparameter Tuning System)
专为10000+策略的真实回测设计

核心功能:
1. 系统性参数空间探索
2. 大规模真实回测执行 
3. 进度管理和错误恢复
4. 绩效分析和参数关联性分析
"""

import os
import sys
import json
import time
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import argparse
import itertools
from pathlib import Path

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from database_operations import DatabaseManager

class MassHyperparameterSystem:
    """大规模超参数调优系统"""
    
    def __init__(self, config_file: str = "hyperparameter_tuning/config.yaml"):
        self.config_file = config_file
        self.project_root = project_root
        
        # 工作目录设置
        self.work_dir = os.path.join(current_dir, "mass_tuning_workspace")
        os.makedirs(self.work_dir, exist_ok=True)
        
        # 数据库设置
        self.progress_db_path = os.path.join(self.work_dir, "tuning_progress.db")
        self.results_db_path = os.path.join(self.work_dir, "tuning_results.db")
        
        # 时间戳
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 初始化数据库
        self._init_databases()
        
        # 加载配置
        self.config = self._load_config()
        
        print(f"🏭 大规模超参数调优系统初始化完成")
        print(f"📁 工作目录: {self.work_dir}")
        print(f"🆔 会话ID: {self.session_id}")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        import yaml
        
        config_paths = [
            os.path.join(self.project_root, self.config_file),
            os.path.join(current_dir, self.config_file),
            os.path.join(current_dir, "hyperparameter_tuning", "config.yaml")
        ]
        
        config_path = None
        for path in config_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if not config_path:
            raise FileNotFoundError(f"配置文件不存在: {config_paths}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print(f"✅ 配置文件加载: {config_path}")
        return config
    
    def _init_databases(self):
        """初始化进度和结果数据库"""
        # 进度数据库
        with sqlite3.connect(self.progress_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    strategy_id TEXT UNIQUE NOT NULL,
                    strategy_config TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',  -- pending, running, factor_completed, backtest_completed, failed
                    start_time TEXT,
                    end_time TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_strategy_status ON strategy_progress(status);
                CREATE INDEX IF NOT EXISTS idx_strategy_session ON strategy_progress(session_id);
            """)
        
        # 结果数据库
        with sqlite3.connect(self.results_db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hyperparameter_tuning_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    backtest_id TEXT,
                    
                    -- 策略参数
                    factors TEXT,
                    window INTEGER,
                    input_column TEXT,
                    min_data_days INTEGER,
                    skip_first_n_days INTEGER,
                    weight_method TEXT,
                    
                    -- 回测设置
                    start_date TEXT,
                    end_date TEXT,
                    initial_capital REAL,
                    
                    -- 关键绩效指标
                    total_return REAL,
                    annual_return REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    win_rate REAL,
                    total_trades INTEGER,
                    
                    -- 详细指标
                    volatility REAL,
                    sortino_ratio REAL,
                    calmar_ratio REAL,
                    
                    -- 元数据
                    execution_time_seconds REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(strategy_id, backtest_id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_hyperparameter_tuning_performance ON hyperparameter_tuning_results(total_return, sharpe_ratio);
                CREATE INDEX IF NOT EXISTS idx_hyperparameter_tuning_session ON hyperparameter_tuning_results(session_id);
            """)
    
    def generate_parameter_space(self, mode: str = "exhaustive", sample_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """生成参数空间"""
        print(f"\n🎯 生成参数空间 (模式: {mode})")
        
        params = self.config['parameters']
        
        # 计算总组合数
        total_combinations = self._calculate_total_combinations(params)
        print(f"📊 理论总组合数: {total_combinations:,}")
        
        if mode == "exhaustive":
            strategies = self._generate_exhaustive_combinations(params)
            print(f"✅ 穷举模式: 生成 {len(strategies):,} 个策略配置")
        elif mode == "sampling":
            if sample_size is None:
                sample_size = min(10000, total_combinations)
            strategies = self._generate_sampled_combinations(params, sample_size)
            print(f"✅ 抽样模式: 生成 {len(strategies):,} 个策略配置")
        else:
            raise ValueError(f"未知模式: {mode}")
        
        return strategies
    
    def _calculate_total_combinations(self, params: Dict[str, Any]) -> int:
        """计算理论总组合数"""
        from itertools import combinations
        
        n_factors = len(params['available_factors'])
        max_factors = params['max_factors_per_strategy']
        min_factors = params['min_factors_per_strategy']
        
        # 计算因子组合数
        factor_combinations = 0
        for r in range(min_factors, max_factors + 1):
            factor_combinations += len(list(combinations(range(n_factors), r)))
        
        total = (factor_combinations * 
                len(params['windows']) * 
                len(params['input_columns']) *
                len(params['min_data_days']) *
                len(params['skip_first_n_days']) *
                len(params['weight_methods']))
        
        return total
    
    def _generate_exhaustive_combinations(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成穷举组合"""
        from itertools import combinations
        
        strategies = []
        strategy_id = 1
        
        # 生成所有因子组合
        min_factors = params['min_factors_per_strategy']
        max_factors = params['max_factors_per_strategy']
        
        for n_factors in range(min_factors, max_factors + 1):
            for factor_combo in combinations(params['available_factors'], n_factors):
                for window in params['windows']:
                    for input_col in params['input_columns']:
                        for min_days in params['min_data_days']:
                            for skip_days in params['skip_first_n_days']:
                                for weight_method in params['weight_methods']:
                                    
                                    strategy_config = {
                                        'strategy_id': f"MASS_{strategy_id:06d}",
                                        'factors': list(factor_combo),
                                        'window': window,
                                        'input_column': input_col,
                                        'min_data_days': min_days,
                                        'skip_first_n_days': skip_days,
                                        'weight_method': weight_method
                                    }
                                    
                                    strategies.append(strategy_config)
                                    strategy_id += 1
                                    
                                    # 定期输出进度
                                    if strategy_id % 10000 == 0:
                                        print(f"📈 已生成 {strategy_id:,} 个配置...")
        
        return strategies
    
    def _generate_sampled_combinations(self, params: Dict[str, Any], sample_size: int) -> List[Dict[str, Any]]:
        """生成抽样组合"""
        import random
        from itertools import combinations
        
        strategies = []
        
        for i in range(sample_size):
            # 随机选择因子数量和因子
            min_factors = params['min_factors_per_strategy']
            max_factors = params['max_factors_per_strategy']
            n_factors = random.randint(min_factors, max_factors)
            factors = random.sample(params['available_factors'], n_factors)
            
            # 随机选择其他参数
            window = random.choice(params['windows'])
            input_col = random.choice(params['input_columns'])
            min_days = random.choice(params['min_data_days'])
            skip_days = random.choice(params['skip_first_n_days'])
            weight_method = random.choice(params['weight_methods'])
            
            strategy_config = {
                'strategy_id': f"SAMP_{i+1:06d}",
                'factors': factors,
                'window': window,
                'input_column': input_col,
                'min_data_days': min_days,
                'skip_first_n_days': skip_days,
                'weight_method': weight_method
            }
            
            strategies.append(strategy_config)
            
            if (i + 1) % 1000 == 0:
                print(f"📈 已生成 {i+1:,} 个配置...")
        
        return strategies
    
    def _save_strategies_to_progress_db(self, strategies: List[Dict[str, Any]]):
        """保存策略配置到进度数据库"""
        with sqlite3.connect(self.progress_db_path) as conn:
            for strategy in strategies:
                conn.execute("""
                    INSERT OR REPLACE INTO strategy_progress 
                    (session_id, strategy_id, strategy_config, status)
                    VALUES (?, ?, ?, 'pending')
                """, (
                    self.session_id,
                    strategy['strategy_id'],
                    json.dumps(strategy)
                ))
        
        print(f"💾 已保存 {len(strategies):,} 个策略配置到进度数据库")
    
    def execute_mass_tuning(self, 
                           start_date: str = "2024-01-01",
                           end_date: str = "2025-06-20", 
                           max_parallel: int = 4,
                           resume: bool = True) -> Dict[str, Any]:
        """执行大规模调优
        
        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期  
            max_parallel: 最大并行数
            resume: 是否从上次中断处继续
        """
        print(f"\n🏭 开始大规模超参数调优")
        print(f"=" * 80)
        print(f"📅 回测期间: {start_date} - {end_date}")
        print(f"🔄 最大并行: {max_parallel}")
        print(f"⏮️ 断点续跑: {resume}")
        print(f"=" * 80)
        
        # 获取待执行的策略
        pending_strategies = self._get_pending_strategies(resume)
        
        if not pending_strategies:
            print("✅ 没有待执行的策略，所有任务已完成")
            return self._generate_summary()
        
        print(f"📋 待执行策略数: {len(pending_strategies):,}")
        
        # 批量执行
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            # 提交所有任务
            future_to_strategy = {}
            
            for strategy_data in pending_strategies:
                strategy_config = json.loads(strategy_data['strategy_config'])
                future = executor.submit(
                    self._execute_single_strategy,
                    strategy_config,
                    start_date,
                    end_date
                )
                future_to_strategy[future] = strategy_data
            
            # 处理完成的任务
            completed = 0
            failed = 0
            
            for future in as_completed(future_to_strategy):
                strategy_data = future_to_strategy[future]
                strategy_id = strategy_data['strategy_id']
                
                try:
                    result = future.result()
                    if result['success']:
                        completed += 1
                        print(f"✅ [{completed+failed:,}/{len(pending_strategies):,}] {strategy_id} - "
                              f"ROI: {result.get('total_return', 'N/A'):.2f}%")
                    else:
                        failed += 1
                        print(f"❌ [{completed+failed:,}/{len(pending_strategies):,}] {strategy_id} - "
                              f"{result.get('error', 'Unknown error')}")
                    
                    # 定期显示进度
                    if (completed + failed) % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = (completed + failed) / elapsed * 60  # 每分钟处理数
                        remaining = len(pending_strategies) - (completed + failed)
                        eta = remaining / rate if rate > 0 else 0
                        
                        print(f"📊 进度统计: 完成 {completed:,}, 失败 {failed:,}, "
                              f"处理速度 {rate:.1f}/分钟, 预计剩余 {eta/60:.1f}小时")
                
                except Exception as e:
                    failed += 1
                    print(f"❌ [{completed+failed:,}/{len(pending_strategies):,}] {strategy_id} - 异常: {str(e)[:100]}")
                    self._update_strategy_status(strategy_id, 'failed', error_message=str(e))
        
        total_time = time.time() - start_time
        
        print(f"\n🎉 大规模调优完成!")
        print(f"⏱️ 总耗时: {total_time/3600:.2f} 小时")
        print(f"✅ 成功: {completed:,}")
        print(f"❌ 失败: {failed:,}")
        print(f"📊 成功率: {completed/(completed+failed)*100:.1f}%")
        
        return self._generate_summary()
    
    def _get_pending_strategies(self, resume: bool) -> List[Dict[str, Any]]:
        """获取待执行的策略"""
        with sqlite3.connect(self.progress_db_path) as conn:
            if resume:
                # 恢复模式：获取未完成的策略
                cursor = conn.execute("""
                    SELECT * FROM strategy_progress 
                    WHERE status IN ('pending', 'running', 'factor_completed')
                    ORDER BY id
                """)
            else:
                # 重新开始：获取所有策略
                cursor = conn.execute("""
                    SELECT * FROM strategy_progress 
                    WHERE session_id = ?
                    ORDER BY id
                """, (self.session_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def _execute_single_strategy(self, strategy_config: Dict[str, Any], 
                                start_date: str, end_date: str) -> Dict[str, Any]:
        """执行单个策略"""
        strategy_id = strategy_config['strategy_id']
        
        try:
            # 更新状态为运行中
            self._update_strategy_status(strategy_id, 'running')
            
            # 第1步：执行因子策略
            factor_success = self._run_factor_strategy(strategy_config, start_date, end_date)
            
            if not factor_success:
                self._update_strategy_status(strategy_id, 'failed', error_message="Factor strategy execution failed")
                return {'success': False, 'error': 'Factor execution failed'}
            
            self._update_strategy_status(strategy_id, 'factor_completed')
            
            # 第2步：执行回测
            backtest_result = self._run_backtest(strategy_config, start_date, end_date)
            
            if not backtest_result:
                self._update_strategy_status(strategy_id, 'failed', error_message="Backtest execution failed")
                return {'success': False, 'error': 'Backtest failed'}
            
            # 保存结果
            self._save_backtest_result(strategy_config, backtest_result)
            self._update_strategy_status(strategy_id, 'backtest_completed')
            
            return {
                'success': True,
                'total_return': backtest_result.get('total_return', 0),
                'sharpe_ratio': backtest_result.get('sharpe_ratio', 0)
            }
            
        except Exception as e:
            self._update_strategy_status(strategy_id, 'failed', error_message=str(e))
            return {'success': False, 'error': str(e)}
    
    def _run_factor_strategy(self, strategy_config: Dict[str, Any], 
                           start_date: str, end_date: str) -> bool:
        """运行因子策略"""
        # 动态注册策略
        registered_name = self._register_temp_strategy(strategy_config)
        
        try:
            # 构建命令
            cmd = [
                sys.executable,
                os.path.join(self.project_root, 'factor_strategies', 'run_factor_strategies.py'),
                '--start_date', start_date,
                '--end_date', end_date,
                '--strategy', registered_name,
                '--auto'
            ]
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=600  # 10分钟超时
            )
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False
        finally:
            # 清理临时策略
            self._unregister_temp_strategy(registered_name)
    
    def _run_backtest(self, strategy_config: Dict[str, Any], 
                     start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """运行回测"""
        backtest_params = self.config.get('backtest', {})
        
        try:
            # 构建回测命令
            cmd = [
                sys.executable,
                os.path.join(self.project_root, 'backtest_v5.py'),
                strategy_config['strategy_id'],  # 策略名
                start_date,
                end_date,
                str(backtest_params.get('initial_capital', 10000)),
                str(backtest_params.get('position_size', 0.25)),
                str(backtest_params.get('fee_rate', 0.001)),
                str(backtest_params.get('max_positions', 4)),
                str(backtest_params.get('entry_top_n', 4)),
                str(backtest_params.get('exit_threshold', 10))
            ]
            
            # 执行回测
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                return self._parse_backtest_output(result.stdout)
            else:
                return None
                
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None
    
    def _parse_backtest_output(self, output: str) -> Dict[str, Any]:
        """解析回测输出"""
        import re
        
        result = {}
        lines = output.split('\n')
        
        for line in lines:
            # 提取关键指标
            if '总收益率' in line or 'Total Return' in line:
                numbers = re.findall(r'-?\d+\.?\d*', line)
                if numbers:
                    result['total_return'] = float(numbers[-1])
            elif '年化收益率' in line or 'Annual Return' in line:
                numbers = re.findall(r'-?\d+\.?\d*', line)
                if numbers:
                    result['annual_return'] = float(numbers[-1])
            elif '夏普比率' in line or 'Sharpe Ratio' in line:
                numbers = re.findall(r'-?\d+\.?\d*', line)
                if numbers:
                    result['sharpe_ratio'] = float(numbers[-1])
            elif '最大回撤' in line or 'Max Drawdown' in line:
                numbers = re.findall(r'-?\d+\.?\d*', line)
                if numbers:
                    result['max_drawdown'] = float(numbers[-1])
            elif '胜率' in line or 'Win Rate' in line:
                numbers = re.findall(r'-?\d+\.?\d*', line)
                if numbers:
                    result['win_rate'] = float(numbers[-1])
            elif '交易次数' in line or 'Total Trades' in line:
                numbers = re.findall(r'\d+', line)
                if numbers:
                    result['total_trades'] = int(numbers[-1])
        
        return result
    
    def _register_temp_strategy(self, strategy_config: Dict[str, Any]) -> str:
        """临时注册策略"""
        # 这里简化处理，实际应该动态注册到 FACTOR_STRATEGIES
        return strategy_config['strategy_id']
    
    def _unregister_temp_strategy(self, strategy_name: str):
        """取消临时策略注册"""
        pass
    
    def _update_strategy_status(self, strategy_id: str, status: str, error_message: str = None):
        """更新策略状态"""
        with sqlite3.connect(self.progress_db_path) as conn:
            if error_message:
                conn.execute("""
                    UPDATE strategy_progress 
                    SET status = ?, error_message = ?, end_time = CURRENT_TIMESTAMP
                    WHERE strategy_id = ?
                """, (status, error_message, strategy_id))
            else:
                conn.execute("""
                    UPDATE strategy_progress 
                    SET status = ?, end_time = CURRENT_TIMESTAMP
                    WHERE strategy_id = ?
                """, (status, strategy_id))
    
    def _save_backtest_result(self, strategy_config: Dict[str, Any], backtest_result: Dict[str, Any]):
        """保存回测结果"""
        backtest_params = self.config.get('backtest', {})
        
        with sqlite3.connect(self.results_db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO hyperparameter_tuning_results (
                    session_id, strategy_id, factors, window, input_column,
                    min_data_days, skip_first_n_days, weight_method,
                    start_date, end_date, initial_capital,
                    total_return, annual_return, sharpe_ratio, max_drawdown,
                    win_rate, total_trades
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.session_id,
                strategy_config['strategy_id'],
                json.dumps(strategy_config['factors']),
                strategy_config['window'],
                strategy_config['input_column'],
                strategy_config['min_data_days'],
                strategy_config['skip_first_n_days'],
                strategy_config['weight_method'],
                backtest_params.get('start_date'),
                backtest_params.get('end_date'),
                backtest_params.get('initial_capital', 10000),
                backtest_result.get('total_return'),
                backtest_result.get('annual_return'),
                backtest_result.get('sharpe_ratio'),
                backtest_result.get('max_drawdown'),
                backtest_result.get('win_rate'),
                backtest_result.get('total_trades')
            ))
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成执行总结"""
        with sqlite3.connect(self.progress_db_path) as conn:
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM strategy_progress 
                WHERE session_id = ?
                GROUP BY status
            """, (self.session_id,))
            
            status_counts = dict(cursor.fetchall())
        
        return {
            'session_id': self.session_id,
            'status_summary': status_counts,
            'total_strategies': sum(status_counts.values()),
            'completed': status_counts.get('backtest_completed', 0),
            'timestamp': datetime.now().isoformat()
        }
    
    def analyze_performance(self, top_n: int = 100) -> Dict[str, Any]:
        """分析绩效和参数关联性"""
        print(f"\n📊 开始绩效分析 (Top {top_n})")
        
        # 获取所有完成的回测结果
        with sqlite3.connect(self.results_db_path) as conn:
            df = pd.read_sql_query("""
                SELECT * FROM hyperparameter_tuning_results 
                WHERE session_id = ? AND total_return IS NOT NULL
                ORDER BY total_return DESC, sharpe_ratio DESC
            """, conn, params=(self.session_id,))
        
        if df.empty:
            print("❌ 没有找到有效的回测结果")
            return {}
        
        print(f"📈 有效回测结果: {len(df):,} 个")
        
        # 按ROI和Sharpe筛选Top策略
        top_by_roi = df.nlargest(top_n, 'total_return')
        top_by_sharpe = df.nlargest(top_n, 'sharpe_ratio')
        
        # 参数关联性分析
        correlation_analysis = self._analyze_parameter_correlation(df)
        
        # 保存分析结果
        analysis_result = {
            'summary': {
                'total_strategies': len(df),
                'top_n': top_n,
                'analysis_time': datetime.now().isoformat()
            },
            'top_performers': {
                'by_roi': top_by_roi.to_dict('records'),
                'by_sharpe': top_by_sharpe.to_dict('records')
            },
            'parameter_analysis': correlation_analysis
        }
        
        # 保存到文件
        analysis_file = os.path.join(self.work_dir, f"performance_analysis_{self.session_id}.json")
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)
        
        print(f"📄 分析结果已保存: {analysis_file}")
        
        # 打印关键发现
        self._print_key_findings(analysis_result)
        
        return analysis_result
    
    def _analyze_parameter_correlation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析参数与绩效的关联性"""
        # 数值型参数的相关性
        numeric_params = ['window', 'min_data_days', 'skip_first_n_days']
        performance_metrics = ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate']
        
        correlations = {}
        for param in numeric_params:
            param_corr = {}
            for metric in performance_metrics:
                if param in df.columns and metric in df.columns:
                    corr = df[param].corr(df[metric])
                    param_corr[metric] = corr if not pd.isna(corr) else 0.0
            correlations[param] = param_corr
        
        # 分类参数的绩效分析
        categorical_analysis = {}
        
        # 因子分析
        factor_performance = self._analyze_factor_performance(df)
        categorical_analysis['factors'] = factor_performance
        
        # 输入列分析
        if 'input_column' in df.columns:
            input_col_perf = df.groupby('input_column')[performance_metrics].mean().to_dict()
            categorical_analysis['input_columns'] = input_col_perf
        
        # 权重方法分析
        if 'weight_method' in df.columns:
            weight_method_perf = df.groupby('weight_method')[performance_metrics].mean().to_dict()
            categorical_analysis['weight_methods'] = weight_method_perf
        
        return {
            'numeric_correlations': correlations,
            'categorical_analysis': categorical_analysis
        }
    
    def _analyze_factor_performance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析因子对绩效的影响"""
        # 统计每个因子的出现频率和平均绩效
        factor_stats = {}
        
        for _, row in df.iterrows():
            try:
                factors = json.loads(row['factors'])
                for factor in factors:
                    if factor not in factor_stats:
                        factor_stats[factor] = {
                            'count': 0,
                            'total_return_sum': 0,
                            'sharpe_ratio_sum': 0,
                            'returns': [],
                            'sharpes': []
                        }
                    
                    factor_stats[factor]['count'] += 1
                    if pd.notna(row['total_return']):
                        factor_stats[factor]['total_return_sum'] += row['total_return']
                        factor_stats[factor]['returns'].append(row['total_return'])
                    if pd.notna(row['sharpe_ratio']):
                        factor_stats[factor]['sharpe_ratio_sum'] += row['sharpe_ratio']
                        factor_stats[factor]['sharpes'].append(row['sharpe_ratio'])
            except:
                continue
        
        # 计算平均值
        factor_performance = {}
        for factor, stats in factor_stats.items():
            factor_performance[factor] = {
                'frequency': stats['count'],
                'avg_total_return': stats['total_return_sum'] / stats['count'] if stats['count'] > 0 else 0,
                'avg_sharpe_ratio': stats['sharpe_ratio_sum'] / stats['count'] if stats['count'] > 0 else 0,
                'return_std': pd.Series(stats['returns']).std() if stats['returns'] else 0,
                'sharpe_std': pd.Series(stats['sharpes']).std() if stats['sharpes'] else 0
            }
        
        return factor_performance
    
    def _print_key_findings(self, analysis_result: Dict[str, Any]):
        """打印关键发现"""
        print(f"\n🎯 关键发现")
        print(f"=" * 60)
        
        # Top策略
        top_by_roi = analysis_result['top_performers']['by_roi'][:5]
        print(f"\n🏆 收益率Top 5:")
        for i, strategy in enumerate(top_by_roi, 1):
            print(f"  {i}. {strategy['strategy_id']}: {strategy['total_return']:.2f}% "
                  f"(Sharpe: {strategy.get('sharpe_ratio', 'N/A'):.2f})")
        
        # 参数相关性
        correlations = analysis_result['parameter_analysis']['numeric_correlations']
        print(f"\n📈 参数相关性 (与收益率):")
        for param, corr_dict in correlations.items():
            roi_corr = corr_dict.get('total_return', 0)
            print(f"  {param}: {roi_corr:+.3f}")
        
        # 因子表现
        factor_perf = analysis_result['parameter_analysis']['categorical_analysis'].get('factors', {})
        if factor_perf:
            print(f"\n🧮 因子平均表现:")
            sorted_factors = sorted(factor_perf.items(), 
                                  key=lambda x: x[1]['avg_total_return'], 
                                  reverse=True)
            for factor, perf in sorted_factors[:5]:
                print(f"  {factor}: {perf['avg_total_return']:.2f}% "
                      f"(频次: {perf['frequency']})")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='🏭 大规模超参数调优系统')
    parser.add_argument('command', choices=['generate', 'execute', 'analyze', 'full'],
                       help='执行命令')
    
    args = parser.parse_args()
    
    try:
        system = MassHyperparameterSystem()
        
        if args.command == 'generate':
            system.generate_parameter_space()
            
        print("🎉 系统创建成功!")
            
    except KeyboardInterrupt:
        print("\n❌ 用户中断执行")
    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 