#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次執行所有用戶的套利收益分析
自動尋找並執行所有 .env.* 檔案（排除 .env.example）
"""

import os
import sys
import subprocess
import time
from datetime import datetime, timezone
import glob
import re

def find_env_files():
    """尋找所有的 .env.* 檔案"""
    env_files = []
    
    # 尋找所有 .env.* 檔案
    for file in glob.glob(".env.*"):
        # 排除範例檔案
        if file.endswith('.example') or file.endswith('.template'):
            continue
        
        # 從檔名提取用戶名
        match = re.match(r'^\.env\.(.+)$', file)
        if match:
            user_name = match.group(1)
            env_files.append((file, user_name))
    
    return sorted(env_files)

def run_user_analysis(env_file, user_name):
    """執行單個用戶的分析"""
    print(f"\n{'='*60}")
    print(f"🚀 開始執行用戶: {user_name}")
    print(f"📁 環境檔案: {env_file}")
    print(f"⏰ 開始時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*60}")
    
    try:
        # 執行分析命令 - 使用專案虛擬環境的 Python
        # 動態獲取當前專案的Python路徑
        script_dir = os.path.dirname(os.path.abspath(__file__))
        python_path = os.path.join(script_dir, "venv", "bin", "python3")
        
        # 如果虛擬環境Python不存在，回退到系統Python
        if not os.path.exists(python_path):
            # 嘗試使用python3.12
            python312_path = os.path.join(script_dir, "venv", "bin", "python3.12")
            if os.path.exists(python312_path):
                python_path = python312_path
            else:
                python_path = "python3"
        
        cmd = [
            python_path,
            os.path.join(script_dir, "get_return_multi_user.py"),
            "--auto",
            "--user",
            user_name
        ]
        
        # 切換到專案目錄並執行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5分鐘超時
            cwd=script_dir  # 確保在專案目錄中執行
        )
        
        # 顯示輸出
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print(f"⚠️ 錯誤訊息:\n{result.stderr}", file=sys.stderr)
        
        if result.returncode == 0:
            print(f"✅ {user_name} 執行成功")
            return True
        else:
            print(f"❌ {user_name} 執行失敗 (返回碼: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ {user_name} 執行超時")
        return False
    except Exception as e:
        print(f"❌ {user_name} 執行異常: {str(e)}")
        return False

def main():
    """主程式"""
    print("="*70)
    print("🔄 批次執行套利收益分析")
    print(f"📅 執行日期: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    print(f"⏰ 開始時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*70)
    
    # 尋找所有環境檔案
    env_files = find_env_files()
    
    if not env_files:
        print("❌ 未找到任何 .env.* 檔案")
        return 1
    
    print(f"\n📋 找到 {len(env_files)} 個用戶配置:")
    for env_file, user_name in env_files:
        print(f"   • {user_name} ({env_file})")
    
    # 執行結果統計
    success_count = 0
    failed_users = []
    
    # 批次執行
    for i, (env_file, user_name) in enumerate(env_files, 1):
        print(f"\n[{i}/{len(env_files)}] 處理中...")
        
        success = run_user_analysis(env_file, user_name)
        
        if success:
            success_count += 1
        else:
            failed_users.append(user_name)
        
        # 如果不是最後一個，等待2秒避免API限制
        if i < len(env_files):
            print(f"\n⏳ 等待2秒後繼續...")
            time.sleep(2)
    
    # 顯示總結
    print("\n" + "="*70)
    print("📊 執行總結")
    print("="*70)
    print(f"✅ 成功: {success_count}/{len(env_files)}")
    
    if failed_users:
        print(f"❌ 失敗用戶: {', '.join(failed_users)}")
    
    print(f"⏰ 結束時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*70)
    
    # 返回狀態碼（0=全部成功，1=部分或全部失敗）
    return 0 if success_count == len(env_files) else 1

if __name__ == "__main__":
    sys.exit(main())