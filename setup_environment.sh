#!/bin/bash
# 資金費率套利系統 - 環境設定腳本
# 功能：在新電腦上快速設定 Python 虛擬環境
# 使用方式：./setup_environment.sh

echo "🔧 開始設定 Python 虛擬環境..."
echo "=" * 60

# 檢查 Python 3 是否存在
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安裝，請先安裝 Python 3.7+"
    exit 1
fi

echo "✅ Python 版本：$(python3 --version)"
echo "✅ Python 路徑：$(which python3)"

# 進入專案目錄
cd "$(dirname "$0")"
echo "✅ 工作目錄：$(pwd)"

# 刪除舊的虛擬環境（如果存在）
if [ -d "venv" ]; then
    echo "🗑️  刪除舊的虛擬環境..."
    rm -rf venv
fi

# 創建新的虛擬環境
echo "🏗️  創建新的虛擬環境..."
python3 -m venv venv

# 啟動虛擬環境
echo "🔧 啟動虛擬環境..."
source venv/bin/activate

# 升級 pip
echo "⬆️  升級 pip..."
pip install --upgrade pip

# 安裝套件
echo "📦 安裝必要套件..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "❌ requirements.txt 不存在"
    exit 1
fi

# 功能測試
echo "🧪 執行功能測試..."
python -c "
import pandas as pd
import numpy as np
import ccxt
import aiohttp
import matplotlib
from database_operations import DatabaseManager
print('✅ 所有核心套件導入成功')
"

if [ $? -eq 0 ]; then
    echo "✅ 環境設定完成！"
    echo ""
    echo "🎯 使用方式："
    echo "  ./start_master.sh --help                    # 查看幫助"
    echo "  ./start_master.sh --exchanges binance bybit --top_n 100 --strategy original --yes"
    echo ""
    echo "📁 重要檔案："
    echo "  venv/                 # 虛擬環境目錄"
    echo "  requirements.txt      # 套件清單"
    echo "  start_master.sh       # 啟動腳本"
    echo "  setup_environment.sh  # 環境設定腳本"
else
    echo "❌ 環境設定失敗，請檢查錯誤訊息"
    exit 1
fi