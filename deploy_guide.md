# 🚀 Arbitrage01-3 部署指南

## 📋 部署前檢查清單

### 目標電腦需求
- [ ] Python 3.7+ 已安裝
- [ ] 至少 1GB 可用空間
- [ ] 網路連接正常

### 檔案準備
- [ ] 已複製完整的 Arbitrage01-3 目錄
- [ ] requirements.txt 檔案存在
- [ ] 所有 .py 檔案完整

## 🔧 部署步驟

### 步驟1：環境設定
```bash
# 進入專案目錄
cd /path/to/Arbitrage01-3

# 設定執行權限
chmod +x setup_environment.sh start_master.sh cron_job.sh

# 執行環境設定（會自動創建虛擬環境和安裝套件）
./setup_environment.sh
```

### 步驟2：功能測試
```bash
# 測試幫助訊息
./start_master.sh --help

# 測試核心功能（不實際執行）
./start_master.sh --exchanges binance bybit --top_n 10 --strategy original --yes --no-telegram
```

### 步驟3：配置定時任務
```bash
# 編輯 cron_job.sh，修改專案路徑
nano cron_job.sh
# 將 PROJECT_DIR="/path/to/Arbitrage01-3" 改為實際路徑

# 編輯 crontab
crontab -e

# 添加定時任務（例如每天 8:00 執行）
0 8 * * * /path/to/Arbitrage01-3/cron_job.sh
```

## 🎯 標準化使用方式

### 手動執行
```bash
# 基本執行
./start_master.sh --exchanges binance bybit --top_n 100 --strategy original --yes

# 自動更新模式
./start_master.sh --exchanges binance bybit --top_n 100 --start_date up_to_date --end_date up_to_date --strategy original --yes

# 發送前後5名圖片
./start_master.sh --exchanges binance bybit --top_n 100 --strategy original --yes --telegram_send 5

# 不發送圖片
./start_master.sh --exchanges binance bybit --top_n 100 --strategy original --yes --telegram_send 0
```

### 自動執行（crontab）
```bash
# 每天 8:00 自動執行
0 8 * * * /path/to/Arbitrage01-3/cron_job.sh

# 每 6 小時執行一次
0 */6 * * * /path/to/Arbitrage01-3/cron_job.sh
```

## 🔍 常見問題排解

### 問題1：Permission denied
```bash
# 解決方案：設定執行權限
chmod +x setup_environment.sh start_master.sh cron_job.sh
```

### 問題2：Python 版本不匹配
```bash
# 解決方案：重新創建虛擬環境
rm -rf venv
./setup_environment.sh
```

### 問題3：套件安裝失敗
```bash
# 解決方案：使用預編譯版本
source venv/bin/activate
pip install --only-binary=all -r requirements.txt
```

### 問題4：資料庫連接失敗
```bash
# 確保資料庫目錄存在
mkdir -p data
# 測試資料庫連接
python database_schema.py
```

## 📊 日誌檢查

### 查看最新日誌
```bash
# 查看今天的日誌
cat logs/cron_$(date +%Y%m%d).log

# 查看最新10筆日誌
tail -n 10 logs/cron_$(date +%Y%m%d).log

# 即時監控日誌
tail -f logs/cron_$(date +%Y%m%d).log
```

### 日誌清理
```bash
# 刪除超過30天的日誌（自動執行）
find logs/ -name "cron_*.log" -mtime +30 -delete
```

## 🚨 部署驗證

### 必要驗證項目
- [ ] Python 環境正確（`python --version`）
- [ ] 套件導入成功（`python -c "import pandas"`）
- [ ] 資料庫連接正常（`python database_schema.py`）
- [ ] 主控制器執行正常（`./start_master.sh --help`）
- [ ] 定時任務設定正確（`crontab -l`）

### 部署完成確認
```bash
# 執行完整測試
./start_master.sh --exchanges binance bybit --top_n 10 --strategy original --yes --no-telegram

# 確認執行成功
echo $?  # 應該輸出 0
```

## 📝 更新和維護

### 套件更新
```bash
source venv/bin/activate
pip list --outdated
pip install --upgrade 套件名稱
pip freeze > requirements.txt
```

### 環境重建
```bash
# 完全重新設定環境
rm -rf venv
./setup_environment.sh
```

## 🎯 成功指標

部署成功後，你應該能夠：
- ✅ 在任何電腦上執行 `./start_master.sh --help` 看到幫助訊息
- ✅ 執行 `./start_master.sh` 命令啟動系統
- ✅ 通過 crontab 自動執行定時任務
- ✅ 查看日誌瞭解執行狀態
- ✅ 命令行方式在不同電腦上保持一致

這就達到了「可以丟到任何一台電腦上時都可以比較順利地跑得起來，而且下命令行的方式都類似」的目標！