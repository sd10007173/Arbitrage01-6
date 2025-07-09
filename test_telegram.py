#!/usr/bin/env python3
import requests
from api_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def test_telegram():
    """測試 Telegram 通知功能"""
    print("🔍 測試 Telegram 通知...")
    print(f"Bot Token: {TELEGRAM_BOT_TOKEN}")
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    
    # 測試發送消息
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    message = "🧪 測試消息 - 直接測試"
    
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, data=data, timeout=30)
        print(f"狀態碼: {response.status_code}")
        print(f"回應內容: {response.text}")
        
        if response.status_code == 200:
            print("✅ Telegram 通知成功！")
            return True
        else:
            print("❌ Telegram 通知失敗")
            return False
    except Exception as e:
        print(f"❌ 異常: {str(e)}")
        return False

if __name__ == "__main__":
    test_telegram() 