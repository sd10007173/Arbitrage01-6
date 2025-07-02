#!/usr/bin/env python3
"""
數據庫統一遷移腳本
將 hyperparameter_tuning.db 的調優表遷移到 funding_rate.db
"""

import sqlite3
import os
import shutil
from datetime import datetime

def backup_database():
    """備份生產數據庫"""
    print("📋 備份生產數據庫...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"data/funding_rate_backup_{timestamp}.db"
    shutil.copy2("data/funding_rate.db", backup_path)
    print(f"✅ 備份完成: {backup_path}")
    return backup_path

def get_table_schema(cursor, table_name):
    """獲取表的創建語句"""
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    result = cursor.fetchone()
    return result[0] if result else None

def migrate_tuning_tables():
    """遷移調優表到生產數據庫"""
    print("🚀 開始遷移調優表...")
    
    # 連接兩個數據庫
    source_db = sqlite3.connect('factor_strategies/hyperparameter_tuning/hyperparameter_tuning.db')
    target_db = sqlite3.connect('data/funding_rate.db')
    
    source_cursor = source_db.cursor()
    target_cursor = target_db.cursor()
    
    # 需要遷移的表
    tables_to_migrate = ['tuning_sessions', 'strategy_queue', 'execution_log']
    
    for table in tables_to_migrate:
        print(f"  📊 遷移表: {table}")
        
        # 1. 獲取源表的結構
        schema = get_table_schema(source_cursor, table)
        if not schema:
            print(f"    ⚠️ 跳過不存在的表: {table}")
            continue
        
        # 2. 檢查目標數據庫是否已有此表
        target_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if target_cursor.fetchone():
            print(f"    🗑️ 刪除目標數據庫中的舊表: {table}")
            target_cursor.execute(f"DROP TABLE {table}")
        
        # 3. 在目標數據庫中創建表
        print(f"    🔨 創建表結構: {table}")
        target_cursor.execute(schema)
        
        # 4. 複製數據
        source_cursor.execute(f"SELECT * FROM {table}")
        rows = source_cursor.fetchall()
        
        if rows:
            # 獲取列數
            source_cursor.execute(f"PRAGMA table_info({table})")
            columns = source_cursor.fetchall()
            column_count = len(columns)
            placeholders = ','.join(['?' for _ in range(column_count)])
            
            target_cursor.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
            print(f"    ✅ 複製了 {len(rows)} 條記錄")
        else:
            print(f"    📝 表為空，僅創建結構")
    
    # 處理 backtest_results 表的衝突
    print("  🔄 處理 backtest_results 表衝突...")
    
    # 重命名現有的 backtest_results 為 backtest_results_old
    target_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_results'")
    if target_cursor.fetchone():
        print("    📦 重命名舊的 backtest_results 表為 backtest_results_old")
        target_cursor.execute("ALTER TABLE backtest_results RENAME TO backtest_results_old")
    
    # 創建新的調優專用 backtest_results 表
    schema = get_table_schema(source_cursor, 'backtest_results')
    if schema:
        print("    🔨 創建新的調優專用 backtest_results 表")
        target_cursor.execute(schema)
        
        # 複製數據（如果有的話）
        source_cursor.execute("SELECT * FROM backtest_results")
        rows = source_cursor.fetchall()
        
        if rows:
            source_cursor.execute("PRAGMA table_info(backtest_results)")
            columns = source_cursor.fetchall()
            column_count = len(columns)
            placeholders = ','.join(['?' for _ in range(column_count)])
            target_cursor.executemany(f"INSERT INTO backtest_results VALUES ({placeholders})", rows)
            print(f"    ✅ 複製了 {len(rows)} 條記錄")
    
    # 提交更改
    target_db.commit()
    print("✅ 數據遷移完成")
    
    # 關閉連接
    source_db.close()
    target_db.close()

def update_mass_tuning_config():
    """更新 mass_tuning_system 的數據庫配置"""
    print("⚙️ 更新配置...")
    
    config_file = 'factor_strategies/hyperparameter_tuning/core/database_manager.py'
    
    # 讀取現有配置
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替換數據庫路徑
    old_path = 'hyperparameter_tuning.db'
    new_path = '../../data/funding_rate.db'
    
    if old_path in content:
        content = content.replace(old_path, new_path)
        
        # 寫回文件
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 已更新數據庫路徑: {old_path} -> {new_path}")
    else:
        print("⚠️ 未找到需要替換的數據庫路徑")

def verify_migration():
    """驗證遷移結果"""
    print("🔍 驗證遷移結果...")
    
    db = sqlite3.connect('data/funding_rate.db')
    cursor = db.cursor()
    
    # 檢查調優表是否存在
    tuning_tables = ['tuning_sessions', 'strategy_queue', 'backtest_results', 'execution_log']
    
    for table in tuning_tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if cursor.fetchone():
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  ✅ {table}: {count} 記錄")
        else:
            print(f"  ❌ {table}: 表不存在")
    
    # 檢查核心表是否完整
    core_tables = ['trading_pair', 'funding_rate_history']
    for table in core_tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  🔒 {table}: {count:,} 記錄 (核心數據)")
    
    db.close()
    print("✅ 驗證完成")

def main():
    """主函數"""
    print("🎯 數據庫統一遷移腳本")
    print("=" * 50)
    
    try:
        # 1. 備份
        backup_path = backup_database()
        
        # 2. 遷移
        migrate_tuning_tables()
        
        # 3. 更新配置
        update_mass_tuning_config()
        
        # 4. 驗證
        verify_migration()
        
        print("\n🎉 數據庫統一完成！")
        print("📋 下一步:")
        print("  1. 測試 mass_tuning_system.py")
        print("  2. 確認功能正常後，可刪除 hyperparameter_tuning.db")
        print(f"  3. 如果有問題，可從備份恢復: {backup_path}")
        
    except Exception as e:
        print(f"\n❌ 遷移失敗: {e}")
        print("請檢查錯誤並重試")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 