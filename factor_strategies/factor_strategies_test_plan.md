# Factor Strategies 測試計劃

## 概述
本測試計劃針對因子策略系統的四個核心模組進行全面測試：
- `factor_engine.py` - 因子計算引擎
- `factor_library.py` - 因子計算函數庫
- `factor_strategy_config.py` - 策略配置文件
- `run_factor_strategies.py` - 主執行腳本

## 測試目標總覽：
- 測試目標1：因子策略配置解析與驗證
- 測試目標2：因子計算函數正確性驗證  
- 測試目標3：數據獲取與過濾邏輯驗證
- 測試目標4：缓存系統功能驗證
- 測試目標5：策略排名計算邏輯驗證
- 測試目標6：數據庫寫入與讀取驗證
- 測試目標7：命令行參數與執行模式驗證
- 測試目標8：異常情況處理驗證
- 測試目標9：並行執行與性能驗證
- 測試目標10：邊界條件與數據完整性驗證

---

## 測試目標1：因子策略配置解析與驗證
- **測試方式：** 驗證策略配置文件的正確解析和參數驗證
- **測試資料設計：** 無需特殊數據，使用配置文件本身
- **測試資料插入的sql：** 無
- **驗證測試資料的sql：** 
```sql
-- 驗證配置可被正確讀取
SELECT 1 as config_test;
```

## 測試目標2：因子計算函數正確性驗證
- **測試方式：** 使用已知輸入驗證各個因子函數的數學計算正確性
- **測試資料設計：** 創建標準化的收益率序列，包含上升趨勢、下降趨勢、波動較大、穩定等不同場景
- **測試資料插入的sql：**
```sql
-- 插入測試用的標準化收益率數據
INSERT INTO return_metrics (trading_pair, date, roi_1d, roi_7d, return_1d, return_7d, roi_14d, roi_30d) VALUES
-- 上升趨勢數據 (30天)
('TEST_TREND_UP', '2025-01-01', 0.01, 0.07, 0.01, 0.07, 0.14, 0.30),
('TEST_TREND_UP', '2025-01-02', 0.015, 0.08, 0.015, 0.08, 0.15, 0.32),
('TEST_TREND_UP', '2025-01-03', 0.012, 0.075, 0.012, 0.075, 0.145, 0.31),
('TEST_TREND_UP', '2025-01-04', 0.018, 0.09, 0.018, 0.09, 0.16, 0.35),
-- 繼續插入26天數據...
-- 下降趨勢數據
('TEST_TREND_DOWN', '2025-01-01', -0.01, -0.07, -0.01, -0.07, -0.14, -0.30),
('TEST_TREND_DOWN', '2025-01-02', -0.015, -0.08, -0.015, -0.08, -0.15, -0.32);
-- 繼續插入28天數據...
```
- **驗證測試資料的sql：**
```sql
-- 驗證測試數據已正確插入
SELECT trading_pair, COUNT(*) as days_count, 
       AVG(roi_1d) as avg_roi_1d, 
       STDDEV(roi_1d) as std_roi_1d
FROM return_metrics 
WHERE trading_pair LIKE 'TEST_%' 
GROUP BY trading_pair;
```

## 測試目標3：數據獲取與過濾邏輯驗證
- **測試方式：** 驗證引擎能正確獲取指定日期範圍的數據，並按配置過濾新幣
- **測試資料設計：** 創建包含新上線幣種和老幣種的混合數據集
- **測試資料插入的sql：**
```sql
-- 插入老幣種數據 (上線超過7天)
INSERT INTO return_metrics (trading_pair, date, roi_1d, roi_7d, return_1d, return_7d) VALUES
('OLD_COIN_A', '2024-12-20', 0.01, 0.07, 0.01, 0.07),
('OLD_COIN_A', '2024-12-21', 0.015, 0.08, 0.015, 0.08),
-- 繼續插入到2025-01-30...
-- 插入新幣種數據 (剛上線2天)
('NEW_COIN_B', '2025-01-29', 0.02, 0.05, 0.02, 0.05),
('NEW_COIN_B', '2025-01-30', 0.025, 0.06, 0.025, 0.06);
```
- **驗證測試資料的sql：**
```sql
-- 驗證數據過濾邏輯
SELECT trading_pair, 
       MIN(date) as first_date, 
       MAX(date) as last_date,
       COUNT(*) as total_days,
       JULIANDAY('2025-01-30') - JULIANDAY(MIN(date)) as days_since_first
FROM return_metrics 
WHERE trading_pair IN ('OLD_COIN_A', 'NEW_COIN_B', 'MID_COIN_C')
GROUP BY trading_pair;
```

