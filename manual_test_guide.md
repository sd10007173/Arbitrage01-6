# 手動測試指導手冊

## 🎯 測試目標
找出 `strategy_ranking_v3.py`, `calculate_FR_return_list_v3.py`, 和 `master_controller_v2.py` 的潛在問題。

## 📋 測試前準備

### 1. 備份數據庫
```bash
cp data/funding_rate.db data/funding_rate_backup.db
```

### 2. 檢查當前數據狀況
```bash
sqlite3 data/funding_rate.db "SELECT 'funding_rate_history' as table_name, MIN(DATE(timestamp_utc)) as min_date, MAX(DATE(timestamp_utc)) as max_date, COUNT(*) as total_records FROM funding_rate_history UNION ALL SELECT 'funding_rate_diff', MIN(DATE(timestamp_utc)), MAX(DATE(timestamp_utc)), COUNT(*) FROM funding_rate_diff UNION ALL SELECT 'return_metrics', MIN(date), MAX(date), COUNT(*) FROM return_metrics UNION ALL SELECT 'strategy_ranking', MIN(date), MAX(date), COUNT(*) FROM strategy_ranking"
```

## 🧪 快速測試場景

### 場景1: 空數據測試
```bash
# 刪除2025-07-01後的數據
sqlite3 data/funding_rate.db "DELETE FROM funding_rate_history WHERE timestamp_utc >= '2025-07-01'"
sqlite3 data/funding_rate.db "DELETE FROM funding_rate_diff WHERE timestamp_utc >= '2025-07-01'"
sqlite3 data/funding_rate.db "DELETE FROM return_metrics WHERE date >= '2025-07-01'"
sqlite3 data/funding_rate.db "DELETE FROM strategy_ranking WHERE date >= '2025-07-01'"

# 測試 calculate_FR_return_list_v3
python calculate_FR_return_list_v3.py
python calculate_FR_return_list_v3.py --check-only
python calculate_FR_return_list_v3.py --process-latest

# 測試 strategy_ranking_v3
echo "1" | python strategy_ranking_v3.py
python strategy_ranking_v3.py --check-only

# 測試 master_controller_v2
python master_controller_v2.py --top_n 5
```

### 場景2: 單交易對測試
```bash
# 恢復數據
cp data/funding_rate_backup.db data/funding_rate.db

# 只保留一個交易對
sqlite3 data/funding_rate.db "DELETE FROM return_metrics WHERE trading_pair != 'BTC_binance_bybit'"
sqlite3 data/funding_rate.db "DELETE FROM strategy_ranking WHERE trading_pair != 'BTC_binance_bybit'"

# 測試所有程序
python calculate_FR_return_list_v3.py --symbol BTC_binance_bybit
python strategy_ranking_v3.py --symbol BTC_binance_bybit --strategies original
python master_controller_v2.py --top_n 1
```

### 場景3: 極端值測試
```bash
# 恢復數據
cp data/funding_rate_backup.db data/funding_rate.db

# 插入極端值
sqlite3 data/funding_rate.db "INSERT OR REPLACE INTO funding_rate_diff (timestamp_utc, symbol, exchange_a, exchange_b, diff_ab) VALUES ('2025-07-15 08:00:00', 'EXTREME_TEST', 'binance', 'bybit', 999999.0)"

# 測試處理極端值
python calculate_FR_return_list_v3.py --start_date 2025-07-15 --end_date 2025-07-15
python strategy_ranking_v3.py --start_date 2025-07-15 --end_date 2025-07-15 --strategies original
```

### 場景4: NULL值測試
```bash
# 恢復數據
cp data/funding_rate_backup.db data/funding_rate.db

# 創建NULL值
sqlite3 data/funding_rate.db "UPDATE funding_rate_diff SET diff_ab = NULL WHERE symbol = 'BTC' AND timestamp_utc >= '2025-07-15'"
sqlite3 data/funding_rate.db "UPDATE return_metrics SET return_1d = NULL, roi_1d = NULL WHERE trading_pair LIKE 'ETH%' AND date >= '2025-07-15'"

# 測試NULL值處理
python calculate_FR_return_list_v3.py --start_date 2025-07-15 --end_date 2025-07-16
python strategy_ranking_v3.py --start_date 2025-07-15 --end_date 2025-07-16 --strategies original
```

