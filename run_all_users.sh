#!/bin/bash
# 批次執行所有用戶的套利收益分析 (Shell 版本)
# 自動尋找並執行所有 .env.* 檔案

# 設定路徑
PROJECT_DIR="/Users/chenhourun/Desktop/Arbitrage01-3"
PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"  # 統一使用 Python 3.11
LOG_DIR="$PROJECT_DIR/logs"

# 確保日誌目錄存在
mkdir -p "$LOG_DIR"

# 取得當前日期時間
CURRENT_DATE=$(date +"%Y-%m-%d")
CURRENT_TIME=$(date +"%Y-%m-%d %H:%M:%S")
LOG_FILE="$LOG_DIR/batch_execution_${CURRENT_DATE}.log"

echo "=========================================" | tee -a "$LOG_FILE"
echo "🔄 批次執行套利收益分析" | tee -a "$LOG_FILE"
echo "📅 執行日期: $CURRENT_DATE" | tee -a "$LOG_FILE"
echo "⏰ 開始時間: $CURRENT_TIME" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"

# 切換到專案目錄
cd "$PROJECT_DIR"

# 計數器
TOTAL=0
SUCCESS=0
FAILED=0

# 尋找所有 .env.* 檔案（排除 .example 和 .template）
for ENV_FILE in .env.*; do
    # 跳過範例檔案
    if [[ "$ENV_FILE" == *.example ]] || [[ "$ENV_FILE" == *.template ]]; then
        continue
    fi
    
    # 跳過不存在的檔案（當沒有匹配時）
    if [ ! -f "$ENV_FILE" ]; then
        continue
    fi
    
    # 提取用戶名（從 .env.xxx 提取 xxx）
    USER_NAME=${ENV_FILE#.env.}
    
    TOTAL=$((TOTAL + 1))
    
    echo "" | tee -a "$LOG_FILE"
    echo "[$TOTAL] 執行用戶: $USER_NAME" | tee -a "$LOG_FILE"
    echo "----------------------------------------" | tee -a "$LOG_FILE"
    
    # 執行分析
    $PYTHON_PATH get_return_multi_user.py --auto --user "$USER_NAME" 2>&1 | tee -a "$LOG_FILE"
    
    # 檢查執行結果
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "✅ $USER_NAME 執行成功" | tee -a "$LOG_FILE"
        SUCCESS=$((SUCCESS + 1))
    else
        echo "❌ $USER_NAME 執行失敗" | tee -a "$LOG_FILE"
        FAILED=$((FAILED + 1))
    fi
    
    # 等待2秒避免API限制（最後一個不等待）
    if [ $TOTAL -gt 0 ]; then
        sleep 2
    fi
done

# 顯示總結
echo "" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"
echo "📊 執行總結" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"
echo "總計: $TOTAL 個用戶" | tee -a "$LOG_FILE"
echo "成功: $SUCCESS 個" | tee -a "$LOG_FILE"
echo "失敗: $FAILED 個" | tee -a "$LOG_FILE"
echo "⏰ 結束時間: $(date +"%Y-%m-%d %H:%M:%S")" | tee -a "$LOG_FILE"
echo "📁 日誌檔案: $LOG_FILE" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"

# 返回狀態碼
if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi