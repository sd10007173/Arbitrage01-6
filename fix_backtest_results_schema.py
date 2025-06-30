#!/usr/bin/env python3
"""
修正 backtest_results 表的欄位順序
將 total_return, roi, total_days, sharpe_ratio 排列在一起

簡化版本：直接刪除 backtest_performance_summary 視圖
"""

import sqlite3
import shutil
import os
from datetime import datetime

def backup_database(db_path):
    """備份數據庫"""
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"✅ 數據庫已備份到: {backup_path}")
    return backup_path

def fix_backtest_results_schema(db_path="data/funding_rate.db"):
    """修正 backtest_results 表的欄位順序"""
    
    print("🔧 開始修正 backtest_results 表結構...")
    
    # 1. 備份數據庫
    backup_path = backup_database(db_path)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        try:
            # 2. 直接刪除 backtest_performance_summary 視圖
            print("🗑️  刪除 backtest_performance_summary 視圖...")
            cursor.execute("DROP VIEW IF EXISTS backtest_performance_summary")
            
            # 3. 檢查當前表結構
            cursor.execute("PRAGMA table_info(backtest_results)")
            current_columns = cursor.fetchall()
            print(f"📋 當前表有 {len(current_columns)} 個欄位")
            
            # 4. 創建新表結構（正確的欄位順序）
            print("🏗️  創建新表結構...")
            cursor.execute('''
                CREATE TABLE backtest_results_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_id TEXT NOT NULL UNIQUE,
                    strategy_name TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    
                    -- 回測參數
                    initial_capital REAL NOT NULL,
                    position_size REAL,
                    fee_rate REAL,
                    max_positions INTEGER,
                    entry_top_n INTEGER,
                    exit_threshold INTEGER,
                    
                    -- 回測結果
                    final_balance REAL,
                    
                    -- 核心績效指標（排列在一起）
                    total_return REAL,
                    roi REAL,
                    total_days INTEGER,
                    sharpe_ratio REAL,
                    
                    -- 其他績效指標
                    max_drawdown REAL,
                    win_rate REAL,
                    total_trades INTEGER,
                    profit_days INTEGER,
                    loss_days INTEGER,
                    avg_holding_days REAL,
                    
                    -- 其他信息
                    config_params TEXT,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 約束
                    CHECK(initial_capital > 0),
                    CHECK(final_balance >= 0),
                    CHECK(win_rate >= 0 AND win_rate <= 1)
                )
            ''')
            
            # 5. 複製數據到新表
            print("📦 複製現有數據...")
            cursor.execute('''
                INSERT INTO backtest_results_new 
                SELECT 
                    id, backtest_id, strategy_name, start_date, end_date,
                    initial_capital, position_size, fee_rate, max_positions, 
                    entry_top_n, exit_threshold, final_balance,
                    total_return, roi, total_days, sharpe_ratio,
                    max_drawdown, win_rate, total_trades, profit_days, 
                    loss_days, avg_holding_days,
                    config_params, notes, created_at
                FROM backtest_results
            ''')
            
            copied_rows = cursor.rowcount
            print(f"✅ 已複製 {copied_rows} 條記錄")
            
            # 6. 刪除舊表並重命名新表
            print("🔄 替換表結構...")
            cursor.execute("DROP TABLE backtest_results")
            cursor.execute("ALTER TABLE backtest_results_new RENAME TO backtest_results")
            
            # 7. 重新創建索引
            print("🏗️  重新創建索引...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy ON backtest_results(strategy_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backtest_results_date_range ON backtest_results(start_date, end_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backtest_results_created ON backtest_results(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy_date ON backtest_results (strategy_name, start_date, end_date)")
            
            # 8. 驗證修正結果
            print("🔍 驗證修正結果...")
            cursor.execute("PRAGMA table_info(backtest_results)")
            new_columns = cursor.fetchall()
            
            print(f"✅ 新表有 {len(new_columns)} 個欄位")
            print("\n📋 新表結構:")
            for i, (cid, name, type_, notnull, default, pk) in enumerate(new_columns, 1):
                print(f"  {i:2d}. {name:<20} {type_:<10}")
            
            # 確認核心欄位順序
            field_positions = {col[1]: col[0] for col in new_columns}
            core_fields = ['total_return', 'roi', 'total_days', 'sharpe_ratio']
            
            print(f"\n🎯 核心欄位位置:")
            for field in core_fields:
                if field in field_positions:
                    print(f"  {field}: 位置 {field_positions[field] + 1}")
            
            # 檢查是否連續
            positions = [field_positions[field] for field in core_fields if field in field_positions]
            if positions == sorted(positions) and max(positions) - min(positions) == len(positions) - 1:
                print("✅ 核心欄位已正確排列在一起")
            else:
                print("⚠️  核心欄位位置可能不連續")
            
            conn.commit()
            print("\n🎉 修正完成！")
            
        except Exception as e:
            print(f"❌ 修正過程中出錯: {e}")
            conn.rollback()
            raise
    
    return True

if __name__ == "__main__":
    try:
        success = fix_backtest_results_schema()
        if success:
            print("\n✨ backtest_results 表結構修正成功！")
            print("💡 提示：backtest_performance_summary 視圖已被刪除")
            print("   如果需要，可以在 database_schema.py 中重新創建")
        else:
            print("\n❌ 修正失敗")
    except Exception as e:
        print(f"\n💥 執行失敗: {e}") 