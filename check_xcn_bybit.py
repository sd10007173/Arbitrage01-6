#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢查Bybit所有包含XCN的交易對
"""

import ccxt

def check_xcn_in_bybit():
    """檢查Bybit是否有XCN相關交易對"""
    try:
        # 檢查期貨市場
        print("🔍 檢查Bybit期貨市場...")
        exchange_future = ccxt.bybit({'options': {'defaultType': 'swap'}})
        future_markets = exchange_future.load_markets()
        
        xcn_futures = [symbol for symbol in future_markets.keys() if 'XCN' in symbol]
        print(f"期貨市場XCN相關交易對: {xcn_futures}")
        
        # 檢查現貨市場
        print("\n🔍 檢查Bybit現貨市場...")
        exchange_spot = ccxt.bybit({'options': {'defaultType': 'spot'}})
        spot_markets = exchange_spot.load_markets()
        
        xcn_spots = [symbol for symbol in spot_markets.keys() if 'XCN' in symbol]
        print(f"現貨市場XCN相關交易對: {xcn_spots}")
        
        # 總結
        all_xcn = xcn_futures + xcn_spots
        print(f"\n📊 總結: Bybit共有 {len(all_xcn)} 個XCN相關交易對")
        for symbol in all_xcn:
            print(f"  - {symbol}")
            
        return len(all_xcn) > 0
        
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return False

if __name__ == "__main__":
    has_xcn = check_xcn_in_bybit()
    print(f"\n🎯 結論: Bybit {'有' if has_xcn else '沒有'} XCN交易對")