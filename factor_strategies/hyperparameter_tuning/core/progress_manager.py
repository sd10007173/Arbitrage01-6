"""
進度管理器 - ProgressManager
負責管理執行進度、斷點續跑、錯誤恢復等功能
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from .database_manager import DatabaseManager

@dataclass
class SessionInfo:
    """會話信息類"""
    session_id: str
    mode: str
    total_strategies: int
    completed_strategies: int
    failed_strategies: int
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress_percent: float = 0.0
    estimated_remaining_time: Optional[float] = None

@dataclass
class ExecutionStats:
    """執行統計類"""
    total_count: int
    pending_count: int
    running_count: int
    completed_count: int
    failed_count: int
    avg_execution_time: float
    success_rate: float
    estimated_total_time: float

class ProgressManager:
    """進度管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化進度管理器
        
        Args:
            db_manager: 數據庫管理器
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 執行統計緩存
        self._stats_cache = {}
        self._cache_ttl = 30  # 緩存有效期30秒
        
    def create_session(self, mode: str, total_strategies: int, 
                      config_data: Dict[str, Any] = None, notes: str = None) -> str:
        """
        創建新的調優會話
        
        Args:
            mode: 執行模式
            total_strategies: 總策略數量
            config_data: 配置數據
            notes: 備註
            
        Returns:
            會話ID
        """
        try:
            session_id = self.db_manager.create_session(
                mode=mode,
                total_strategies=total_strategies,
                config_data=config_data,
                notes=notes
            )
            
            # 記錄創建日誌
            self.db_manager.log_execution(
                session_id=session_id,
                level="INFO",
                message=f"創建會話 - 模式: {mode}, 策略數量: {total_strategies}"
            )
            
            self.logger.info(f"創建會話成功: {session_id}")
            return session_id
            
        except Exception as e:
            self.logger.error(f"創建會話失敗: {e}")
            raise
            
    def add_strategies_to_queue(self, session_id: str, strategies: List[Dict[str, Any]]):
        """
        添加策略到執行隊列
        
        Args:
            session_id: 會話ID
            strategies: 策略配置列表
        """
        try:
            self.db_manager.add_strategies_to_queue(session_id, strategies)
            
            # 記錄添加日誌
            self.db_manager.log_execution(
                session_id=session_id,
                level="INFO",
                message=f"添加 {len(strategies)} 個策略到執行隊列"
            )
            
            self.logger.info(f"添加策略到隊列成功: {len(strategies)} 個")
            
        except Exception as e:
            self.logger.error(f"添加策略到隊列失敗: {e}")
            raise
            
    def get_pending_strategies(self, session_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        獲取待執行的策略
        
        Args:
            session_id: 會話ID
            limit: 限制數量
            
        Returns:
            待執行的策略列表
        """
        try:
            strategies = self.db_manager.get_pending_strategies(session_id, limit)
            self.logger.debug(f"獲取待執行策略: {len(strategies)} 個")
            return strategies
            
        except Exception as e:
            self.logger.error(f"獲取待執行策略失敗: {e}")
            raise
            
    def update_session_status(self, session_id: str, status: str):
        """
        更新會話狀態
        
        Args:
            session_id: 會話ID
            status: 新狀態 ('created', 'running', 'completed', 'failed', 'paused')
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                if status == 'running':
                    cursor.execute('''
                        UPDATE tuning_sessions 
                        SET status = ?, started_at = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    ''', (status, session_id))
                elif status in ['completed', 'failed']:
                    cursor.execute('''
                        UPDATE tuning_sessions 
                        SET status = ?, completed_at = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    ''', (status, session_id))
                else:
                    cursor.execute('''
                        UPDATE tuning_sessions 
                        SET status = ?
                        WHERE session_id = ?
                    ''', (status, session_id))
                    
                conn.commit()
                
            # 記錄狀態變更日誌
            self.db_manager.log_execution(
                session_id=session_id,
                level="INFO",
                message=f"會話狀態變更: {status}"
            )
            
        except Exception as e:
            self.logger.error(f"更新會話狀態失敗: {e}")
            raise
            
    def update_strategy_status(self, queue_id: int, status: str, 
                             execution_time: float = None, error_message: str = None):
        """
        更新策略執行狀態
        
        Args:
            queue_id: 隊列記錄ID
            status: 新狀態
            execution_time: 執行時間（秒）
            error_message: 錯誤消息
        """
        try:
            self.db_manager.update_strategy_status(
                queue_id=queue_id,
                status=status,
                execution_time=execution_time,
                error_message=error_message
            )
            
            # 清除統計緩存
            self._clear_stats_cache()
            
        except Exception as e:
            self.logger.error(f"更新策略狀態失敗: {e}")
            raise
            
    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """
        獲取會話信息
        
        Args:
            session_id: 會話ID
            
        Returns:
            會話信息對象
        """
        try:
            status_data = self.db_manager.get_session_status(session_id)
            
            if "error" in status_data:
                return None
                
            # 計算進度百分比
            total = status_data['total_strategies']
            completed = status_data.get('completed_strategies', 0)
            failed = status_data.get('failed_strategies', 0)
            
            progress_percent = ((completed + failed) / total * 100) if total > 0 else 0
            
            # 計算預估剩餘時間
            estimated_remaining_time = self._calculate_estimated_time(session_id, status_data)
            
            session_info = SessionInfo(
                session_id=session_id,
                mode=status_data['mode'],
                total_strategies=total,
                completed_strategies=completed,
                failed_strategies=failed,
                status=status_data['status'],
                created_at=status_data['created_at'],
                started_at=status_data.get('started_at'),
                completed_at=status_data.get('completed_at'),
                progress_percent=progress_percent,
                estimated_remaining_time=estimated_remaining_time
            )
            
            return session_info
            
        except Exception as e:
            self.logger.error(f"獲取會話信息失敗: {e}")
            return None
            
    def get_execution_stats(self, session_id: str, use_cache: bool = True) -> Optional[ExecutionStats]:
        """
        獲取執行統計信息
        
        Args:
            session_id: 會話ID
            use_cache: 是否使用緩存
            
        Returns:
            執行統計對象
        """
        try:
            # 檢查緩存
            if use_cache and session_id in self._stats_cache:
                cached_stats, cached_time = self._stats_cache[session_id]
                if time.time() - cached_time < self._cache_ttl:
                    return cached_stats
                    
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 獲取狀態統計
                cursor.execute('''
                    SELECT 
                        status,
                        COUNT(*) as count,
                        AVG(execution_time_seconds) as avg_time
                    FROM strategy_queue 
                    WHERE session_id = ? 
                    GROUP BY status
                ''', (session_id,))
                
                status_counts = {}
                total_avg_time = 0
                completed_count = 0
                
                for row in cursor.fetchall():
                    status = row['status']
                    count = row['count']
                    avg_time = row['avg_time'] or 0
                    
                    status_counts[status] = count
                    
                    if status == 'completed' and avg_time > 0:
                        total_avg_time = avg_time
                        completed_count = count
                        
                # 獲取總數
                cursor.execute('''
                    SELECT COUNT(*) as total FROM strategy_queue WHERE session_id = ?
                ''', (session_id,))
                total_count = cursor.fetchone()['total']
                
                # 構建統計對象
                pending_count = status_counts.get('pending', 0)
                running_count = status_counts.get('running', 0)
                completed_count = status_counts.get('completed', 0)
                failed_count = status_counts.get('failed', 0)
                
                success_rate = (completed_count / (completed_count + failed_count) * 100) if (completed_count + failed_count) > 0 else 0
                
                # 估算總時間
                estimated_total_time = 0
                if total_avg_time > 0 and total_count > 0:
                    estimated_total_time = total_avg_time * total_count
                    
                stats = ExecutionStats(
                    total_count=total_count,
                    pending_count=pending_count,
                    running_count=running_count,
                    completed_count=completed_count,
                    failed_count=failed_count,
                    avg_execution_time=total_avg_time,
                    success_rate=success_rate,
                    estimated_total_time=estimated_total_time
                )
                
                # 更新緩存
                if use_cache:
                    self._stats_cache[session_id] = (stats, time.time())
                    
                return stats
                
        except Exception as e:
            self.logger.error(f"獲取執行統計失敗: {e}")
            return None
            
    def get_session_status(self, session_id: str, detailed: bool = False) -> Dict[str, Any]:
        """
        獲取會話狀態（合併版本）
        
        Args:
            session_id: 會話ID
            detailed: 是否返回詳細信息
            
        Returns:
            狀態信息字典
        """
        try:
            session_info = self.get_session_info(session_id)
            if not session_info:
                return {"error": "會話不存在"}
                
            result = {
                "session_id": session_info.session_id,
                "mode": session_info.mode,
                "status": session_info.status,
                "total_strategies": session_info.total_strategies,
                "completed_strategies": session_info.completed_strategies,
                "failed_strategies": session_info.failed_strategies,
                "progress_percent": round(session_info.progress_percent, 2),
                "created_at": session_info.created_at,
                "started_at": session_info.started_at,
                "completed_at": session_info.completed_at
            }
            
            if session_info.estimated_remaining_time:
                result["estimated_remaining_minutes"] = round(session_info.estimated_remaining_time / 60, 1)
                
            if detailed:
                stats = self.get_execution_stats(session_id)
                if stats:
                    result["execution_stats"] = {
                        "pending_count": stats.pending_count,
                        "running_count": stats.running_count,
                        "completed_count": stats.completed_count,
                        "failed_count": stats.failed_count,
                        "avg_execution_time_seconds": round(stats.avg_execution_time, 2),
                        "success_rate_percent": round(stats.success_rate, 2),
                        "estimated_total_time_minutes": round(stats.estimated_total_time / 60, 1)
                    }
                    
                # 獲取最佳結果
                top_results = self._get_top_results(session_id, limit=5)
                if top_results:
                    result["top_results"] = top_results
                    
            return result
            
        except Exception as e:
            self.logger.error(f"獲取會話狀態失敗: {e}")
            return {"error": str(e)}
            
    def get_latest_session(self) -> Optional[str]:
        """獲取最新的會話ID"""
        return self.db_manager.get_latest_session()
        
    def can_resume_session(self, session_id: str) -> Tuple[bool, str]:
        """
        檢查會話是否可以斷點續跑
        
        Args:
            session_id: 會話ID
            
        Returns:
            (是否可以續跑, 原因說明)
        """
        try:
            session_info = self.get_session_info(session_id)
            if not session_info:
                return False, "會話不存在"
                
            if session_info.status == 'completed':
                return False, "會話已完成"
                
            if session_info.status == 'failed':
                return True, "會話失敗，可以重試失敗的策略"
                
            pending_strategies = self.get_pending_strategies(session_id, limit=1)
            if not pending_strategies:
                return False, "沒有待執行的策略"
                
            return True, "會話可以續跑"
            
        except Exception as e:
            self.logger.error(f"檢查會話續跑狀態失敗: {e}")
            return False, f"檢查失敗: {e}"
            
    def reset_failed_strategies(self, session_id: str) -> int:
        """
        重置失敗的策略為待執行狀態
        
        Args:
            session_id: 會話ID
            
        Returns:
            重置的策略數量
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 重置失敗的策略
                cursor.execute('''
                    UPDATE strategy_queue 
                    SET status = 'pending', 
                        started_at = NULL, 
                        completed_at = NULL,
                        execution_time_seconds = NULL,
                        error_message = NULL,
                        retry_count = retry_count + 1
                    WHERE session_id = ? AND status = 'failed'
                ''', (session_id,))
                
                reset_count = cursor.rowcount
                conn.commit()
                
            # 記錄重置日誌
            if reset_count > 0:
                self.db_manager.log_execution(
                    session_id=session_id,
                    level="INFO",
                    message=f"重置 {reset_count} 個失敗策略"
                )
                
            # 清除緩存
            self._clear_stats_cache()
            
            self.logger.info(f"重置失敗策略成功: {reset_count} 個")
            return reset_count
            
        except Exception as e:
            self.logger.error(f"重置失敗策略失敗: {e}")
            raise
            
    def _calculate_estimated_time(self, session_id: str, status_data: Dict[str, Any]) -> Optional[float]:
        """計算預估剩餘時間"""
        try:
            stats = self.get_execution_stats(session_id)
            if not stats or stats.avg_execution_time <= 0:
                return None
                
            remaining_strategies = stats.pending_count + stats.running_count
            if remaining_strategies <= 0:
                return 0
                
            estimated_seconds = remaining_strategies * stats.avg_execution_time
            return estimated_seconds
            
        except Exception as e:
            self.logger.debug(f"計算預估時間失敗: {e}")
            return None
            
    def _get_top_results(self, session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """獲取最佳結果"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT strategy_id, sharpe_ratio, annual_return, total_return, max_drawdown
                    FROM backtest_results 
                    WHERE session_id = ? 
                    ORDER BY sharpe_ratio DESC 
                    LIMIT ?
                ''', (session_id, limit))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'strategy_id': row['strategy_id'],
                        'sharpe_ratio': round(row['sharpe_ratio'], 4) if row['sharpe_ratio'] else None,
                        'annual_return': round(row['annual_return'], 4) if row['annual_return'] else None,
                        'total_return': round(row['total_return'], 4) if row['total_return'] else None,
                        'max_drawdown': round(row['max_drawdown'], 4) if row['max_drawdown'] else None
                    })
                    
                return results
                
        except Exception as e:
            self.logger.debug(f"獲取最佳結果失敗: {e}")
            return []
            
    def _clear_stats_cache(self):
        """清除統計緩存"""
        self._stats_cache.clear()
        
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        清理舊的會話數據
        
        Args:
            days: 保留天數
            
        Returns:
            清理的會話數量
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 獲取要清理的會話
                cursor.execute('''
                    SELECT session_id FROM tuning_sessions 
                    WHERE created_at < ? AND status IN ('completed', 'failed')
                ''', (cutoff_date.isoformat(),))
                
                old_sessions = [row['session_id'] for row in cursor.fetchall()]
                
                # 清理每個會話
                cleaned_count = 0
                for session_id in old_sessions:
                    if self.db_manager.clean_session_data(session_id):
                        cleaned_count += 1
                        
            self.logger.info(f"清理舊會話完成: {cleaned_count} 個")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"清理舊會話失敗: {e}")
            return 0 