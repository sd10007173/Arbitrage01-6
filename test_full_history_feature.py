#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全歷史圖片功能測試腳本
測試目標：
1. draw_return_metrics_v3.py 的時間範圍參數
2. 圖片命名規則
3. master_controller 的圖片生成
4. send_ranking_charts 的圖片發送
"""

import os
import sys
import sqlite3
import subprocess
from datetime import datetime

def run_sql_script(sql_file):
    """執行 SQL 腳本"""
    print(f"\n=== 執行 SQL 腳本: {sql_file} ===")
    try:
        # 讀取 SQL 腳本
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 連接資料庫
        conn = sqlite3.connect('data/funding_rate.db')
        cursor = conn.cursor()
        
        # 執行 SQL 腳本
        cursor.executescript(sql_content)
        
        # 提交並關閉
        conn.commit()
        conn.close()
        print("✅ SQL 腳本執行成功")
        return True
    except Exception as e:
        print(f"❌ SQL 腳本執行失敗: {e}")
        return False

def test_draw_return_metrics_parameters():
    """測試 draw_return_metrics_v3.py 的參數功能"""
    print("\n=== 測試 draw_return_metrics_v3.py 參數功能 ===")
    
    # 清理舊圖片
    os.system("rm -f data/picture/*_full_history_return_pic.png")
    os.system("rm -f data/picture/*_2025-07-10-2025-07-15_return_pic.png")
    
    tests = [
        {
            'name': '全歷史圖片生成',
            'cmd': ['python3', 'draw_return_metrics_v3.py', '--output-dir', 'data/picture'],
            'expected_files': [
                'data/picture/BTC_binance_bybit_full_history_return_pic.png',
                'data/picture/ETH_binance_bybit_full_history_return_pic.png',
                'data/picture/ADA_binance_bybit_full_history_return_pic.png'
            ]
        },
        {
            'name': '特定期間圖片生成',
            'cmd': ['python3', 'draw_return_metrics_v3.py', '--start-date', '2025-07-10', '--end-date', '2025-07-15', '--output-dir', 'data/picture'],
            'expected_files': [
                'data/picture/BTC_binance_bybit_2025-07-10-2025-07-15_return_pic.png',
                'data/picture/ETH_binance_bybit_2025-07-10-2025-07-15_return_pic.png',
                'data/picture/ADA_binance_bybit_2025-07-10-2025-07-15_return_pic.png'
            ]
        },
        {
            'name': '單個交易對全歷史圖片',
            'cmd': ['python3', 'draw_return_metrics_v3.py', '--trading-pair', 'BTC_binance_bybit', '--output-dir', 'data/picture'],
            'expected_files': [
                'data/picture/BTC_binance_bybit_full_history_return_pic.png'
            ]
        }
    ]
    
    for test in tests:
        print(f"\n--- 測試: {test['name']} ---")
        print(f"執行命令: {' '.join(test['cmd'])}")
        
        # 執行命令
        result = subprocess.run(test['cmd'], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 命令執行成功")
            
            # 檢查生成的圖片
            for expected_file in test['expected_files']:
                if os.path.exists(expected_file):
                    file_size = os.path.getsize(expected_file)
                    print(f"✅ 圖片已生成: {expected_file} ({file_size} bytes)")
                else:
                    print(f"❌ 圖片未生成: {expected_file}")
        else:
            print(f"❌ 命令執行失敗: {result.stderr}")

def test_master_controller_integration():
    """測試 master_controller 的集成功能"""
    print("\n=== 測試 master_controller 集成功能 ===")
    
    # 清理舊圖片
    os.system("rm -f data/picture/*_full_history_return_pic.png")
    
    # 模擬執行 master_controller 的第7步
    print("\n--- 模擬 master_controller 第7步 ---")
    cmd = ['python3', 'draw_return_metrics_v3.py', '--output-dir', 'data/picture']
    print(f"執行命令: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ 第7步執行成功")
        
        # 檢查生成的全歷史圖片
        expected_files = [
            'data/picture/BTC_binance_bybit_full_history_return_pic.png',
            'data/picture/ETH_binance_bybit_full_history_return_pic.png',
            'data/picture/ADA_binance_bybit_full_history_return_pic.png'
        ]
        
        for expected_file in expected_files:
            if os.path.exists(expected_file):
                file_size = os.path.getsize(expected_file)
                print(f"✅ 全歷史圖片已生成: {expected_file} ({file_size} bytes)")
            else:
                print(f"❌ 全歷史圖片未生成: {expected_file}")
    else:
        print(f"❌ 第7步執行失敗: {result.stderr}")

def test_send_ranking_charts():
    """測試 send_ranking_charts 功能"""
    print("\n=== 測試 send_ranking_charts 功能 ===")
    
    # 確保有全歷史圖片
    os.system("python3 draw_return_metrics_v3.py --output-dir data/picture")
    
    # 測試發送功能
    test_code = '''
import sys
sys.path.append(".")
from master_controller import MasterController

controller = MasterController()
try:
    controller.send_ranking_charts(target_date="2025-07-15", strategy="original")
    print("✅ send_ranking_charts 測試完成")
except Exception as e:
    print(f"❌ send_ranking_charts 測試失敗: {e}")
'''
    
    result = subprocess.run(['python3', '-c', test_code], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

def test_data_verification():
    """驗證測試數據"""
    print("\n=== 驗證測試數據 ===")
    
    try:
        conn = sqlite3.connect('data/funding_rate.db')
        cursor = conn.cursor()
        
        # 檢查各表的數據量
        tables = ['funding_rate_history', 'funding_rate_diff', 'return_metrics', 'strategy_ranking']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"✅ {table}: {count} 條記錄")
        
        # 檢查日期範圍
        cursor.execute("SELECT MIN(date), MAX(date) FROM return_metrics")
        min_date, max_date = cursor.fetchone()
        print(f"✅ return_metrics 日期範圍: {min_date} 到 {max_date}")
        
        # 檢查排名數據
        cursor.execute("SELECT trading_pair, rank_position FROM strategy_ranking WHERE strategy_name = 'original' ORDER BY rank_position")
        rankings = cursor.fetchall()
        print(f"✅ original 策略排名:")
        for trading_pair, rank_position in rankings:
            print(f"   第{rank_position}名: {trading_pair}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 數據驗證失敗: {e}")
        return False

def cleanup_test_files():
    """清理測試文件"""
    print("\n=== 清理測試文件 ===")
    os.system("rm -f data/picture/*_full_history_return_pic.png")
    os.system("rm -f data/picture/*_2025-07-10-2025-07-15_return_pic.png")
    print("✅ 測試文件已清理")

def main():
    """主測試函數"""
    print("🚀 開始全歷史圖片功能測試")
    print("=" * 60)
    
    # 步驟1：準備測試數據
    print("\n步驟1：準備測試數據")
    if not run_sql_script('test_data_setup.sql'):
        print("❌ 測試數據準備失敗，終止測試")
        return
    
    # 步驟2：驗證測試數據
    print("\n步驟2：驗證測試數據")
    if not test_data_verification():
        print("❌ 測試數據驗證失敗，終止測試")
        return
    
    # 步驟3：測試 draw_return_metrics_v3.py 參數
    print("\n步驟3：測試 draw_return_metrics_v3.py 參數")
    test_draw_return_metrics_parameters()
    
    # 步驟4：測試 master_controller 集成
    print("\n步驟4：測試 master_controller 集成")
    test_master_controller_integration()
    
    # 步驟5：測試 send_ranking_charts
    print("\n步驟5：測試 send_ranking_charts")
    test_send_ranking_charts()
    
    # 步驟6：清理測試文件
    print("\n步驟6：清理測試文件")
    cleanup_test_files()
    
    print("\n" + "=" * 60)
    print("🎉 全歷史圖片功能測試完成")
    print("=" * 60)

if __name__ == "__main__":
    main() 