## 測試目標4：缓存系統功能驗證
- **測試方式：** 驗證數據缓存和因子計算缓存的命中率、過期機制、LRU管理
- **測試資料設計：** 使用重複的查詢參數觸發缓存機制
- **測試資料插入的sql：**
```sql
-- 插入大量相似參數的數據，用於觸發缓存
INSERT INTO return_metrics (trading_pair, date, roi_1d, return_1d) VALUES
('CACHE_TEST_1', '2025-01-30', 0.01, 0.01),
('CACHE_TEST_2', '2025-01-30', 0.01, 0.01),
('CACHE_TEST_3', '2025-01-30', 0.01, 0.01),
('CACHE_TEST_4', '2025-01-30', 0.01, 0.01),
('CACHE_TEST_5', '2025-01-30', 0.01, 0.01);
```
- **驗證測試資料的sql：**
```sql
-- 驗證缓存測試數據
SELECT COUNT(DISTINCT trading_pair) as unique_pairs,
       COUNT(*) as total_records
FROM return_metrics 
WHERE trading_pair LIKE 'CACHE_TEST_%';
```

## 測試目標5：策略排名計算邏輯驗證
- **測試方式：** 驗證因子分數計算、Z-Score標準化、權重組合邏輯的正確性
- **測試資料設計：** 創建可預測結果的標準化數據集
- **測試資料插入的sql：**
```sql
-- 插入排名測試數據 (可預測的數學結果)
INSERT INTO return_metrics (trading_pair, date, roi_1d, roi_7d, return_1d, return_7d) VALUES
-- 最佳表現幣種 (高趨勢、高夏普、低波動、高勝率)
('RANK_BEST', '2025-01-01', 0.02, 0.14, 0.02, 0.14),
('RANK_BEST', '2025-01-02', 0.022, 0.154, 0.022, 0.154),
-- 最差表現幣種 (負趨勢、低夏普、高波動、低勝率)  
('RANK_WORST', '2025-01-01', -0.01, -0.07, -0.01, -0.07),
('RANK_WORST', '2025-01-02', -0.015, -0.105, -0.015, -0.105);
-- 繼續30天...
```
- **驗證測試資料的sql：**
```sql
-- 驗證排名測試數據的分佈
SELECT trading_pair,
       AVG(roi_1d) as avg_roi_1d,
       STDDEV(roi_1d) as std_roi_1d,
       SUM(CASE WHEN roi_1d > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
FROM return_metrics 
WHERE trading_pair LIKE 'RANK_%'
GROUP BY trading_pair
ORDER BY avg_roi_1d DESC;
```

## 測試目標6：數據庫寫入與讀取驗證
- **測試方式：** 驗證策略結果正確寫入 strategy_ranking 表，格式符合預期
- **測試資料設計：** 使用上述測試數據執行策略，檢查輸出
- **測試資料插入的sql：** (使用上述已插入的測試數據)
- **驗證測試資料的sql：**
```sql
-- 驗證策略排名結果已正確寫入
SELECT strategy_name, date, 
       COUNT(*) as ranking_count,
       MIN(rank_position) as min_rank,
       MAX(rank_position) as max_rank,
       AVG(final_ranking_score) as avg_score
FROM strategy_ranking 
WHERE date = '2025-01-30' 
  AND strategy_name LIKE '%test%'
GROUP BY strategy_name, date;
```

## 測試目標7：命令行參數與執行模式驗證
- **測試方式：** 測試各種命令行參數組合和執行模式
- **測試資料設計：** 使用已有測試數據
- **測試資料插入的sql：** (使用上述已插入的測試數據)
- **驗證測試資料的sql：**
```sql
-- 驗證不同執行模式的結果
SELECT strategy_name, date, COUNT(*) as processed_pairs
FROM strategy_ranking
WHERE date BETWEEN '2025-01-29' AND '2025-01-30'
  AND strategy_name IN ('sharp_only_v1', 'sharp_only_v2', 'sharp_only_v3')
GROUP BY strategy_name, date
ORDER BY strategy_name, date;
```

## 測試目標8：異常情況處理驗證
- **測試方式：** 故意創建異常數據，驗證錯誤處理機制
- **測試資料設計：** 創建缺失數據、NULL值、極值等異常情況
- **測試資料插入的sql：**
```sql
-- 插入異常測試數據
INSERT INTO return_metrics (trading_pair, date, roi_1d, roi_7d) VALUES
-- 缺失數據 (只有1天數據)
('ERROR_NO_DATA', '2025-01-30', 0.01, 0.07),
-- NULL值數據
('ERROR_NULL_DATA', '2025-01-30', NULL, 0.07),
('ERROR_NULL_DATA', '2025-01-29', 0.01, NULL),
-- 極值數據
('ERROR_EXTREME', '2025-01-30', 999.99, 999.99),
('ERROR_EXTREME', '2025-01-29', -999.99, -999.99);
```
- **驗證測試資料的sql：**
```sql
-- 檢查異常情況是否被正確處理（不應該出現在排名中）
SELECT COUNT(*) as error_rankings
FROM strategy_ranking
WHERE trading_pair LIKE 'ERROR_%' 
  AND date = '2025-01-30';
```

