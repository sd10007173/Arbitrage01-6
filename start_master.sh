#!/bin/bash
# 資金費率套利系統 - 主控制器啟動腳本
# 功能：自動啟動虛擬環境並執行 master_controller_v3.py
# 使用方式：./start_master.sh [參數]
# 範例：./start_master.sh --exchanges binance bybit --top_n 100 --strategy original --yes

# 進入腳本所在目錄
cd "$(dirname "$0")"

# 檢查虛擬環境是否存在
if [ ! -d "venv" ]; then
    echo "❌ 虛擬環境不存在，請先執行 setup_environment.sh"
    exit 1
fi

# 啟動虛擬環境
source venv/bin/activate

# 檢查 Python 環境
echo "🔍 環境檢查："
echo "Python 版本：$(python3 --version)"
echo "Python 路徑：$(which python3)"
echo "工作目錄：$(pwd)"
echo ""

# 顯示建議的使用方式
echo "💡 建議直接使用以下命令："
echo "   source venv/bin/activate"
echo "   python3 master_controller_v3.py --exchanges binance bybit --top_n 5 --start_date 2025-07-14 --end_date 2025-07-15 --strategy original --yes"
echo ""

# 執行主控制器
echo "🚀 啟動資金費率套利系統..."
python3 master_controller_v3.py "$@"

# 保存退出狀態
exit_code=$?

# 根據退出狀態顯示結果
if [ $exit_code -eq 0 ]; then
    echo "✅ 程式執行完成"
else
    echo "❌ 程式執行失敗，退出碼：$exit_code"
fi

exit $exit_code