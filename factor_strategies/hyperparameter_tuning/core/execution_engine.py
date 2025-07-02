"""
批量執行引擎 - BatchExecutionEngine
實現BR-002: 真實回測執行 和 BR-003: 大規模處理
"""

import logging
import subprocess
import json
import time
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from dataclasses import dataclass

from .database_manager import DatabaseManager
from .progress_manager import ProgressManager

# 導入因子引擎
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from factor_strategies.factor_engine import FactorEngine
from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES

@dataclass
class ExecutionResult:
    """執行結果類"""
    success: bool
    strategy_id: str
    execution_time: float
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None

class BatchExecutionEngine:
    """批量執行引擎"""
    
    def __init__(self, db_manager: DatabaseManager, progress_manager: ProgressManager):
        """
        初始化批量執行引擎
        
        Args:
            db_manager: 數據庫管理器
            progress_manager: 進度管理器
        """
        self.db_manager = db_manager
        self.progress_manager = progress_manager
        self.logger = logging.getLogger(__name__)
        
        # 執行配置
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.factor_engine_path = self.project_root / "factor_strategies" / "run_factor_strategies.py"
        self.backtest_script_path = self.project_root / "backtest_v5.py"
        
        # 執行狀態
        self._is_running = False
        self._should_stop = False
        self._current_session_id = None
        
        # 性能監控
        self._execution_times = []
        self._max_history = 100
        
    def execute_batch(self, session_id: str, parallel_count: int = 4, 
                     resume: bool = False, timeout_minutes: int = 30) -> bool:
        """
        執行批量回測
        
        Args:
            session_id: 會話ID
            parallel_count: 並發數量
            resume: 是否斷點續跑
            timeout_minutes: 超時時間（分鐘）
            
        Returns:
            執行是否成功
        """
        try:
            self.logger.info(f"開始執行批量回測 - 會話: {session_id}, 並發: {parallel_count}")
            
            # 設置執行狀態
            self._is_running = True
            self._should_stop = False
            self._current_session_id = session_id
            
            # 更新會話狀態
            self.progress_manager.update_session_status(session_id, 'running')
            
            # 如果是斷點續跑，重置失敗的策略
            if resume:
                reset_count = self.progress_manager.reset_failed_strategies(session_id)
                self.logger.info(f"斷點續跑 - 重置失敗策略: {reset_count} 個")
                
            # 獲取待執行的策略
            pending_strategies = self.progress_manager.get_pending_strategies(session_id)
            if not pending_strategies:
                self.logger.info("沒有待執行的策略")
                self.progress_manager.update_session_status(session_id, 'completed')
                return True
                
            self.logger.info(f"待執行策略數量: {len(pending_strategies)}")
            
            # 執行策略
            success = self._execute_strategies_parallel(
                session_id=session_id,
                strategies=pending_strategies,
                parallel_count=parallel_count,
                timeout_minutes=timeout_minutes
            )
            
            # 更新最終狀態
            if success and not self._should_stop:
                self.progress_manager.update_session_status(session_id, 'completed')
                self.logger.info("批量回測執行完成")
            elif self._should_stop:
                self.progress_manager.update_session_status(session_id, 'paused')
                self.logger.info("批量回測被暫停")
            else:
                self.progress_manager.update_session_status(session_id, 'failed')
                self.logger.error("批量回測執行失敗")
                
            return success
            
        except Exception as e:
            self.logger.error(f"執行批量回測異常: {e}")
            self.progress_manager.update_session_status(session_id, 'failed')
            return False
        finally:
            self._is_running = False
            self._current_session_id = None
            
    def _execute_strategies_parallel(self, session_id: str, strategies: List[Dict[str, Any]], 
                                   parallel_count: int, timeout_minutes: int) -> bool:
        """並行執行策略"""
        try:
            completed_count = 0
            failed_count = 0
            
            # 使用線程池執行
            with ThreadPoolExecutor(max_workers=parallel_count) as executor:
                # 提交所有任務
                future_to_strategy = {}
                for strategy in strategies:
                    if self._should_stop:
                        break
                        
                    future = executor.submit(
                        self._execute_single_strategy,
                        strategy,
                        timeout_minutes * 60  # 轉換為秒
                    )
                    future_to_strategy[future] = strategy
                    
                # 等待任務完成
                for future in as_completed(future_to_strategy):
                    if self._should_stop:
                        break
                        
                    strategy = future_to_strategy[future]
                    queue_id = strategy['id']
                    
                    try:
                        result = future.result()
                        
                        if result.success:
                            # 更新策略狀態為完成
                            self.progress_manager.update_strategy_status(
                                queue_id=queue_id,
                                status='completed',
                                execution_time=result.execution_time
                            )
                            
                            # 保存回測結果
                            if result.result:
                                self.db_manager.save_backtest_result(
                                    session_id=session_id,
                                    strategy_id=result.strategy_id,
                                    result=result.result
                                )
                                
                            completed_count += 1
                            self.logger.info(f"策略執行成功: {result.strategy_id} ({result.execution_time:.1f}s)")
                            
                        else:
                            # 更新策略狀態為失敗
                            self.progress_manager.update_strategy_status(
                                queue_id=queue_id,
                                status='failed',
                                execution_time=result.execution_time,
                                error_message=result.error_message
                            )
                            
                            failed_count += 1
                            self.logger.error(f"策略執行失敗: {result.strategy_id} - {result.error_message}")
                            
                        # 記錄執行時間用於性能分析
                        self._record_execution_time(result.execution_time)
                        
                        # 每10個策略記錄一次進度
                        if (completed_count + failed_count) % 10 == 0:
                            self.logger.info(f"執行進度: 完成 {completed_count}, 失敗 {failed_count}")
                            
                    except Exception as e:
                        # 處理異常
                        self.progress_manager.update_strategy_status(
                            queue_id=queue_id,
                            status='failed',
                            error_message=f"執行異常: {str(e)}"
                        )
                        failed_count += 1
                        self.logger.error(f"策略執行異常: {strategy['strategy_id']} - {e}")
                        
            self.logger.info(f"並行執行完成 - 成功: {completed_count}, 失敗: {failed_count}")
            return not self._should_stop
            
        except Exception as e:
            self.logger.error(f"並行執行異常: {e}")
            return False
            
    def _execute_single_strategy(self, strategy: Dict[str, Any], timeout_seconds: int) -> ExecutionResult:
        """
        執行單個策略的真實回測
        
        Args:
            strategy: 策略信息
            timeout_seconds: 超時時間（秒）
            
        Returns:
            執行結果
        """
        strategy_id = strategy['strategy_id']
        strategy_config = strategy['strategy_config']
        
        # 如果是字符串，需要解析為字典
        if isinstance(strategy_config, str):
            strategy_config = json.loads(strategy_config)
        
        start_time = time.time()
        
        try:
            self.logger.debug(f"開始執行策略: {strategy_id}")
            
            # 更新策略狀態為運行中
            self.progress_manager.update_strategy_status(strategy['id'], 'running')
            
            # 補充完整的回測配置
            complete_config = self._build_complete_config(strategy_config)
            
            # 創建臨時配置文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(complete_config, f, indent=2)
                config_file = f.name
                
            try:
                # 步驟1: 先生成策略排行榜數據
                factor_result = self._run_factor_strategies(complete_config, timeout_seconds // 2)
                if not factor_result['success']:
                    return ExecutionResult(
                        success=False,
                        strategy_id=strategy_id,
                        execution_time=time.time() - start_time,
                        error_message=f"策略排行榜生成失敗: {factor_result['error']}"
                    )
                
                # 步驟2: 執行真實回測腳本 (BR-002: 真實回測執行)
                result = self._run_backtest_script(strategy_id, config_file, timeout_seconds // 2)
                
                execution_time = time.time() - start_time
                
                if result['success']:
                    return ExecutionResult(
                        success=True,
                        strategy_id=strategy_id,
                        execution_time=execution_time,
                        result=result['data'],
                        stdout=result.get('stdout')
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        strategy_id=strategy_id,
                        execution_time=execution_time,
                        error_message=result.get('error', 'Unknown error'),
                        stderr=result.get('stderr')
                    )
                    
            finally:
                # 清理臨時文件
                try:
                    os.unlink(config_file)
                except:
                    pass
                    
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                strategy_id=strategy_id,
                execution_time=execution_time,
                error_message=str(e)
            )
            
    def _run_backtest_script(self, strategy_id: str, config_file: str, 
                           timeout_seconds: int) -> Dict[str, Any]:
        """
        運行回測腳本
        
        Args:
            strategy_id: 策略ID
            config_file: 配置文件路徑
            timeout_seconds: 超時時間
            
        Returns:
            執行結果
        """
        try:
            # 構建命令
            cmd = [
                'python', str(self.backtest_script_path),
                '--config', config_file,
                '--strategy_id', strategy_id,
                '--output_format', 'json',
                '--quiet'  # 減少輸出
            ]
            
            self.logger.debug(f"執行命令: {' '.join(cmd)}")
            
            # 執行命令
            process = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            
            if process.returncode == 0:
                # 解析輸出結果 - 從混合輸出中提取JSON
                try:
                    # 嘗試從stdout末尾提取JSON
                    stdout_lines = process.stdout.strip().split('\n')
                    
                    # 查找最後一個看起來像JSON的部分
                    json_data = None
                    for i in range(len(stdout_lines) - 1, -1, -1):
                        line = stdout_lines[i].strip()
                        if line.startswith('{') and line.endswith('}'):
                            try:
                                json_data = json.loads(line)
                                break
                            except json.JSONDecodeError:
                                continue
                    
                    # 如果沒找到單行JSON，嘗試多行JSON
                    if json_data is None:
                        # 從最後開始向前查找JSON開始標記
                        json_start = -1
                        brace_count = 0
                        for i in range(len(stdout_lines) - 1, -1, -1):
                            line = stdout_lines[i].strip()
                            if '}' in line:
                                brace_count += line.count('}')
                            if '{' in line:
                                brace_count -= line.count('{')
                                if brace_count == 0:
                                    json_start = i
                                    break
                        
                        if json_start >= 0:
                            json_text = '\n'.join(stdout_lines[json_start:])
                            json_data = json.loads(json_text)
                    
                    if json_data:
                        return {
                            'success': True,
                            'data': json_data,
                            'stdout': process.stdout
                        }
                    else:
                        return {
                            'success': False,
                            'error': 'No valid JSON found in output',
                            'stdout': process.stdout,
                            'stderr': process.stderr
                        }
                        
                except json.JSONDecodeError as e:
                    return {
                        'success': False,
                        'error': f'JSON解析失敗: {e}',
                        'stdout': process.stdout,
                        'stderr': process.stderr
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'輸出解析異常: {e}',
                        'stdout': process.stdout,
                        'stderr': process.stderr
                    }
            else:
                return {
                    'success': False,
                    'error': f'回測腳本執行失敗 (返回碼: {process.returncode})',
                    'stdout': process.stdout,
                    'stderr': process.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'執行超時 ({timeout_seconds}秒)'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'執行異常: {str(e)}'
            }
            
    def _build_complete_config(self, strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        構建完整的回測配置，添加必要的回測參數
        
        Args:
            strategy_config: 原始策略配置
            
        Returns:
            完整的配置
        """
        # 根據factors生成strategy_name
        factors_str = '_'.join(strategy_config['factors'])
        strategy_name = f"{factors_str}_W{strategy_config['window_size']}_{strategy_config['rebalance_frequency']}D_D{strategy_config['data_period']}_S{strategy_config['selection_count']}_{strategy_config['weight_method']}"
        
        # 創建完整配置
        complete_config = strategy_config.copy()
        complete_config.update({
            'strategy_name': strategy_name,
            'start_date': '2024-12-01',  # 默認回測日期
            'end_date': '2024-12-05',
            'initial_capital': 10000,
            'position_size': 0.25,
            'fee_rate': 0.001,
            'exit_size': 1.0,
            'max_positions': 4,
            'entry_top_n': 4,
            'exit_threshold': 10,
            'position_mode': 'percentage_based'
        })
        
        return complete_config
        
    def _create_dynamic_strategy(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        將簡化的策略配置轉換為完整的FactorEngine策略配置
        
        Args:
            config: 簡化的策略配置
            
        Returns:
            完整的策略配置
        """
        # 因子名稱映射表
        factor_mapping = {
            'SR': {
                'name': 'F_sharpe',
                'function': 'calculate_sharpe_ratio',
                'input_col': 'roi_1d',
                'params': {'annualizing_factor': 365}
            },
            'DD': {
                'name': 'F_drawdown', 
                'function': 'calculate_max_drawdown',
                'input_col': 'roi_1d',
                'params': {}
            },
            'TR': {
                'name': 'F_trend',
                'function': 'calculate_trend_slope',
                'input_col': 'roi_1d',
                'params': {}
            },
            'ST': {
                'name': 'F_stability',
                'function': 'calculate_inv_std_dev',
                'input_col': 'roi_1d',
                'params': {'epsilon': 1e-9}
            },
            'WR': {
                'name': 'F_winrate',
                'function': 'calculate_win_rate',
                'input_col': 'roi_1d',
                'params': {}
            },
            'SO': {
                'name': 'F_sortino',
                'function': 'calculate_sortino_ratio',
                'input_col': 'roi_1d', 
                'params': {'annualizing_factor': 365}
            }
        }
        
        # 構建factors配置
        factors_config = {}
        for factor_code in config['factors']:
            if factor_code in factor_mapping:
                factor_info = factor_mapping[factor_code]
                factors_config[factor_info['name']] = {
                    'function': factor_info['function'],
                    'window': config['window_size'],
                    'input_col': factor_info['input_col'],
                    'params': factor_info['params']
                }
        
        # 構建完整策略配置
        strategy_config = {
            'name': f"Dynamic Strategy {config['strategy_name']}",
            'description': f"動態生成的策略：{config['factors']}",
            'data_requirements': {
                'min_data_days': config['data_period'],
                'skip_first_n_days': 3,
            },
            'factors': factors_config,
            'ranking_logic': {
                'indicators': list(factors_config.keys()),
                'weights': [1.0 / len(factors_config)] * len(factors_config)  # 均等權重
            }
        }
        
        return strategy_config

    def _run_factor_strategies(self, config: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
        """
        運行因子策略生成排行榜數據 - 使用FactorEngine直接執行
        
        Args:
            config: 完整的策略配置
            timeout_seconds: 超時時間
            
        Returns:
            執行結果
        """
        try:
            strategy_name = config['strategy_name']
            
            # 創建動態策略配置
            dynamic_strategy_config = self._create_dynamic_strategy(config)
            
            # 動態添加到FACTOR_STRATEGIES字典
            FACTOR_STRATEGIES[strategy_name] = dynamic_strategy_config
            
            self.logger.debug(f"動態添加策略: {strategy_name}")
            self.logger.debug(f"策略配置: {dynamic_strategy_config}")
            
            # 創建FactorEngine實例
            engine = FactorEngine()
            
            # 執行策略 - 使用固定日期範圍生成數據
            target_date = '2024-12-04'  # 使用較晚的日期確保有足夠歷史數據
            result_df = engine.run_strategy(strategy_name, target_date, save_to_db=True)
            
            if not result_df.empty:
                return {
                    'success': True,
                    'message': f'成功生成 {len(result_df)} 條排行榜記錄',
                    'records_count': len(result_df)
                }
            else:
                return {
                    'success': False,
                    'error': '策略執行成功但沒有生成排行榜數據'
                }
                
        except Exception as e:
            self.logger.error(f"動態策略執行異常: {e}")
            return {
                'success': False,
                'error': f'動態策略執行異常: {str(e)}'
            }
        finally:
            # 清理動態添加的策略配置（可選）
            if strategy_name in FACTOR_STRATEGIES:
                # 可以選擇保留或刪除
                pass
            
    def _record_execution_time(self, execution_time: float):
        """記錄執行時間用於性能分析"""
        self._execution_times.append(execution_time)
        if len(self._execution_times) > self._max_history:
            self._execution_times.pop(0)
            
    def get_performance_stats(self) -> Dict[str, Any]:
        """獲取性能統計"""
        if not self._execution_times:
            return {}
            
        times = self._execution_times
        return {
            'total_executions': len(times),
            'avg_time': sum(times) / len(times),
            'min_time': min(times),
            'max_time': max(times),
            'recent_avg': sum(times[-10:]) / min(10, len(times))
        }
        
    def stop_execution(self):
        """停止執行"""
        self.logger.info("收到停止執行信號")
        self._should_stop = True
        
    def is_running(self) -> bool:
        """檢查是否正在執行"""
        return self._is_running
        
    def get_current_session(self) -> Optional[str]:
        """獲取當前執行的會話ID"""
        return self._current_session_id
        
    def validate_environment(self) -> Dict[str, Any]:
        """驗證執行環境"""
        issues = []
        
        # 檢查關鍵文件是否存在
        if not self.backtest_script_path.exists():
            issues.append(f"回測腳本不存在: {self.backtest_script_path}")
            
        if not self.factor_engine_path.exists():
            issues.append(f"因子引擎不存在: {self.factor_engine_path}")
            
        # 檢查Python環境
        try:
            result = subprocess.run(['python', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            python_version = result.stdout.strip()
        except Exception as e:
            issues.append(f"Python環境檢查失敗: {e}")
            python_version = "未知"
            
        # 檢查必要的Python模塊
        required_modules = ['pandas', 'numpy', 'sqlite3']
        missing_modules = []
        
        for module in required_modules:
            try:
                subprocess.run(['python', '-c', f'import {module}'], 
                             capture_output=True, timeout=5, check=True)
            except:
                missing_modules.append(module)
                
        if missing_modules:
            issues.append(f"缺少必要模塊: {missing_modules}")
            
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'python_version': python_version,
            'backtest_script': str(self.backtest_script_path),
            'factor_engine': str(self.factor_engine_path),
            'project_root': str(self.project_root)
        } 