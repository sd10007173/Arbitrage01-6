"""
加密貨幣資金費率套利系統 - 數據庫架構定義
支持完整的數據流程：歷史數據 -> 差異計算 -> 收益分析 -> 策略排名 -> 回測
"""

import sqlite3
import os
from datetime import datetime

class FundingRateDB:
    def __init__(self, db_path="data/funding_rate.db"):
        """
        初始化數據庫連接
        
        Args:
            db_path: 數據庫文件路徑，默認為 data/funding_rate.db
        """
        # 確保數據庫目錄存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.init_database()
        print(f"✅ 數據庫初始化完成: {db_path}")
    
    def get_connection(self):
        """獲取數據庫連接，返回字典式結果"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 返回字典式結果，便於操作
        return conn
    
    def init_database(self):
        """初始化所有數據庫表結構"""
        with self.get_connection() as conn:
            # 啟用外鍵約束
            conn.execute("PRAGMA foreign_keys = ON")
            
            # 創建所有表
            self._create_funding_rate_history_table(conn)
            self._create_funding_rate_diff_table(conn)
            self._create_return_metrics_table(conn)
            self._create_strategy_ranking_table(conn)
            self._create_backtest_results_table(conn)
            self._create_backtest_trades_table(conn)
            self._create_market_caps_table(conn)
            self._create_trading_pairs_table(conn)
            self._create_ranking_persistence_table(conn)

            
            # 創建索引
            self._create_indexes(conn)
            
            # 創建視圖
            self._create_views(conn)
            
            conn.commit()
    
    def _create_funding_rate_history_table(self, conn):
        """創建資金費率歷史數據表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS funding_rate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc DATETIME NOT NULL,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                funding_rate REAL,                -- 資金費率，API無返回值時保持null
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp_utc, symbol, exchange) ON CONFLICT REPLACE
            )
        ''')
    
    def _create_funding_rate_diff_table(self, conn):
        """創建資金費率差異數據表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS funding_rate_diff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc DATETIME NOT NULL,
                symbol TEXT NOT NULL,
                exchange_a TEXT NOT NULL,
                funding_rate_a TEXT,              -- 保留原始格式
                exchange_b TEXT NOT NULL,
                funding_rate_b TEXT,              -- 保留原始格式
                diff_ab REAL NOT NULL,            -- A - B 的差值
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp_utc, symbol, exchange_a, exchange_b) ON CONFLICT REPLACE
            )
        ''')
    
    def _create_return_metrics_table(self, conn):
        """創建收益指標數據表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS return_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trading_pair TEXT NOT NULL,       -- 格式: SYMBOL_exchangeA_exchangeB
                date DATE NOT NULL,
                return_1d REAL,                   -- 1天累積收益
                roi_1d REAL,                      -- 1天年化收益率
                return_2d REAL,
                roi_2d REAL,
                return_7d REAL,
                roi_7d REAL,
                return_14d REAL,
                roi_14d REAL,
                return_30d REAL,
                roi_30d REAL,
                return_all REAL,                  -- 全期間累積收益
                roi_all REAL,                     -- 全期間年化收益率
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trading_pair, date) ON CONFLICT REPLACE
            )
        ''')
    
    def _create_strategy_ranking_table(self, conn):
        """創建策略排行榜數據表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS strategy_ranking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,      -- 策略名稱（original, momentum_focused 等）
                trading_pair TEXT NOT NULL,
                date DATE NOT NULL,
                final_ranking_score REAL,         -- 最終排名分數
                rank_position INTEGER,            -- 排名位置
                long_term_score REAL,             -- 長期評分組件
                short_term_score REAL,            -- 短期評分組件
                combined_roi_z_score REAL,        -- 組合ROI Z分數
                final_combination_value TEXT,     -- 計算過程詳情
                -- 動態欄位：各策略組件分數
                component_scores TEXT,            -- JSON格式存儲各組件分數
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(strategy_name, trading_pair, date) ON CONFLICT REPLACE
            )
        ''')
    
    def _create_backtest_results_table(self, conn):
        """創建回測結果數據表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id TEXT NOT NULL UNIQUE, -- 唯一標識一次回測（時間戳+策略名）
                strategy_name TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                
                -- 回測參數
                initial_capital REAL NOT NULL,
                position_size REAL,              -- 每次進場資金比例
                fee_rate REAL,                   -- 手續費率
                max_positions INTEGER,           -- 最大持倉數
                entry_top_n INTEGER,             -- 進場條件：前N名
                exit_threshold INTEGER,          -- 離場條件：排名跌出前N名
                
                -- 回測結果
                final_balance REAL,
                total_return REAL,               -- 總收益率
                roi REAL,                        -- 年化收益率 (ROI)
                total_days INTEGER,              -- 回測總天數
                max_drawdown REAL,               -- 最大回撤
                win_rate REAL,                   -- 勝率
                total_trades INTEGER,            -- 總交易次數
                profit_days INTEGER,             -- 獲利天數
                loss_days INTEGER,               -- 虧損天數
                avg_holding_days REAL,           -- 平均持倉天數
                sharpe_ratio REAL,               -- 夏普比率
                
                -- 其他信息
                config_params TEXT,              -- JSON格式存儲完整配置
                notes TEXT,                      -- 備註
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                -- 約束
                CHECK(initial_capital > 0),
                CHECK(final_balance >= 0),
                CHECK(win_rate >= 0 AND win_rate <= 1)
            )
        ''')
    
    def _create_backtest_trades_table(self, conn):
        """創建回測交易明細表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id TEXT NOT NULL,
                trade_date DATE NOT NULL,
                trading_pair TEXT NOT NULL,
                action TEXT NOT NULL,            -- 'enter', 'exit', 'funding'
                amount REAL,                     -- 交易金額
                funding_rate_diff REAL,         -- 資金費率差
                position_balance REAL,          -- 持倉餘額
                cash_balance REAL,              -- 現金餘額
                total_balance REAL,             -- 總餘額
                rank_position INTEGER,          -- 當時排名位置
                position_detail TEXT,           -- 當前持倉詳情，格式: "BT_TEST1(2000), BT_TEST2(1000)"
                notes TEXT,                     -- 備註（如：為什麼進場/離場）
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                -- 外鍵約束
                FOREIGN KEY (backtest_id) REFERENCES backtest_results(backtest_id) ON DELETE CASCADE,
                
                -- 檢查約束
                CHECK(action IN ('enter', 'exit', 'funding')),
                CHECK(total_balance >= 0)
            )
        ''')

    def _create_market_caps_table(self, conn):
        """創建市值數據表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS market_caps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                name TEXT,
                current_price REAL,
                market_cap REAL,
                market_cap_rank INTEGER,
                total_volume REAL,
                price_change_24h REAL,
                price_change_percentage_24h REAL,
                circulating_supply REAL,
                total_supply REAL,
                max_supply REAL,
                ath REAL,
                ath_change_percentage REAL,
                ath_date DATETIME,
                atl REAL,
                atl_change_percentage REAL,
                atl_date DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol) ON CONFLICT REPLACE
            )
        ''')

    def _create_trading_pairs_table(self, conn):
        """創建交易對列表表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trading_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                exchange_a TEXT NOT NULL,
                exchange_b TEXT NOT NULL,
                market_cap REAL,
                fr_date TEXT,                    -- 最後更新的資金費率日期
                diff_first_date TEXT,            -- 首次出現資金費率差的日期 (YYYY-MM-DD HH:MM:SS)
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, exchange_a, exchange_b) ON CONFLICT REPLACE
            )
        ''')

    def _create_ranking_persistence_table(self, conn):
        """創建排名持久性分析結果表"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trading_pair_top_ranking_days (
                event_id TEXT PRIMARY KEY,          -- 唯一事件ID, 格式: {strategy}_{trading_pair}_(n)
                strategy TEXT NOT NULL,             -- 策略名稱
                trading_pair TEXT NOT NULL,         -- 交易對名稱
                entry_date DATE NOT NULL,           -- 首次進入前x名的日期
                entry_rank INTEGER NOT NULL,        -- 進入時的排名
                exit_date DATE,                     -- 跌出前y名的日期
                exit_rank INTEGER,                  -- 離開時的排名 (可能為NULL)
                consecutive_days INTEGER NOT NULL,  -- 連續在前y名內的天數
                trigger_rank_x INTEGER NOT NULL,    -- 觸發分析的排名X
                persistence_rank_y INTEGER NOT NULL,-- 持續性觀察的排名Y
                parameters TEXT,                    -- 分析參數, e.g., "x=10, y=50"
                cumulative_consecutive_days INTEGER, -- 該交易對的累計持續天數
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    

    
    def _create_indexes(self, conn):
        """創建索引提升查詢性能"""
        indexes = [
            # 資金費率歷史數據索引
            "CREATE INDEX IF NOT EXISTS idx_funding_history_symbol_exchange ON funding_rate_history(symbol, exchange)",
            "CREATE INDEX IF NOT EXISTS idx_funding_history_timestamp ON funding_rate_history(timestamp_utc)",
            "CREATE INDEX IF NOT EXISTS idx_funding_history_symbol_time ON funding_rate_history(symbol, timestamp_utc)",
            
            # 資金費率差異索引
            "CREATE INDEX IF NOT EXISTS idx_funding_diff_symbol ON funding_rate_diff(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_funding_diff_timestamp ON funding_rate_diff(timestamp_utc)",
            "CREATE INDEX IF NOT EXISTS idx_funding_diff_exchanges ON funding_rate_diff(exchange_a, exchange_b)",
            
            # 收益指標索引
            "CREATE INDEX IF NOT EXISTS idx_return_metrics_date ON return_metrics(date)",
            "CREATE INDEX IF NOT EXISTS idx_return_metrics_pair ON return_metrics(trading_pair)",
            "CREATE INDEX IF NOT EXISTS idx_return_metrics_pair_date ON return_metrics(trading_pair, date)",
            
            # 策略排行榜索引
            "CREATE INDEX IF NOT EXISTS idx_strategy_ranking_date ON strategy_ranking(date)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_ranking_strategy ON strategy_ranking(strategy_name)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_ranking_strategy_date ON strategy_ranking(strategy_name, date)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_ranking_rank ON strategy_ranking(rank_position)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_ranking_date_rank ON strategy_ranking (date, rank_position)",
            
            # 回測結果索引
            "CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy ON backtest_results(strategy_name)",
            "CREATE INDEX IF NOT EXISTS idx_backtest_results_date_range ON backtest_results(start_date, end_date)",
            "CREATE INDEX IF NOT EXISTS idx_backtest_results_created ON backtest_results(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy_date ON backtest_results (strategy_name, start_date, end_date)",
            
            # 回測交易索引
            "CREATE INDEX IF NOT EXISTS idx_backtest_trades_backtest_id ON backtest_trades(backtest_id)",
            "CREATE INDEX IF NOT EXISTS idx_backtest_trades_date ON backtest_trades(trade_date)",
            "CREATE INDEX IF NOT EXISTS idx_backtest_trades_pair ON backtest_trades(trading_pair)",
            
            # trading_pair_top_ranking_days 索引
            "CREATE INDEX IF NOT EXISTS idx_ranking_persistence_strategy ON trading_pair_top_ranking_days (strategy)",
            "CREATE INDEX IF NOT EXISTS idx_ranking_persistence_pair ON trading_pair_top_ranking_days (trading_pair)",

        ]
        
        for index_sql in indexes:
            try:
                conn.execute(index_sql)
            except sqlite3.Error as e:
                print(f"⚠️ 創建索引時出錯: {e}")
    
    def _create_views(self, conn):
        """創建有用的視圖"""
        
        # 1. 最新排行榜視圖
        conn.execute('''
            CREATE VIEW IF NOT EXISTS latest_ranking AS
            SELECT 
                sr.*,
                rm.roi_1d,
                rm.roi_7d,
                rm.roi_30d
            FROM strategy_ranking sr
            LEFT JOIN return_metrics rm ON sr.trading_pair = rm.trading_pair AND sr.date = rm.date
            WHERE sr.date = (SELECT MAX(date) FROM strategy_ranking WHERE strategy_name = sr.strategy_name)
        ''')
        
        # 2. 交易對績效摘要視圖
        conn.execute('''
            CREATE VIEW IF NOT EXISTS trading_pair_performance AS
            SELECT 
                trading_pair,
                COUNT(*) as data_points,
                AVG(roi_1d) as avg_roi_1d,
                AVG(roi_7d) as avg_roi_7d,
                AVG(roi_30d) as avg_roi_30d,
                MIN(date) as first_date,
                MAX(date) as last_date
            FROM return_metrics
            GROUP BY trading_pair
        ''')
        
        # 3. 回測績效摘要視圖
        conn.execute('''
            CREATE VIEW IF NOT EXISTS backtest_performance_summary AS
            SELECT 
                strategy_name,
                COUNT(*) as total_backtests,
                AVG(total_return) as avg_return,
                AVG(max_drawdown) as avg_drawdown,
                AVG(win_rate) as avg_win_rate,
                AVG(sharpe_ratio) as avg_sharpe,
                MAX(total_return) as best_return,
                MIN(max_drawdown) as best_drawdown
            FROM backtest_results
            GROUP BY strategy_name
        ''')
    
    def get_database_info(self):
        """獲取數據庫基本信息"""
        with self.get_connection() as conn:
            # 獲取所有表的記錄數
            tables = [
                'funding_rate_history',
                'funding_rate_diff', 
                'return_metrics',
                'strategy_ranking',
                'backtest_results',
                'backtest_trades',
                'market_caps',
                'trading_pairs'
            ]
            
            info = {"database_path": self.db_path, "tables": {}}
            
            for table in tables:
                try:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    info["tables"][table] = count
                except sqlite3.Error:
                    info["tables"][table] = "表不存在"
            
            return info
    
    def vacuum_database(self):
        """清理和優化數據庫"""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
        print("✅ 數據庫清理和優化完成")

if __name__ == "__main__":
    # 測試數據庫創建
    db = FundingRateDB()
    info = db.get_database_info()
    
    print("\n📊 數據庫信息:")
    print(f"路徑: {info['database_path']}")
    print("表記錄數:")
    for table, count in info['tables'].items():
        print(f"  {table}: {count}") 