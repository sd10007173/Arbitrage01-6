#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
調試Bybit手續費API回應格式
"""

import hashlib
import hmac
import time
import requests
from datetime import datetime, timezone, timedelta
import json
from api_config import BYBIT_API_KEY, BYBIT_SECRET_KEY

class BybitTradingFeeDebugger:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = 'https://api.bybit.com'

    def generate_signature(self, params: dict) -> str:
        """生成API簽名"""
        sorted_params = sorted(params.items())
        query_string = '&'.join(f"{key}={value}" for key, value in sorted_params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def debug_raw_response(self, target_date):
        """調試原始API回應"""
        start_dt = datetime.strptime(target_date, '%Y-%m-%d')
        
        start_ts = int(start_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int((start_dt + timedelta(days=1) - timedelta(seconds=1)).replace(tzinfo=timezone.utc).timestamp() * 1000)

        params = {
            "accountType": "UNIFIED",
            "type": "TRADE", 
            "limit": "200",
            "startTime": str(start_ts),
            "endTime": str(end_ts),
            "api_key": self.api_key,
            "timestamp": str(int(time.time() * 1000))
        }

        sign = self.generate_signature(params)
        params["sign"] = sign

        url = f"{self.base_url}/v5/account/transaction-log"
        
        print(f"🔍 調試 {target_date} 的交易記錄...")
        print(f"查詢時間範圍: {datetime.fromtimestamp(start_ts/1000, tz=timezone.utc)} - {datetime.fromtimestamp(end_ts/1000, tz=timezone.utc)}")
        print("=" * 80)
        
        try:
            response = requests.get(url, params=params, timeout=30)
            print(f"HTTP狀態碼: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"API回應碼: {data.get('retCode', 'N/A')}")
                print(f"API回應訊息: {data.get('retMsg', 'N/A')}")
                
                if data.get("retCode") == 0 and 'result' in data:
                    result = data['result']
                    records = result.get('list', [])
                    
                    print(f"總記錄數: {len(records)}")
                    print("=" * 80)
                    
                    if records:
                        # 分析記錄格式
                        print("📋 記錄格式分析:")
                        print("-" * 40)
                        
                        for i, record in enumerate(records[:5]):  # 只顯示前5筆
                            print(f"\n第{i+1}筆記錄:")
                            print(f"  完整記錄: {json.dumps(record, indent=4, ensure_ascii=False)}")
                            print("-" * 40)
                        
                        # 重點分析手續費相關欄位
                        print("\n🔍 手續費欄位分析:")
                        print("=" * 80)
                        
                        fee_fields = ['fee', 'feeRate', 'execFee', 'tradingFee', 'commission']
                        
                        for record in records:
                            time_str = datetime.fromtimestamp(
                                int(record['transactionTime'])/1000, tz=timezone.utc
                            ).strftime('%Y-%m-%d %H:%M:%S UTC')
                            
                            print(f"時間: {time_str}")
                            print(f"交易對: {record.get('symbol', 'N/A')}")
                            print(f"交易類型: {record.get('type', 'N/A')}")
                            
                            # 檢查所有可能的手續費欄位
                            for field in fee_fields:
                                if field in record:
                                    print(f"  {field}: {record[field]}")
                            
                            # 檢查所有欄位（尋找可能的手續費欄位）
                            print("  所有欄位:")
                            for key, value in record.items():
                                if 'fee' in key.lower() or 'commission' in key.lower():
                                    print(f"    {key}: {value}")
                            
                            print("-" * 60)
                        
                        # 過濾AWEUSDT記錄
                        awe_records = [r for r in records if r.get('symbol') == 'AWEUSDT']
                        print(f"\n🎯 AWEUSDT記錄數: {len(awe_records)}")
                        
                        if awe_records:
                            print("AWEUSDT詳細記錄:")
                            for i, record in enumerate(awe_records):
                                print(f"\n第{i+1}筆AWEUSDT記錄:")
                                print(json.dumps(record, indent=2, ensure_ascii=False))
                        
                    else:
                        print("❌ 該日期沒有找到任何交易記錄")
                else:
                    print(f"❌ API錯誤: {data.get('retMsg', 'Unknown error')}")
                    print(f"完整回應: {json.dumps(data, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ HTTP錯誤: {response.status_code}")
                print(f"回應內容: {response.text}")
                
        except Exception as e:
            print(f"❌ 請求異常: {str(e)}")

def main():
    print("🔍 Bybit手續費API調試工具")
    print("=" * 50)
    
    debugger = BybitTradingFeeDebugger(BYBIT_API_KEY, BYBIT_SECRET_KEY)
    
    # 調試2025-07-02（用戶截圖顯示有交易的日期）
    target_date = "2025-07-02"
    debugger.debug_raw_response(target_date)

if __name__ == "__main__":
    main() 