## 測試目標9：並行執行與性能驗證
- **測試方式：** 比較串行與並行執行的性能差異和結果一致性
- **測試資料設計：** 使用足夠數量的測試數據觸發並行處理
- **測試資料插入的sql：**
```sql
-- 插入大量性能測試數據
WITH RECURSIVE date_series(date_val) AS (
  SELECT '2025-01-01'
  UNION ALL
  SELECT DATE(date_val, '+1 day')
  FROM date_series
  WHERE date_val < '2025-01-30'
)
INSERT INTO return_metrics (trading_pair, date, roi_1d, roi_7d, return_1d, return_7d)
SELECT 
  'PERF_' || (row_number() OVER ()) trading_pair,
  date_val,
  RANDOM() * 0.02 - 0.01 as roi_1d,  -- 隨機 -1% 到 1%
  RANDOM() * 0.14 - 0.07 as roi_7d,  -- 隨機 -7% 到 7%
  RANDOM() * 0.02 - 0.01 as return_1d,
  RANDOM() * 0.14 - 0.07 as return_7d
FROM date_series
CROSS JOIN (
  SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5
) t;
```
- **驗證測試資料的sql：**
```sql
-- 檢查並行執行結果的一致性
SELECT strategy_name, date, COUNT(*) as ranking_count
FROM strategy_ranking
WHERE trading_pair LIKE 'PERF_%'
GROUP BY strategy_name, date
ORDER BY strategy_name, date;
```

## 測試目標10：邊界條件與數據完整性驗證
- **測試方式：** 測試各種邊界條件，如最小數據量、日期邊界、策略配置邊界
- **測試資料設計：** 精確控制數據量，測試臨界情況
- **測試資料插入的sql：**
```sql
-- 插入邊界條件測試數據
WITH RECURSIVE boundary_dates(date_val, day_num) AS (
  SELECT '2024-12-28', 1  -- 從12月28日開始，確保到1月30日有34天
  UNION ALL
  SELECT DATE(date_val, '+1 day'), day_num + 1
  FROM boundary_dates
  WHERE day_num < 34
)
INSERT INTO return_metrics (trading_pair, date, roi_1d, roi_7d, return_1d, return_7d)
SELECT 
  'BOUNDARY_MIN',
  date_val,
  0.01 * (day_num - 17) / 17 as roi_1d,  -- 線性趨勢
  0.07 * (day_num - 17) / 17 as roi_7d,
  0.01 * (day_num - 17) / 17 as return_1d,
  0.07 * (day_num - 17) / 17 as return_7d
FROM boundary_dates;

-- 不滿足要求的數據 (只有2天)
INSERT INTO return_metrics (trading_pair, date, roi_1d, roi_7d, return_1d, return_7d) VALUES
('BOUNDARY_INSUFFICIENT', '2025-01-29', 0.01, 0.07, 0.01, 0.07),
('BOUNDARY_INSUFFICIENT', '2025-01-30', 0.015, 0.08, 0.015, 0.08);
```
- **驗證測試資料的sql：**
```sql
-- 檢查邊界條件的處理結果
SELECT 
  CASE 
    WHEN EXISTS (SELECT 1 FROM strategy_ranking WHERE trading_pair = 'BOUNDARY_MIN' AND date = '2025-01-30') 
    THEN 'BOUNDARY_MIN processed' 
    ELSE 'BOUNDARY_MIN skipped' 
  END as min_result,
  CASE 
    WHEN EXISTS (SELECT 1 FROM strategy_ranking WHERE trading_pair = 'BOUNDARY_INSUFFICIENT' AND date = '2025-01-30') 
    THEN 'BOUNDARY_INSUFFICIENT processed' 
    ELSE 'BOUNDARY_INSUFFICIENT skipped' 
  END as insufficient_result;
```

## 測試執行順序建議

1. **配置測試** (目標1) - 確保基礎配置正確
2. **函數測試** (目標2) - 驗證數學計算正確性  
3. **數據測試** (目標3) - 驗證數據獲取邏輯
4. **功能測試** (目標4-6) - 驗證核心功能
5. **集成測試** (目標7-8) - 驗證整體系統
6. **性能測試** (目標9-10) - 驗證性能和邊界

## 預期測試結果

每個測試目標都應該有明確的通過/失敗標準：
- ✅ **通過**：功能符合預期，數據正確
- ❌ **失敗**：功能異常，需要修復
- ⚠️ **警告**：功能正常但性能或邊界情況需要注意

---

*最後更新：2025-01-02* 