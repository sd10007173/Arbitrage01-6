#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量執行器
負責批量運行策略回測並收集結果
"""

import os
import sys
import json
import time
import subprocess
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import tempfile

# 添加父目錄到 Python 路徑以導入真實模組
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

# 設置正確的數據庫路徑
MAIN_DB_PATH = os.path.join(project_root, "data", "funding_rate.db")

# 導入真實的模組
from factor_strategies.factor_engine import FactorEngine
from backtest_v5 import FundingRateBacktest


class BatchRunner:
    """批量執行器"""
    
    def __init__(self, config: Dict[str, Any], output_dir: str):
        """
        初始化批量執行器
        :param config: 配置字典
        :param output_dir: 輸出目錄
        """
        self.config = config
        self.output_dir = output_dir
        self.backtest_config = config['backtest']
        self.execution_config = config['execution']
        
        # 設置日誌
        self._setup_logging()
        
        # 結果存儲
        self.results = []
        self.failed_strategies = []
        
    def _setup_logging(self):
        """設置日誌"""
        log_dir = os.path.join(self.output_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'batch_execution_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def run_batch_backtest(self, strategy_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量運行回測
        :param strategy_configs: 策略配置列表
        :return: 執行結果統計
        """
        total_strategies = len(strategy_configs)
        self.logger.info(f"🚀 開始批量回測，共 {total_strategies} 個策略")
        
        start_time = time.time()
        
        # 並行執行
        max_workers = self.execution_config.get('max_parallel_jobs', 4)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任務
            future_to_strategy = {
                executor.submit(self._run_single_strategy, strategy_config): strategy_config
                for strategy_config in strategy_configs
            }
            
            # 收集結果
            completed = 0
            for future in as_completed(future_to_strategy):
                strategy_config = future_to_strategy[future]
                completed += 1
                
                try:
                    result = future.result()
                    if result:
                        self.results.append(result)
                        self.logger.info(f"✅ ({completed}/{total_strategies}) 策略 {strategy_config['strategy_id']} 完成")
                    else:
                        self.failed_strategies.append(strategy_config['strategy_id'])
                        self.logger.error(f"❌ ({completed}/{total_strategies}) 策略 {strategy_config['strategy_id']} 失敗")
                        
                except Exception as e:
                    self.failed_strategies.append(strategy_config['strategy_id'])
                    self.logger.error(f"❌ ({completed}/{total_strategies}) 策略 {strategy_config['strategy_id']} 異常: {str(e)}")
                
                # 顯示進度
                if completed % 10 == 0:
                    progress = (completed / total_strategies) * 100
                    elapsed_time = time.time() - start_time
                    avg_time_per_strategy = elapsed_time / completed
                    estimated_remaining = avg_time_per_strategy * (total_strategies - completed)
                    
                    self.logger.info(f"📊 進度: {completed}/{total_strategies} ({progress:.1f}%) - "
                                   f"平均耗時: {avg_time_per_strategy:.1f}s - "
                                   f"預估剩餘: {estimated_remaining/60:.1f}分鐘")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 統計結果
        execution_stats = {
            'total_strategies': total_strategies,
            'successful': len(self.results),
            'failed': len(self.failed_strategies),
            'success_rate': len(self.results) / total_strategies * 100,
            'execution_time_seconds': execution_time,
            'execution_time_minutes': execution_time / 60,
            'average_time_per_strategy': execution_time / total_strategies,
            'failed_strategy_ids': self.failed_strategies
        }
        
        self.logger.info(f"🎯 批量回測完成！")
        self.logger.info(f"   - 總策略數: {total_strategies}")
        self.logger.info(f"   - 成功: {len(self.results)}")
        self.logger.info(f"   - 失敗: {len(self.failed_strategies)}")
        self.logger.info(f"   - 成功率: {execution_stats['success_rate']:.1f}%")
        self.logger.info(f"   - 總耗時: {execution_time/60:.1f} 分鐘")
        
        return execution_stats
    
    def _run_single_strategy(self, strategy_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        運行單個策略
        :param strategy_config: 策略配置
        :return: 策略結果
        """
        strategy_id = strategy_config['strategy_id']
        
        try:
            # 第1步：運行因子策略生成排行榜
            ranking_result = self._run_factor_strategy(strategy_config)
            if not ranking_result:
                self.logger.error(f"因子策略運行失敗: {strategy_id}")
                return None
            
            # 第2步：運行回測
            backtest_result = self._run_backtest(strategy_id, ranking_result)
            if not backtest_result:
                self.logger.error(f"回測運行失敗: {strategy_id}")
                return None
            
            # 第3步：合併結果
            combined_result = {
                'strategy_id': strategy_id,
                'strategy_config': strategy_config,
                'ranking_result': ranking_result,
                'backtest_result': backtest_result,
                'execution_time': datetime.now().isoformat()
            }
            
            # 第4步：保存中間結果（可選）
            if self.execution_config.get('save_intermediate_results', False):
                self._save_intermediate_result(combined_result)
            
            return combined_result
            
        except Exception as e:
            self.logger.error(f"策略 {strategy_id} 執行異常: {str(e)}")
            return None
    
    def _run_factor_strategy(self, strategy_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        運行因子策略 - 使用真實的 FactorEngine
        :param strategy_config: 策略配置
        :return: 因子策略結果
        """
        try:
            # 創建策略配置並註冊到 FactorEngine
            factor_strategy_name = self._register_strategy_to_factor_engine(strategy_config)
            
            # 初始化 FactorEngine，使用正確的數據庫路徑
            engine = FactorEngine(db_path=MAIN_DB_PATH)
            
            # 獲取回測日期範圍
            start_date = self.backtest_config['start_date']
            end_date = self.backtest_config['end_date']
            
            # 為回測期間內的每一天生成因子策略排行榜
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            successful_days = 0
            total_days = 0
            
            current_dt = start_dt
            while current_dt <= end_dt:
                date_str = current_dt.strftime('%Y-%m-%d')
                total_days += 1
                
                try:
                    # 檢查數據充足性
                    is_sufficient, message = engine.check_data_sufficiency(factor_strategy_name, date_str)
                    if not is_sufficient:
                        self.logger.debug(f"跳過 {date_str}: {message}")
                        current_dt += timedelta(days=1)
                        continue
                    
                    # 運行策略
                    result = engine.run_strategy(factor_strategy_name, date_str)
                    if not result.empty:
                        successful_days += 1
                        
                except Exception as e:
                    self.logger.debug(f"日期 {date_str} 執行失敗: {str(e)}")
                
                current_dt += timedelta(days=1)
            
            # 清理臨時註冊的策略
            self._unregister_strategy_from_factor_engine(factor_strategy_name)
            
            ranking_result = {
                'strategy_name': factor_strategy_name,
                'start_date': start_date,
                'end_date': end_date,
                'total_days': total_days,
                'successful_days': successful_days,
                'success_rate': successful_days / total_days * 100 if total_days > 0 else 0
            }
            
            return ranking_result
            
        except Exception as e:
            self.logger.error(f"因子策略運行失敗: {str(e)}")
            return None
    
    def _run_backtest(self, strategy_id: str, ranking_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        運行回測 - 使用真實的 FundingRateBacktest
        :param strategy_id: 策略ID
        :param ranking_result: 因子策略結果
        :return: 回測結果
        """
        try:
            # 保存當前工作目錄
            original_cwd = os.getcwd()
            
            # 切換到項目根目錄，確保回測引擎能找到正確的數據庫路徑
            current_dir = os.path.dirname(os.path.abspath(__file__))  # hyperparameter_tuning
            factor_strategies_dir = os.path.dirname(current_dir)      # factor_strategies  
            project_root = os.path.dirname(factor_strategies_dir)     # Arbitrage01-3
            os.chdir(project_root)
            
            try:
                # 初始化回測引擎
                backtest_engine = FundingRateBacktest(
                    initial_capital=self.backtest_config.get('initial_capital', 10000),
                    position_size=self.backtest_config.get('position_size', 0.25),
                    fee_rate=self.backtest_config.get('fee_rate', 0.001),
                    exit_size=self.backtest_config.get('exit_size', 1.0),
                    max_positions=self.backtest_config.get('max_positions', 4),
                    entry_top_n=self.backtest_config.get('entry_top_n', 4),
                    exit_threshold=self.backtest_config.get('exit_threshold', 10),
                    position_mode=self.backtest_config.get('position_mode', 'percentage_based')
                )
                
                # 運行回測
                strategy_name = ranking_result['strategy_name']
                start_date = ranking_result['start_date']
                end_date = ranking_result['end_date']
                
                # 添加調試信息
                self.logger.info(f"🔍 準備回測策略: {strategy_name}")
                self.logger.info(f"📅 回測期間: {start_date} 至 {end_date}")
                
                backtest_engine.run_backtest(strategy_name, start_date, end_date)
                
            finally:
                # 恢復原始工作目錄
                os.chdir(original_cwd)
            
            # 提取回測結果
            backtest_summary = {
                'strategy_id': strategy_id,
                'strategy_name': strategy_name,
                'start_date': start_date,
                'end_date': end_date,
                'initial_capital': backtest_engine.initial_capital,
                'final_capital': backtest_engine.total_balance,
                'total_return': backtest_engine.total_balance - backtest_engine.initial_capital,
                'roi': (backtest_engine.total_balance - backtest_engine.initial_capital) / backtest_engine.initial_capital,
                'max_drawdown': backtest_engine.max_drawdown,
                'sharpe_ratio': backtest_engine.calculate_sharpe_ratio(),
                'win_rate': backtest_engine.calculate_win_rate(),
                'total_trades': len(backtest_engine.holding_periods),
                'avg_holding_days': backtest_engine.calculate_average_holding_days(),
                'backtest_days': backtest_engine.backtest_days,
                'status': 'completed'
            }
            
            return backtest_summary
            
        except Exception as e:
            self.logger.error(f"回測運行失敗: {str(e)}")
            return None
    
    def _register_strategy_to_factor_engine(self, strategy_config: Dict[str, Any]) -> str:
        """
        將超參數調優的策略配置轉換為 factor_strategy_config 格式並註冊
        :param strategy_config: 超參數調優策略配置
        :return: 註冊的策略名稱
        """
        # 動態導入並修改 factor_strategy_config
        from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES
        
        strategy_name = strategy_config['strategy_id']
        
        # 轉換因子配置
        factors = {}
        for i, factor_cfg in enumerate(strategy_config['factors']):
            factor_name = f"F_{factor_cfg['function'].replace('calculate_', '')}"
            factors[factor_name] = {
                'function': factor_cfg['function'],
                'window': factor_cfg['window'],
                'input_col': factor_cfg['input_column']
            }
        
        # 生成權重（根據權重方法）
        num_factors = len(strategy_config['factors'])
        weights = self._generate_weights(num_factors, strategy_config['scoring']['method'])
        
        # 創建 factor_strategy_config 格式的配置
        factor_strategy = {
            'name': strategy_config['strategy_name'],
            'description': f"超參數調優生成的策略: {strategy_name}",
            'data_requirements': {
                'min_data_days': strategy_config['data_requirements']['min_data_days'],
                'skip_first_n_days': strategy_config['data_requirements']['skip_first_n_days']
            },
            'factors': factors,
            'ranking_logic': {
                'indicators': list(factors.keys()),
                'weights': weights
            }
        }
        
        # 註冊策略
        FACTOR_STRATEGIES[strategy_name] = factor_strategy
        
        return strategy_name
    
    def _unregister_strategy_from_factor_engine(self, strategy_name: str):
        """移除臨時註冊的策略"""
        from factor_strategies.factor_strategy_config import FACTOR_STRATEGIES
        if strategy_name in FACTOR_STRATEGIES:
            del FACTOR_STRATEGIES[strategy_name]
    
    def _generate_weights(self, num_factors: int, weight_method: str) -> List[float]:
        """
        根據權重方法生成因子權重
        :param num_factors: 因子數量
        :param weight_method: 權重方法
        :return: 權重列表
        """
        if weight_method == 'equal':
            return [1.0 / num_factors] * num_factors
        elif weight_method == 'inverse_correlation':
            # 暫時使用等權重，後續可以實現真實的反相關權重計算
            return [1.0 / num_factors] * num_factors
        elif weight_method == 'factor_strength':
            # 暫時使用等權重，後續可以實現基於歷史績效的權重計算
            return [1.0 / num_factors] * num_factors
        else:
            return [1.0 / num_factors] * num_factors
    
    def _save_intermediate_result(self, result: Dict[str, Any]):
        """保存中間結果"""
        results_dir = os.path.join(self.output_dir, 'intermediate_results')
        os.makedirs(results_dir, exist_ok=True)
        
        filename = f"{result['strategy_id']}_result.json"
        filepath = os.path.join(results_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    
    def save_final_results(self) -> str:
        """
        保存最終結果
        :return: 結果文件路徑
        """
        results_dir = os.path.join(self.output_dir, 'final_results')
        os.makedirs(results_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = os.path.join(results_dir, f'batch_results_{timestamp}.json')
        
        final_results = {
            'execution_summary': {
                'total_strategies': len(self.results) + len(self.failed_strategies),
                'successful_strategies': len(self.results),
                'failed_strategies': len(self.failed_strategies),
                'success_rate': len(self.results) / (len(self.results) + len(self.failed_strategies)) * 100 if (len(self.results) + len(self.failed_strategies)) > 0 else 0,
                'execution_timestamp': datetime.now().isoformat()
            },
            'results': self.results,
            'failed_strategy_ids': self.failed_strategies
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"💾 最終結果已保存到: {results_file}")
        return results_file
    
    def get_results(self) -> List[Dict[str, Any]]:
        """獲取所有結果"""
        return self.results
    
    def get_failed_strategies(self) -> List[str]:
        """獲取失敗的策略ID列表"""
        return self.failed_strategies


def main():
    """測試函數"""
    import yaml
    from param_generator import ParameterGenerator
    
    # 載入配置
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 生成少量策略用於測試
    config['execution']['mode'] = 'sampling'
    config['execution']['n_strategies'] = 3  # 測試用少量策略
    
    generator = ParameterGenerator(config)
    strategies = generator.generate_sample_combinations(3)
    
    print(f"🧪 測試模式：運行 {len(strategies)} 個策略")
    
    # 創建批量執行器
    output_dir = 'results/test_real_backtest'
    os.makedirs(output_dir, exist_ok=True)
    runner = BatchRunner(config, output_dir)
    
    # 運行批量回測
    stats = runner.run_batch_backtest(strategies)
    
    print("\n📊 執行統計:")
    for key, value in stats.items():
        if key != 'failed_strategy_ids':
            print(f"  - {key}: {value}")
    
    # 保存結果
    results_file = runner.save_final_results()
    print(f"\n💾 結果已保存到: {results_file}")


if __name__ == "__main__":
    main() 