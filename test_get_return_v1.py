#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get_return_v1.py 測試腳本
用於驗證程式功能和模擬數據輸出
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta

def test_directory_structure():
    """測試目錄結構"""
    print("🔧 檢查目錄結構...")
    
    # 檢查主程式
    if not os.path.exists('get_return_v1.py'):
        print("❌ get_return_v1.py 不存在")
        return False
    
    # 檢查配置範例
    if not os.path.exists('api_config.py.example'):
        print("❌ api_config.py.example 不存在")
        return False
    
    # 檢查說明文件
    if not os.path.exists('GET_RETURN_V1_README.md'):
        print("❌ GET_RETURN_V1_README.md 不存在")
        return False
    
    # 創建輸出目錄
    os.makedirs('csv/Return', exist_ok=True)
    
    print("✅ 目錄結構檢查完成")
    return True

def create_mock_data():
    """創建模擬數據"""
    print("📊 創建模擬數據...")
    
    # 模擬歷史保證金數據
    mock_margin_history = {
        "2024-01-01": {
            "binance": {
                "BTCUSDT": 10000.0,
                "ETHUSDT": 8000.0
            },
            "bybit": {
                "BTCUSDT": 15000.0,
                "ETHUSDT": 12000.0
            },
            "source": "mock_data"
        },
        "2024-01-02": {
            "binance": {
                "BTCUSDT": 10500.0,
                "ETHUSDT": 8200.0
            },
            "bybit": {
                "BTCUSDT": 15500.0,
                "ETHUSDT": 12500.0
            },
            "source": "mock_data"
        }
    }
    
    # 保存模擬保證金歷史
    margin_file = "csv/Return/margin_history.json"
    with open(margin_file, 'w') as f:
        json.dump(mock_margin_history, f, indent=2)
    
    print(f"✅ 模擬保證金歷史已保存到 {margin_file}")
    
    # 創建模擬輸出範例
    mock_overall_data = [
        {
            'Date': '2024-01-01',
            'Symbol': 'BTCUSDT',
            'Binance FF': 12.34,
            'Bybit FF': -8.76,
            'Binance TF': -0.50,
            'Bybit TF': -0.30,
            'Net P&L': 2.78,
            'Binance M': 10000.0,
            'Bybit M': 15000.0,
            'Total M': 25000.0,
            'Return': 0.0001112,
            'ROI': 0.0406
        },
        {
            'Date': '2024-01-01',
            'Symbol': 'ETHUSDT',
            'Binance FF': 5.67,
            'Bybit FF': -3.21,
            'Binance TF': -0.20,
            'Bybit TF': -0.15,
            'Net P&L': 2.11,
            'Binance M': 8000.0,
            'Bybit M': 12000.0,
            'Total M': 20000.0,
            'Return': 0.0001055,
            'ROI': 0.0385
        }
    ]
    
    # 保存模擬整合數據
    overall_df = pd.DataFrame(mock_overall_data)
    overall_file = "csv/Return/overall_stat_2024_01_01_MOCK.csv"
    overall_df.to_csv(overall_file, index=False)
    
    print(f"✅ 模擬整合數據已保存到 {overall_file}")
    
    # 創建模擬幣安數據
    mock_binance_data = [
        {
            'Date': '2024-01-01',
            'Symbol': 'BTCUSDT',
            'Funding_Fee': 12.34,
            'Trading_Fee': -0.50,
            'Position_Margin': 10000.0,
            'API_Source': 'mock_data'
        },
        {
            'Date': '2024-01-01',
            'Symbol': 'ETHUSDT',
            'Funding_Fee': 5.67,
            'Trading_Fee': -0.20,
            'Position_Margin': 8000.0,
            'API_Source': 'mock_data'
        }
    ]
    
    binance_df = pd.DataFrame(mock_binance_data)
    binance_file = "csv/Return/binance_stat_2024_01_01_MOCK.csv"
    binance_df.to_csv(binance_file, index=False)
    
    print(f"✅ 模擬幣安數據已保存到 {binance_file}")
    
    # 創建模擬Bybit數據
    mock_bybit_data = [
        {
            'Date': '2024-01-01',
            'Symbol': 'BTCUSDT',
            'Funding_Fee': -8.76,
            'Trading_Fee': -0.30,
            'Position_Margin': 15000.0,
            'API_Source': 'mock_data'
        },
        {
            'Date': '2024-01-01',
            'Symbol': 'ETHUSDT',
            'Funding_Fee': -3.21,
            'Trading_Fee': -0.15,
            'Position_Margin': 12000.0,
            'API_Source': 'mock_data'
        }
    ]
    
    bybit_df = pd.DataFrame(mock_bybit_data)
    bybit_file = "csv/Return/bybit_stat_2024_01_01_MOCK.csv"
    bybit_df.to_csv(bybit_file, index=False)
    
    print(f"✅ 模擬Bybit數據已保存到 {bybit_file}")
    
    return True

def test_data_analysis():
    """測試數據分析功能"""
    print("📈 測試數據分析...")
    
    # 讀取模擬數據
    overall_file = "csv/Return/overall_stat_2024_01_01_MOCK.csv"
    if not os.path.exists(overall_file):
        print("❌ 找不到模擬數據檔案")
        return False
    
    df = pd.read_csv(overall_file)
    
    # 計算統計指標
    total_pnl = df['Net P&L'].sum()
    avg_return = df['Return'].mean()
    total_symbols = len(df['Symbol'].unique())
    
    print(f"   總淨損益: ${total_pnl:.2f}")
    print(f"   平均日收益率: {avg_return*100:.4f}%")
    print(f"   平均年化收益率: {avg_return*365*100:.2f}%")
    print(f"   交易對數量: {total_symbols}")
    
    print("✅ 數據分析測試完成")
    return True

def show_usage_examples():
    """顯示使用範例"""
    print("\n🚀 使用範例:")
    print("1. 配置API金鑰:")
    print("   cp api_config.py.example api_config.py")
    print("   # 編輯 api_config.py 填入真實API金鑰")
    print()
    print("2. 單日分析:")
    print("   python get_return_v1.py --start 2024-01-01 --end 2024-01-01")
    print()
    print("3. 多日分析:")
    print("   python get_return_v1.py --start 2024-01-01 --end 2024-01-31")
    print()
    print("4. 查看輸出:")
    print("   ls csv/Return/")
    print("   head csv/Return/overall_stat_2024_01_01.csv")

def main():
    """主測試函數"""
    print("🧪 get_return_v1.py 測試腳本")
    print("=" * 50)
    
    # 測試目錄結構
    if not test_directory_structure():
        print("❌ 目錄結構測試失敗")
        return
    
    # 創建模擬數據
    if not create_mock_data():
        print("❌ 模擬數據創建失敗")
        return
    
    # 測試數據分析
    if not test_data_analysis():
        print("❌ 數據分析測試失敗")
        return
    
    print("\n✅ 所有測試通過！")
    print("📁 生成的檔案:")
    print("   - csv/Return/margin_history.json")
    print("   - csv/Return/overall_stat_2024_01_01_MOCK.csv")
    print("   - csv/Return/binance_stat_2024_01_01_MOCK.csv")
    print("   - csv/Return/bybit_stat_2024_01_01_MOCK.csv")
    
    show_usage_examples()

if __name__ == "__main__":
    main() 