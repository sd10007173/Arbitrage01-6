#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試場景設置腳本
用於創建各種邊界條件和特殊場景的測試數據
"""

import sqlite3
import shutil
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json

class TestScenarioSetup:
    def __init__(self, db_path="data/funding_rate.db"):
        self.db_path = db_path
        self.backup_path = "data/funding_rate_backup.db"
        self.test_scenarios = {}
        
    def backup_database(self):
        """備份原始數據庫"""
        print("📦 備份原始數據庫...")
        shutil.copy2(self.db_path, self.backup_path)
        print(f"✅ 備份完成: {self.backup_path}")
        
    def restore_database(self):
        """恢復原始數據庫"""
        print("🔄 恢復原始數據庫...")
        shutil.copy2(self.backup_path, self.db_path)
        print(f"✅ 恢復完成: {self.db_path}")
        
    def get_data_info(self):
        """獲取當前數據庫信息"""
        conn = sqlite3.connect(self.db_path)
        
        tables_info = {}
        for table in ['funding_rate_history', 'funding_rate_diff', 'return_metrics', 'strategy_ranking']:
            if table in ['funding_rate_history', 'funding_rate_diff']:
                query = f"SELECT MIN(DATE(timestamp_utc)), MAX(DATE(timestamp_utc)), COUNT(*) FROM {table}"
            else:
                query = f"SELECT MIN(date), MAX(date), COUNT(*) FROM {table}"
            
            cursor = conn.execute(query)
            min_date, max_date, count = cursor.fetchone()
            tables_info[table] = {
                'min_date': min_date,
                'max_date': max_date,
                'count': count
            }
        
        conn.close()
        return tables_info
        
    def scenario_1_empty_data(self):
        """場景1: 空數據場景 - 刪除2025-07-01後的所有數據"""
        print("\n🧪 設置場景1: 空數據場景")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 刪除2025-07-01後的數據
        cursor.execute("DELETE FROM funding_rate_history WHERE timestamp_utc >= '2025-07-01'")
        cursor.execute("DELETE FROM funding_rate_diff WHERE timestamp_utc >= '2025-07-01'")
        cursor.execute("DELETE FROM return_metrics WHERE date >= '2025-07-01'")
        cursor.execute("DELETE FROM strategy_ranking WHERE date >= '2025-07-01'")
        
        conn.commit()
        conn.close()
        
        print("✅ 場景1設置完成: 已刪除2025-07-01後的所有數據")
        
    def scenario_2_sparse_data(self):
        """場景2: 稀疏數據場景 - 只保留部分交易對"""
        print("\n🧪 設置場景2: 稀疏數據場景")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 只保留3個交易對的數據
        keep_symbols = ['BTC', 'ETH', 'ADA']
        
        # 構建SQL條件
        symbol_condition = " AND ".join([f"symbol != '{sym}'" for sym in keep_symbols])
        trading_pair_condition = " AND ".join([f"trading_pair NOT LIKE '{sym}%'" for sym in keep_symbols])
        
        cursor.execute(f"DELETE FROM funding_rate_history WHERE {symbol_condition}")
        cursor.execute(f"DELETE FROM funding_rate_diff WHERE {symbol_condition}")
        cursor.execute(f"DELETE FROM return_metrics WHERE {trading_pair_condition}")
        cursor.execute(f"DELETE FROM strategy_ranking WHERE {trading_pair_condition}")
        
        conn.commit()
        conn.close()
        
        print("✅ 場景2設置完成: 只保留BTC, ETH, ADA交易對")
        
    def scenario_3_single_day_data(self):
        """場景3: 單日數據場景 - 只保留最近一天的數據"""
        print("\n🧪 設置場景3: 單日數據場景")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 找出最新日期
        cursor.execute("SELECT MAX(date) FROM return_metrics")
        latest_date = cursor.fetchone()[0]
        
        if latest_date:
            # 只保留最新一天的數據
            cursor.execute("DELETE FROM funding_rate_history WHERE DATE(timestamp_utc) != ?", (latest_date,))
            cursor.execute("DELETE FROM funding_rate_diff WHERE DATE(timestamp_utc) != ?", (latest_date,))
            cursor.execute("DELETE FROM return_metrics WHERE date != ?", (latest_date,))
            cursor.execute("DELETE FROM strategy_ranking WHERE date != ?", (latest_date,))
        
        conn.commit()
        conn.close()
        
        print(f"✅ 場景3設置完成: 只保留{latest_date}的數據")
        
    def scenario_4_data_gaps(self):
        """場景4: 數據缺口場景 - 故意創建數據缺口"""
        print("\n🧪 設置場景4: 數據缺口場景")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 刪除中間幾天的數據，創造缺口
        gap_dates = ['2025-07-03', '2025-07-04', '2025-07-05', '2025-07-10', '2025-07-11']
        
        for date in gap_dates:
            cursor.execute("DELETE FROM funding_rate_history WHERE DATE(timestamp_utc) = ?", (date,))
            cursor.execute("DELETE FROM funding_rate_diff WHERE DATE(timestamp_utc) = ?", (date,))
            cursor.execute("DELETE FROM return_metrics WHERE date = ?", (date,))
            cursor.execute("DELETE FROM strategy_ranking WHERE date = ?", (date,))
        
        conn.commit()
        conn.close()
        
        print(f"✅ 場景4設置完成: 創建了{len(gap_dates)}個數據缺口")
        
    def scenario_5_extreme_values(self):
        """場景5: 極端值場景 - 插入極端值數據"""
        print("\n🧪 設置場景5: 極端值場景")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 在funding_rate_diff表中插入極端值
        extreme_values = [
            ('2025-07-15 08:00:00', 'EXTREME_TEST', 'binance', 'bybit', 999999.0),
            ('2025-07-15 08:00:00', 'EXTREME_TEST2', 'binance', 'bybit', -999999.0),
            ('2025-07-15 08:00:00', 'EXTREME_TEST3', 'binance', 'bybit', 0.0),
            ('2025-07-15 08:00:00', 'EXTREME_TEST4', 'binance', 'bybit', float('inf')),
            ('2025-07-15 08:00:00', 'EXTREME_TEST5', 'binance', 'bybit', float('-inf')),
        ]
        
        for timestamp, symbol, exchange_a, exchange_b, diff in extreme_values:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO funding_rate_diff 
                    (timestamp_utc, symbol, exchange_a, exchange_b, diff_ab)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp, symbol, exchange_a, exchange_b, diff))
            except Exception as e:
                print(f"   ⚠️ 插入極端值失敗: {symbol} - {e}")
        
        conn.commit()
        conn.close()
        
        print("✅ 場景5設置完成: 插入極端值數據")
        
    def scenario_6_null_values(self):
        """場景6: NULL值場景 - 創建包含NULL值的數據"""
        print("\n🧪 設置場景6: NULL值場景")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 更新部分funding_rate_diff記錄為NULL
        cursor.execute("""
            UPDATE funding_rate_diff 
            SET diff_ab = NULL 
            WHERE symbol = 'BTC' AND timestamp_utc >= '2025-07-15'
        """)
        
        # 更新部分return_metrics記錄為NULL
        cursor.execute("""
            UPDATE return_metrics 
            SET return_1d = NULL, roi_1d = NULL, return_7d = NULL, roi_7d = NULL
            WHERE trading_pair LIKE 'ETH%' AND date >= '2025-07-15'
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ 場景6設置完成: 創建NULL值數據")
        
    def scenario_7_identical_values(self):
        """場景7: 相同值場景 - 所有指標都相同"""
        print("\n🧪 設置場景7: 相同值場景")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 將所有return_metrics的值設為相同
        cursor.execute("""
            UPDATE return_metrics 
            SET return_1d = 0.01, roi_1d = 3.65, 
                return_2d = 0.02, roi_2d = 3.65,
                return_7d = 0.07, roi_7d = 3.65,
                return_14d = 0.14, roi_14d = 3.65,
                return_30d = 0.30, roi_30d = 3.65,
                return_all = 1.00, roi_all = 3.65
            WHERE date >= '2025-07-15'
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ 場景7設置完成: 所有指標設為相同值")
        
    def scenario_8_single_trading_pair(self):
        """場景8: 單交易對場景 - 只保留一個交易對"""
        print("\n🧪 設置場景8: 單交易對場景")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 只保留一個交易對
        cursor.execute("DELETE FROM return_metrics WHERE trading_pair != 'BTC_binance_bybit'")
        cursor.execute("DELETE FROM strategy_ranking WHERE trading_pair != 'BTC_binance_bybit'")
        
        conn.commit()
        conn.close()
        
        print("✅ 場景8設置完成: 只保留BTC_binance_bybit交易對")
        
    def generate_test_report(self, scenario_name):
        """生成測試場景報告"""
        print(f"\n📊 生成 {scenario_name} 測試報告...")
        
        info = self.get_data_info()
        
        report = {
            'scenario': scenario_name,
            'timestamp': datetime.now().isoformat(),
            'data_info': info
        }
        
        # 保存報告
        report_file = f"test_report_{scenario_name}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 報告已保存: {report_file}")
        
        # 顯示簡要信息
        print("\n📈 數據概況:")
        for table, info in info.items():
            print(f"  {table}: {info['count']} 記錄 ({info['min_date']} ~ {info['max_date']})")
        
        return report

def main():
    """主測試函數"""
    print("🚀 測試場景設置器啟動")
    print("=" * 50)
    
    setup = TestScenarioSetup()
    
    # 顯示當前數據情況
    print("📊 當前數據情況:")
    info = setup.get_data_info()
    for table, data in info.items():
        print(f"  {table}: {data['count']} 記錄 ({data['min_date']} ~ {data['max_date']})")
    
    # 選擇測試場景
    scenarios = {
        '1': ('空數據場景', setup.scenario_1_empty_data),
        '2': ('稀疏數據場景', setup.scenario_2_sparse_data),
        '3': ('單日數據場景', setup.scenario_3_single_day_data),
        '4': ('數據缺口場景', setup.scenario_4_data_gaps),
        '5': ('極端值場景', setup.scenario_5_extreme_values),
        '6': ('NULL值場景', setup.scenario_6_null_values),
        '7': ('相同值場景', setup.scenario_7_identical_values),
        '8': ('單交易對場景', setup.scenario_8_single_trading_pair),
        'backup': ('備份數據庫', setup.backup_database),
        'restore': ('恢復數據庫', setup.restore_database),
    }
    
    print("\n📋 可用測試場景:")
    for key, (name, _) in scenarios.items():
        print(f"  {key}. {name}")
    
    choice = input("\n請選擇場景 (輸入數字或 'backup'/'restore'): ").strip()
    
    if choice in scenarios:
        name, func = scenarios[choice]
        print(f"\n🎯 執行: {name}")
        func()
        
        if choice not in ['backup', 'restore']:
            setup.generate_test_report(f"scenario_{choice}")
    else:
        print("❌ 無效選擇")

if __name__ == "__main__":
    main() 