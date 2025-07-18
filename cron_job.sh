#!/bin/bash
# 資金費率套利系統 - 定時任務腳本
# 功能：用於 crontab 定時執行，包含完整的日誌記錄
# 使用方式：在 crontab 中設定此腳本的絕對路徑

# 設定專案目錄（請根據實際部署路徑修改）
PROJECT_DIR="/path/to/Arbitrage01-3"
cd "$PROJECT_DIR"

# 設定日誌目錄
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

# 設定日誌檔案
LOG_FILE="$LOG_DIR/cron_$(date +%Y%m%d).log"

# 記錄開始時間
echo "===============================================" >> "$LOG_FILE"
echo "🕐 開始時間：$(date)" >> "$LOG_FILE"
echo "📁 工作目錄：$(pwd)" >> "$LOG_FILE"

# 啟動虛擬環境
source venv/bin/activate

# 記錄環境資訊
echo "🐍 Python 版本：$(python --version)" >> "$LOG_FILE"
echo "📍 Python 路徑：$(which python)" >> "$LOG_FILE"

# 執行主控制器
echo "🚀 開始執行資金費率套利系統..." >> "$LOG_FILE"
python master_controller_v3.py \
  --exchanges binance bybit \
  --top_n 100 \
  --start_date up_to_date \
  --end_date up_to_date \
  --strategy original \
  --yes \
  --telegram_send 3 \
  >> "$LOG_FILE" 2>&1

# 記錄結束狀態
exit_code=$?
echo "🏁 結束時間：$(date)" >> "$LOG_FILE"
echo "📊 退出碼：$exit_code" >> "$LOG_FILE"

if [ $exit_code -eq 0 ]; then
    echo "✅ 執行成功" >> "$LOG_FILE"
else
    echo "❌ 執行失敗" >> "$LOG_FILE"
fi

echo "===============================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# 清理超過 30 天的日誌
find "$LOG_DIR" -name "cron_*.log" -mtime +30 -delete

exit $exit_code