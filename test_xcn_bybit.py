#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試XCN在Bybit的成交量資料
"""

import ccxt
import json
from datetime import datetime

def test_xcn_bybit_volume():
    """測試XCN在Bybit的最近3天成交量"""
    try:
        # 初始化Bybit交易所
        exchange = ccxt.bybit({'options': {'defaultType': 'swap'}})
        
        symbol = 'XCN/USDT'
        print(f"🔍 測試 {symbol} 在 Bybit 的成交量資料")
        print("=" * 50)
        
        # 獲取最近3天的OHLCV資料
        print("📊 獲取最近3天的OHLCV資料...")
        recent_ohlcv = exchange.fetch_ohlcv(symbol, '1d', limit=3)
        
        print(f"✅ 成功獲取 {len(recent_ohlcv)} 筆資料")
        print("\n詳細資料：")
        
        for i, candle in enumerate(recent_ohlcv):
            timestamp = candle[0]
            open_price = candle[1]
            high = candle[2]
            low = candle[3]
            close = candle[4]
            volume = candle[5]
            
            date = datetime.fromtimestamp(timestamp / 1000)
            
            print(f"第{i+1}天 ({date.strftime('%Y-%m-%d')}):")
            print(f"  開盤: {open_price}")
            print(f"  最高: {high}")
            print(f"  最低: {low}")
            print(f"  收盤: {close}")
            print(f"  成交量: {volume}")
            print(f"  成交量 > 0: {volume > 0 if volume is not None else False}")
            print()
        
        # 檢查是否有成交量 (模擬原程式邏輯)
        has_recent_volume = any(candle[5] > 0 for candle in recent_ohlcv if candle[5] is not None)
        
        print("=" * 50)
        print(f"🎯 原程式判斷結果:")
        print(f"   has_recent_volume = {has_recent_volume}")
        print(f"   bybit_support 會被設為: {1 if has_recent_volume else 0}")
        
        return recent_ohlcv
        
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return None

if __name__ == "__main__":
    test_xcn_bybit_volume()