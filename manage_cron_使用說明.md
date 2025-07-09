# manage_cron.sh 使用說明

## 功能概述
- **UTC+0 時間模式**：所有時間輸入都以 UTC+0 為準，系統自動轉換為本地時區
- **命令行模式**：支援快速命令行操作
- **交互模式**：提供友好的選單介面

## 系統環境
- 系統時區：CST (UTC+8)
- 時間轉換：UTC+0 時間 + 8 小時 = CST 時間

## 使用方法

### 1. 命令行模式

```bash
# 進入項目目錄
cd ~/Downloads/Arbitrage01-3

# 查看當前設定
./manage_cron.sh -s

# 設定每天 00:00 (UTC+0) 執行
./manage_cron.sh -0

# 設定每天 08:00 (UTC+0) 執行
./manage_cron.sh -8

# 自訂時間（例如：每天 14:30 UTC+0）
./manage_cron.sh --custom "30 14 * * *"

# 刪除所有任務
./manage_cron.sh -d

# 顯示說明
./manage_cron.sh -h
```

### 2. 交互模式

```bash
# 啟動交互模式
./manage_cron.sh

# 會顯示選單：
# 1. 查看當前設定
# 2. 設定每日執行時間 (UTC+0)
# 3. 刪除所有任務
# 4. 退出
```

## 時間轉換範例

| UTC+0 時間 | CST 時間 | cron 設定 | 說明 |
|-----------|---------|----------|-----|
| 00:00     | 08:00   | 0 8 * * * | 每天 UTC+0 午夜 |
| 08:00     | 16:00   | 0 16 * * * | 每天 UTC+0 上午8點 |
| 14:30     | 22:30   | 30 22 * * * | 每天 UTC+0 下午2點30分 |

## 當前設定
```bash
每天 00:00 (UTC+0) 執行 get_return_v2.py --auto
對應 CST 時間：08:00
cron 設定：0 8 * * *
```

## 注意事項
1. 所有時間輸入都以 UTC+0 為準
2. 系統會自動轉換為本地時區 (CST)
3. 自訂時間格式：`分 時 日 月 週`
4. 複雜時間格式（如 */6）可能需要手動調整

## 檔案位置
- 管理腳本：`/Users/waynechen/Downloads/Arbitrage01-3/manage_cron.sh`
- 執行日誌：`/Users/waynechen/Downloads/Arbitrage01-3/logs/cron_get_return.log`
- 主程式：`/Users/waynechen/Downloads/Arbitrage01-3/get_return_v2.py` 