## 🚨 重點檢查項目

### 1. calculate_FR_return_list_v3.py
- [ ] 是否正確處理空數據？
- [ ] 是否正確處理NULL值？
- [ ] 是否正確處理極端值？
- [ ] 是否正確處理數據缺口？
- [ ] 執行時間是否合理？
- [ ] 錯誤信息是否清晰？

### 2. strategy_ranking_v3.py
- [ ] 是否產生有效的 final_ranking_score？
- [ ] 是否正確計算排名位置？
- [ ] 是否正確處理單個交易對？
- [ ] 是否正確處理所有指標相同的情況？
- [ ] 是否正確處理不存在的策略？

### 3. master_controller_v2.py
- [ ] 是否正確傳遞 top_n 參數？
- [ ] 是否正確處理無效參數？
- [ ] 是否正確執行完整流程？
- [ ] 是否正確生成 Telegram 圖片？

## 🔍 問題檢測清單

### 常見錯誤信號
- [ ] Python traceback 出現
- [ ] 返回碼不為 0
- [ ] 執行時間異常長（>2分鐘）
- [ ] 輸出包含 "ERROR" 或 "Exception"
- [ ] 數據庫鎖定錯誤
- [ ] NULL 分數問題復現

### 性能問題信號
- [ ] 記憶體使用量過高
- [ ] CPU 使用率持續100%
- [ ] 磁盤 I/O 異常高
- [ ] 網絡連接超時

### 邏輯問題信號
- [ ] 所有交易對排名相同
- [ ] 分數全部為 NULL
- [ ] 計算結果不合理
- [ ] 數據不一致

## 💡 測試技巧

### 1. 使用監控工具
```bash
# 監控資源使用
top -p $(pgrep -f python)

# 監控磁盤使用
df -h

# 監控數據庫大小
ls -lh data/funding_rate.db
```

### 2. 檢查日誌文件
```bash
# 查看最新日誌
tail -f logs/strategy_ranking_v3.log
tail -f logs/calculate_FR_return_list_v3.log

# 搜索錯誤
grep -i error logs/*.log
grep -i exception logs/*.log
```

### 3. 數據庫診斷
```bash
# 檢查數據完整性
sqlite3 data/funding_rate.db ".schema"
sqlite3 data/funding_rate.db "PRAGMA integrity_check"

# 檢查表大小
sqlite3 data/funding_rate.db "SELECT name, COUNT(*) FROM sqlite_master sm JOIN pragma_table_info(sm.name) pti GROUP BY name"
```

## ⚡ 自動化測試

### 使用測試腳本
```bash
# 設置測試場景
python setup_test_scenarios.py

# 運行全面邊界測試
python run_boundary_tests.py

# 檢查測試報告
ls -la *test_report*.json
```

### 自定義測試
```python
# 創建自定義測試腳本
from setup_test_scenarios import TestScenarioSetup

setup = TestScenarioSetup()
setup.backup_database()
setup.scenario_1_empty_data()  # 設置空數據場景
# 然後手動運行測試...
setup.restore_database()
```

## 🎯 成功標準

### 必須通過的測試
1. ✅ 所有基本功能正常運行
2. ✅ 邊界條件不導致崩潰
3. ✅ 錯誤處理得當
4. ✅ 性能在可接受範圍內
5. ✅ 數據完整性得到保證

### 問題發現目標
- 🎯 找出至少 **3個邊界條件問題**
- 🎯 找出至少 **2個數據處理問題**
- 🎯 找出至少 **1個性能問題**
- 🎯 找出至少 **1個用戶體驗問題**

## 🔄 測試完成後
```bash
# 恢復原始數據
cp data/funding_rate_backup.db data/funding_rate.db

# 清理測試文件
rm -f test_report_*.json
rm -f boundary_test_report_*.json
```

記住：**好的測試是找到問題的測試**！不要害怕破壞系統，盡全力找出潛在問題。 