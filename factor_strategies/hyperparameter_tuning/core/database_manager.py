"""
數據庫管理器 - DatabaseManager
負責管理超參數調優過程中的數據存儲
"""

import sqlite3
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager

class DatabaseManager:
    """數據庫管理器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化數據庫管理器
        
        Args:
            db_path: 數據庫路徑，如果為空則使用默認路徑
        """
        self.logger = logging.getLogger(__name__)
        
        if db_path is None:
            # 使用默認路徑
            db_path = Path(__file__).parent.parent / "../../data/funding_rate.db"
            
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化數據庫
        self._init_database()
        
    def _init_database(self):
        """初始化數據庫表結構"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 創建會話表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tuning_sessions (
                        session_id TEXT PRIMARY KEY,
                        mode TEXT NOT NULL,
                        total_strategies INTEGER NOT NULL,
                        completed_strategies INTEGER DEFAULT 0,
                        failed_strategies INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'created',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        config_data TEXT,
                        notes TEXT
                    )
                ''')
                
                # 創建策略隊列表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS strategy_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        strategy_id TEXT NOT NULL,
                        strategy_config TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        priority INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        execution_time_seconds REAL,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        FOREIGN KEY (session_id) REFERENCES tuning_sessions (session_id),
                        UNIQUE(session_id, strategy_id)
                    )
                ''')
                
                # 創建回測結果匯總表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS hyperparameter_tuning_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        strategy_id TEXT NOT NULL,
                        factors TEXT,
                        window_size INTEGER,
                        rebalance_frequency INTEGER,
                        data_period INTEGER,
                        selection_count INTEGER,
                        weight_method TEXT,
                        total_return REAL,
                        annual_return REAL,
                        sharpe_ratio REAL,
                        max_drawdown REAL,
                        win_rate REAL,
                        trade_count INTEGER,
                        start_date TEXT,
                        end_date TEXT,
                        raw_result TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES tuning_sessions (session_id),
                        UNIQUE(session_id, strategy_id)
                    )
                ''')
                
                # 創建執行日誌表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS execution_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        strategy_id TEXT,
                        log_level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES tuning_sessions (session_id)
                    )
                ''')
                
                # 創建索引以提高查詢性能
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy_queue_session_status ON strategy_queue (session_id, status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_hyperparameter_tuning_results_session ON hyperparameter_tuning_results (session_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_hyperparameter_tuning_results_performance ON hyperparameter_tuning_results (sharpe_ratio, annual_return)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_execution_log_session ON execution_log (session_id)')
                
                conn.commit()
                self.logger.info("數據庫初始化完成")
                
        except Exception as e:
            self.logger.error(f"數據庫初始化失敗: {e}")
            raise
            
    @contextmanager
    def get_connection(self):
        """獲取數據庫連接的上下文管理器"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 使結果可以通過字段名訪問
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"數據庫操作失敗: {e}")
            raise
        finally:
            if conn:
                conn.close()
                
    def create_session(self, mode: str, total_strategies: int, 
                      config_data: Dict[str, Any] = None, notes: str = None) -> str:
        """
        創建新的調優會話
        
        Args:
            mode: 執行模式 ('exhaustive' 或 'sampling')
            total_strategies: 總策略數量
            config_data: 配置數據
            notes: 備註
            
        Returns:
            session_id: 會話ID
        """
        try:
            import random
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            random_suffix = f"{random.randint(1000, 9999)}"
            session_id = f"session_{timestamp}_{random_suffix}"
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tuning_sessions 
                    (session_id, mode, total_strategies, config_data, notes)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, mode, total_strategies, 
                     json.dumps(config_data) if config_data else None, notes))
                conn.commit()
                
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
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for i, strategy in enumerate(strategies):
                    strategy_id = strategy.get('strategy_id', f"strategy_{i+1:06d}")
                    cursor.execute('''
                        INSERT INTO strategy_queue 
                        (session_id, strategy_id, strategy_config, priority)
                        VALUES (?, ?, ?, ?)
                    ''', (session_id, strategy_id, json.dumps(strategy), i))
                    
                conn.commit()
                
            self.logger.info(f"添加 {len(strategies)} 個策略到隊列")
            
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
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, strategy_id, strategy_config, priority, retry_count
                    FROM strategy_queue 
                    WHERE session_id = ? AND status = 'pending'
                    ORDER BY priority ASC, created_at ASC
                '''
                
                if limit:
                    query += f' LIMIT {limit}'
                    
                cursor.execute(query, (session_id,))
                rows = cursor.fetchall()
                
                strategies = []
                for row in rows:
                    strategies.append({
                        'id': row['id'],
                        'strategy_id': row['strategy_id'],
                        'strategy_config': json.loads(row['strategy_config']),
                        'priority': row['priority'],
                        'retry_count': row['retry_count']
                    })
                    
                return strategies
                
        except Exception as e:
            self.logger.error(f"獲取待執行策略失敗: {e}")
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
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if status == 'running':
                    cursor.execute('''
                        UPDATE strategy_queue 
                        SET status = ?, started_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (status, queue_id))
                elif status in ['completed', 'failed']:
                    cursor.execute('''
                        UPDATE strategy_queue 
                        SET status = ?, completed_at = CURRENT_TIMESTAMP,
                            execution_time_seconds = ?, error_message = ?
                        WHERE id = ?
                    ''', (status, execution_time, error_message, queue_id))
                else:
                    cursor.execute('''
                        UPDATE strategy_queue 
                        SET status = ?, error_message = ?
                        WHERE id = ?
                    ''', (status, error_message, queue_id))
                    
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"更新策略狀態失敗: {e}")
            raise
            
    def save_backtest_result(self, session_id: str, strategy_id: str, result: Dict[str, Any]):
        """
        保存回測結果
        
        Args:
            session_id: 會話ID
            strategy_id: 策略ID
            result: 回測結果
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 提取關鍵指標
                strategy_config = result.get('strategy_config', {})
                metrics = result.get('metrics', {})
                
                cursor.execute('''
                    INSERT OR REPLACE INTO hyperparameter_tuning_results 
                    (session_id, strategy_id, factors, window_size, rebalance_frequency,
                     data_period, selection_count, weight_method, total_return, 
                     annual_return, sharpe_ratio, max_drawdown, win_rate, trade_count,
                     start_date, end_date, raw_result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id, strategy_id,
                    json.dumps(strategy_config.get('factors', [])),
                    strategy_config.get('window_size'),
                    strategy_config.get('rebalance_frequency'),
                    strategy_config.get('data_period'),
                    strategy_config.get('selection_count'),
                    strategy_config.get('weight_method'),
                    metrics.get('total_return'),
                    metrics.get('annual_return'),
                    metrics.get('sharpe_ratio'),
                    metrics.get('max_drawdown'),
                    metrics.get('win_rate'),
                    metrics.get('trade_count'),
                    metrics.get('start_date'),
                    metrics.get('end_date'),
                    json.dumps(result)
                ))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"保存回測結果失敗: {e}")
            raise
            
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        獲取會話狀態
        
        Args:
            session_id: 會話ID
            
        Returns:
            會話狀態信息
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 獲取會話基本信息
                cursor.execute('''
                    SELECT * FROM tuning_sessions WHERE session_id = ?
                ''', (session_id,))
                session_row = cursor.fetchone()
                
                if not session_row:
                    return {"error": "會話不存在"}
                    
                # 獲取策略執行統計
                cursor.execute('''
                    SELECT 
                        status,
                        COUNT(*) as count,
                        AVG(execution_time_seconds) as avg_time
                    FROM strategy_queue 
                    WHERE session_id = ? 
                    GROUP BY status
                ''', (session_id,))
                
                status_stats = {}
                for row in cursor.fetchall():
                    status_stats[row['status']] = {
                        'count': row['count'],
                        'avg_time': row['avg_time']
                    }
                    
                # 獲取最佳結果
                cursor.execute('''
                    SELECT strategy_id, sharpe_ratio, annual_return
                    FROM hyperparameter_tuning_results 
                    WHERE session_id = ? 
                    ORDER BY sharpe_ratio DESC 
                    LIMIT 5
                ''', (session_id,))
                
                top_results = [dict(row) for row in cursor.fetchall()]
                
                return {
                    'session_id': session_id,
                    'mode': session_row['mode'],
                    'status': session_row['status'],
                    'total_strategies': session_row['total_strategies'],
                    'completed_strategies': session_row['completed_strategies'],
                    'failed_strategies': session_row['failed_strategies'],
                    'created_at': session_row['created_at'],
                    'started_at': session_row['started_at'],
                    'completed_at': session_row['completed_at'],
                    'status_breakdown': status_stats,
                    'top_results': top_results
                }
                
        except Exception as e:
            self.logger.error(f"獲取會話狀態失敗: {e}")
            return {"error": str(e)}
            
    def get_latest_session(self) -> Optional[str]:
        """獲取最新的會話ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT session_id FROM tuning_sessions 
                    ORDER BY created_at DESC LIMIT 1
                ''')
                row = cursor.fetchone()
                return row['session_id'] if row else None
                
        except Exception as e:
            self.logger.error(f"獲取最新會話失敗: {e}")
            return None
            
    def clean_session_data(self, session_id: str, failed_only: bool = False) -> bool:
        """
        清理會話數據
        
        Args:
            session_id: 會話ID
            failed_only: 是否只清理失敗記錄
            
        Returns:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if failed_only:
                    # 只清理失敗的策略
                    cursor.execute('''
                        DELETE FROM strategy_queue 
                        WHERE session_id = ? AND status = 'failed'
                    ''', (session_id,))
                    cursor.execute('''
                        DELETE FROM execution_log 
                        WHERE session_id = ? AND strategy_id IN (
                            SELECT strategy_id FROM strategy_queue 
                            WHERE session_id = ? AND status = 'failed'
                        )
                    ''', (session_id, session_id))
                else:
                    # 清理整個會話
                    cursor.execute('DELETE FROM hyperparameter_tuning_results WHERE session_id = ?', (session_id,))
                    cursor.execute('DELETE FROM strategy_queue WHERE session_id = ?', (session_id,))
                    cursor.execute('DELETE FROM execution_log WHERE session_id = ?', (session_id,))
                    cursor.execute('DELETE FROM tuning_sessions WHERE session_id = ?', (session_id,))
                    
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"清理會話數據失敗: {e}")
            return False
            
    def clean_all_data(self, failed_only: bool = False) -> bool:
        """清理所有數據"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if failed_only:
                    cursor.execute("DELETE FROM strategy_queue WHERE status = 'failed'")
                else:
                    cursor.execute('DELETE FROM hyperparameter_tuning_results')
                    cursor.execute('DELETE FROM strategy_queue')
                    cursor.execute('DELETE FROM execution_log')
                    cursor.execute('DELETE FROM tuning_sessions')
                    
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"清理所有數據失敗: {e}")
            return False
            
    def log_execution(self, session_id: str, level: str, message: str, 
                     strategy_id: str = None, details: Dict[str, Any] = None):
        """記錄執行日誌"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO execution_log 
                    (session_id, strategy_id, log_level, message, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, strategy_id, level, message, 
                     json.dumps(details) if details else None))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"記錄執行日誌失敗: {e}") 