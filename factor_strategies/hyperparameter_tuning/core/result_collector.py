"""
結果收集器 - ResultCollector
負責收集、處理和匯總回測結果
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .database_manager import DatabaseManager

@dataclass
class PerformanceMetrics:
    """性能指標類"""
    strategy_id: str
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    
class ResultCollector:
    """結果收集器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化結果收集器
        
        Args:
            db_manager: 數據庫管理器
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
    def collect_results(self, session_id: str, strategy_id: str, 
                       backtest_result: Dict[str, Any]) -> bool:
        """
        收集單個策略的回測結果
        
        Args:
            session_id: 會話ID
            strategy_id: 策略ID
            backtest_result: 回測結果
            
        Returns:
            是否成功
        """
        try:
            # 保存到數據庫
            self.db_manager.save_backtest_result(session_id, strategy_id, backtest_result)
            
            self.logger.debug(f"收集結果成功: {strategy_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"收集結果失敗 {strategy_id}: {e}")
            return False
            
    def get_session_results(self, session_id: str, limit: int = None, 
                          sort_by: str = "sharpe_ratio") -> List[Dict[str, Any]]:
        """
        獲取會話的所有結果
        
        Args:
            session_id: 會話ID
            limit: 限制數量
            sort_by: 排序字段
            
        Returns:
            結果列表
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 構建查詢
                query = '''
                    SELECT strategy_id, factors, window_size, rebalance_frequency,
                           data_period, selection_count, weight_method,
                           total_return, annual_return, sharpe_ratio, max_drawdown,
                           win_rate, trade_count, start_date, end_date
                    FROM backtest_results 
                    WHERE session_id = ?
                '''
                
                # 添加排序
                if sort_by in ['sharpe_ratio', 'annual_return', 'total_return']:
                    query += f' ORDER BY {sort_by} DESC'
                else:
                    query += ' ORDER BY sharpe_ratio DESC'
                    
                # 添加限制
                if limit:
                    query += f' LIMIT {limit}'
                    
                cursor.execute(query, (session_id,))
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    result = dict(row)
                    # 解析factors字段
                    if result['factors']:
                        result['factors'] = json.loads(result['factors'])
                    results.append(result)
                    
                return results
                
        except Exception as e:
            self.logger.error(f"獲取會話結果失敗: {e}")
            return []
            
    def get_top_performers(self, session_id: str, top_n: int = 10, 
                          metric: str = "sharpe_ratio") -> List[PerformanceMetrics]:
        """
        獲取最佳表現的策略
        
        Args:
            session_id: 會話ID
            top_n: 前N個
            metric: 評估指標
            
        Returns:
            最佳策略列表
        """
        try:
            results = self.get_session_results(session_id, limit=top_n, sort_by=metric)
            
            performers = []
            for result in results:
                metrics = PerformanceMetrics(
                    strategy_id=result['strategy_id'],
                    total_return=result['total_return'] or 0,
                    annual_return=result['annual_return'] or 0,
                    sharpe_ratio=result['sharpe_ratio'] or 0,
                    max_drawdown=result['max_drawdown'] or 0,
                    win_rate=result['win_rate'] or 0,
                    trade_count=result['trade_count'] or 0
                )
                performers.append(metrics)
                
            return performers
            
        except Exception as e:
            self.logger.error(f"獲取最佳表現策略失敗: {e}")
            return []
            
    def generate_summary_report(self, session_id: str) -> Dict[str, Any]:
        """
        生成會話的匯總報告
        
        Args:
            session_id: 會話ID
            
        Returns:
            匯總報告
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 獲取基本統計
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_strategies,
                        AVG(total_return) as avg_total_return,
                        AVG(annual_return) as avg_annual_return,
                        AVG(sharpe_ratio) as avg_sharpe_ratio,
                        AVG(max_drawdown) as avg_max_drawdown,
                        AVG(win_rate) as avg_win_rate,
                        MAX(sharpe_ratio) as best_sharpe_ratio,
                        MIN(sharpe_ratio) as worst_sharpe_ratio,
                        MAX(annual_return) as best_annual_return,
                        MIN(annual_return) as worst_annual_return
                    FROM backtest_results 
                    WHERE session_id = ?
                ''', (session_id,))
                
                stats = dict(cursor.fetchone())
                
                # 獲取最佳策略
                best_strategies = self.get_top_performers(session_id, top_n=5)
                
                # 獲取參數分布統計
                param_stats = self._analyze_parameter_performance(session_id)
                
                report = {
                    'session_id': session_id,
                    'statistics': {
                        'total_strategies': stats['total_strategies'],
                        'avg_total_return': round(stats['avg_total_return'] or 0, 4),
                        'avg_annual_return': round(stats['avg_annual_return'] or 0, 4),
                        'avg_sharpe_ratio': round(stats['avg_sharpe_ratio'] or 0, 4),
                        'avg_max_drawdown': round(stats['avg_max_drawdown'] or 0, 4),
                        'avg_win_rate': round(stats['avg_win_rate'] or 0, 4),
                        'best_sharpe_ratio': round(stats['best_sharpe_ratio'] or 0, 4),
                        'worst_sharpe_ratio': round(stats['worst_sharpe_ratio'] or 0, 4),
                        'best_annual_return': round(stats['best_annual_return'] or 0, 4),
                        'worst_annual_return': round(stats['worst_annual_return'] or 0, 4)
                    },
                    'best_strategies': [
                        {
                            'strategy_id': p.strategy_id,
                            'total_return': round(p.total_return, 4),
                            'annual_return': round(p.annual_return, 4),
                            'sharpe_ratio': round(p.sharpe_ratio, 4),
                            'max_drawdown': round(p.max_drawdown, 4),
                            'win_rate': round(p.win_rate, 4),
                            'trade_count': p.trade_count
                        }
                        for p in best_strategies
                    ],
                    'parameter_analysis': param_stats
                }
                
                return report
                
        except Exception as e:
            self.logger.error(f"生成匯總報告失敗: {e}")
            return {'error': str(e)}
            
    def _analyze_parameter_performance(self, session_id: str) -> Dict[str, Any]:
        """分析參數與性能的關聯性"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 分析各參數的平均表現
                analysis = {}
                
                # 窗口大小分析
                cursor.execute('''
                    SELECT window_size, 
                           AVG(sharpe_ratio) as avg_sharpe,
                           AVG(annual_return) as avg_return,
                           COUNT(*) as count
                    FROM backtest_results 
                    WHERE session_id = ? AND sharpe_ratio IS NOT NULL
                    GROUP BY window_size
                    ORDER BY avg_sharpe DESC
                ''', (session_id,))
                
                window_analysis = []
                for row in cursor.fetchall():
                    window_analysis.append({
                        'window_size': row['window_size'],
                        'avg_sharpe_ratio': round(row['avg_sharpe'], 4),
                        'avg_annual_return': round(row['avg_return'], 4),
                        'strategy_count': row['count']
                    })
                analysis['window_size'] = window_analysis
                
                # 重平衡頻率分析
                cursor.execute('''
                    SELECT rebalance_frequency,
                           AVG(sharpe_ratio) as avg_sharpe,
                           AVG(annual_return) as avg_return,
                           COUNT(*) as count
                    FROM backtest_results 
                    WHERE session_id = ? AND sharpe_ratio IS NOT NULL
                    GROUP BY rebalance_frequency
                    ORDER BY avg_sharpe DESC
                ''', (session_id,))
                
                rebal_analysis = []
                for row in cursor.fetchall():
                    rebal_analysis.append({
                        'rebalance_frequency': row['rebalance_frequency'],
                        'avg_sharpe_ratio': round(row['avg_sharpe'], 4),
                        'avg_annual_return': round(row['avg_return'], 4),
                        'strategy_count': row['count']
                    })
                analysis['rebalance_frequency'] = rebal_analysis
                
                # 權重方法分析
                cursor.execute('''
                    SELECT weight_method,
                           AVG(sharpe_ratio) as avg_sharpe,
                           AVG(annual_return) as avg_return,
                           COUNT(*) as count
                    FROM backtest_results 
                    WHERE session_id = ? AND sharpe_ratio IS NOT NULL
                    GROUP BY weight_method
                    ORDER BY avg_sharpe DESC
                ''', (session_id,))
                
                weight_analysis = []
                for row in cursor.fetchall():
                    weight_analysis.append({
                        'weight_method': row['weight_method'],
                        'avg_sharpe_ratio': round(row['avg_sharpe'], 4),
                        'avg_annual_return': round(row['avg_return'], 4),
                        'strategy_count': row['count']
                    })
                analysis['weight_method'] = weight_analysis
                
                return analysis
                
        except Exception as e:
            self.logger.error(f"參數性能分析失敗: {e}")
            return {}
            
    def export_results(self, session_id: str, format: str = "json", 
                      file_path: str = None) -> Optional[str]:
        """
        導出結果到文件
        
        Args:
            session_id: 會話ID
            format: 導出格式 ("json", "csv")
            file_path: 文件路徑
            
        Returns:
            導出的文件路徑
        """
        try:
            results = self.get_session_results(session_id)
            if not results:
                self.logger.warning(f"會話 {session_id} 沒有結果可導出")
                return None
                
            if file_path is None:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"results_{session_id}_{timestamp}.{format}"
                
            if format == "json":
                self._export_to_json(results, file_path)
            elif format == "csv":
                self._export_to_csv(results, file_path)
            else:
                raise ValueError(f"不支持的導出格式: {format}")
                
            self.logger.info(f"結果導出成功: {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"導出結果失敗: {e}")
            return None
            
    def _export_to_json(self, results: List[Dict[str, Any]], file_path: str):
        """導出為JSON格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
    def _export_to_csv(self, results: List[Dict[str, Any]], file_path: str):
        """導出為CSV格式"""
        if not results:
            return
            
        import csv
        
        # 獲取所有字段名
        fieldnames = list(results[0].keys())
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                # 處理複雜字段
                row = result.copy()
                if 'factors' in row and isinstance(row['factors'], list):
                    row['factors'] = ','.join(row['factors'])
                writer.writerow(row)
                
    def get_comparison_report(self, session_ids: List[str]) -> Dict[str, Any]:
        """
        生成多個會話的對比報告
        
        Args:
            session_ids: 會話ID列表
            
        Returns:
            對比報告
        """
        try:
            comparison = {
                'sessions': [],
                'best_overall': None
            }
            
            best_sharpe = float('-inf')
            best_strategy = None
            
            for session_id in session_ids:
                report = self.generate_summary_report(session_id)
                if 'error' not in report:
                    comparison['sessions'].append({
                        'session_id': session_id,
                        'statistics': report['statistics'],
                        'best_strategy': report['best_strategies'][0] if report['best_strategies'] else None
                    })
                    
                    # 找出最佳策略
                    if report['best_strategies']:
                        top_strategy = report['best_strategies'][0]
                        if top_strategy['sharpe_ratio'] > best_sharpe:
                            best_sharpe = top_strategy['sharpe_ratio']
                            best_strategy = {
                                'session_id': session_id,
                                **top_strategy
                            }
                            
            comparison['best_overall'] = best_strategy
            return comparison
            
        except Exception as e:
            self.logger.error(f"生成對比報告失敗: {e}")
            return {'error': str(e)} 