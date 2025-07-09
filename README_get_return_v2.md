# Get Return v2.0 使用指南

## 📋 功能概述
get_return_v2.py 是套利收益分析工具的升級版本，在 v1.0 的基礎上新增了：
- 🤖 自動模式：每天自動計算昨天的收益
- 📱 Telegram 通知：執行結果自動推送到 Telegram
- ⏰ 排程支持：配合系統排程工具實現無人值守運行

## 🚀 快速開始

### 1. 設定API配置
```bash
# 複製配置範例文件
cp api_config.py.example api_config.py

# 編輯 api_config.py 填入真實的 API 金鑰
```

在 `api_config.py` 中填入：
- Binance API 金鑰和密鑰
- Bybit API 金鑰和密鑰
- Telegram Bot Token 和 Chat ID

### 2. Telegram Bot 設定
1. 在 Telegram 搜索 `@BotFather`
2. 發送 `/newbot` 創建新機器人
3. 獲取 Bot Token
4. 向你的機器人發送一條訊息
5. 訪問 `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` 獲取 Chat ID

### 3. 手動執行
```bash
# 分析昨天的收益
python3 get_return_v2.py --auto

# 手動指定日期
python3 get_return_v2.py --start 2024-01-01 --end 2024-01-31

# 交互式模式
python3 get_return_v2.py
```

## ⏰ 自動排程設定

### Linux/macOS (使用 cron)
```bash
# 編輯 crontab
crontab -e

# 添加以下行：每天 UTC 00:00 執行
0 0 * * * cd /path/to/your/project && python3 get_return_v2.py --auto
```

### Windows (使用工作排程器)
1. 打開「工作排程器」
2. 創建基本工作
3. 設定觸發器：每天 00:00 (UTC)
4. 設定動作：啟動程式 `python.exe get_return_v2.py --auto`

## 📱 Telegram 通知範例

### 開始執行通知
```
🚀 套利收益分析開始
📅 分析日期: 2024-01-15
⏰ 開始時間: 2024-01-16 00:00:15 UTC

正在獲取數據中...
```

### 成功完成通知
```
✅ 套利收益分析完成
📅 分析日期: 2024-01-15
━━━━━━━━━━━━━━━━━━━━
💰 總淨收益: $123.45
📊 交易對數: 5
📈 平均收益率: 0.0456%
📊 年化收益率: 16.64%
━━━━━━━━━━━━━━━━━━━━
⏰ 完成時間: 2024-01-16 00:05:23 UTC
```

### 錯誤通知
```
❌ 套利收益分析失敗
📅 分析日期: 2024-01-15
━━━━━━━━━━━━━━━━━━━━
🔍 錯誤信息: API connection timeout
⏰ 發生時間: 2024-01-16 00:02:15 UTC

請檢查程式和API連接狀態
```

## 📊 輸出文件

程式執行後會產生以下 CSV 文件：
- `csv/Return/overall_stat_YYYY_MM_DD.csv` - 整體統計
- `csv/Return/binance_stat_YYYY_MM_DD.csv` - 幣安數據
- `csv/Return/bybit_stat_YYYY_MM_DD.csv` - Bybit數據
- `csv/Return/margin_history.csv` - 保證金歷史記錄

## 🔧 常用命令

```bash
# 測試自動模式
python3 get_return_v2.py --auto

# 分析特定日期
python3 get_return_v2.py --start 2024-01-15 --end 2024-01-15

# 分析最近一週
python3 get_return_v2.py --start 2024-01-08 --end 2024-01-15

# 查看幫助
python3 get_return_v2.py --help
```

## 🛠️ 故障排除

### 常見問題
1. **API 連接失敗**
   - 檢查網絡連接
   - 確認 API 金鑰正確
   - 確認 API 權限設定

2. **Telegram 通知失敗**
   - 確認 Bot Token 正確
   - 確認 Chat ID 正確
   - 檢查機器人是否被封鎖

3. **保證金數據缺失**
   - 檢查是否有持倉
   - 確認 API 有讀取權限
   - 手動執行一次更新保證金數據

### 日誌檢查
程式運行時會輸出詳細日誌，如遇問題請查看：
- 終端輸出
- 系統排程日誌 (cron logs)

## 🔄 從 v1.0 升級

v2.0 完全兼容 v1.0 的所有功能，可以：
1. 繼續使用原有的交互式模式
2. 所有輸出格式保持一致
3. 配置文件僅需添加 Telegram 相關配置

## 📝 注意事項

1. **安全性**
   - 不要將 `api_config.py` 提交到版本控制
   - 定期更新 API 金鑰
   - 使用最小權限原則

2. **資源使用**
   - 程式會調用大量 API，注意頻率限制
   - 建議在網路穩定的環境運行

3. **數據準確性**
   - 保證金數據基於運行時的持倉情況
   - 建議每日固定時間運行以保持一致性

## 🆘 支援

如有問題或建議，請：
1. 檢查日誌輸出
2. 確認配置文件設定
3. 測試 API 連接狀態
4. 聯繫開發者 