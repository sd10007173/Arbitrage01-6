# 超參數調優系統手動測試計劃

## 📋 測試概覽

### 測試目標
驗證超參數調優系統各組件的正確性和數據一致性，確保因子策略生成、回測執行、結果分析的完整工作流程。

### 測試架構
```
測試數據 → 因子策略生成 → 策略排名存儲 → 回測執行 → 結果驗證
```

---

## 🎯 階段一：因子策略生成測試

### 測試目標
- 驗證FactorEngine能正確計算因子分數
- 驗證Z-Score標準化邏輯
- 驗證權重加權計算
- 驗證strategy_ranking表數據完整性

### 測試方式
使用精心設計的測試數據，運行因子策略生成，驗證計算結果。

### 測試數據設計

#### 1. 基礎測試數據（3個交易對，5天數據）
- **目的**：驗證基本計算邏輯
- **特點**：簡單、可手工驗證的數據

```sql
-- 清理測試數據
DELETE FROM funding_rates WHERE trading_pair LIKE 'TEST_%';
DELETE FROM return_metrics WHERE trading_pair LIKE 'TEST_%';
DELETE FROM strategy_ranking WHERE strategy_name LIKE 'TEST_%';

-- 插入測試用的資金費率數據
INSERT INTO funding_rates (trading_pair, exchange, timestamp, funding_rate, next_funding_time) VALUES
-- TEST_A：穩定正收益
('TEST_A_binance_bybit', 'binance', '2025-06-01 08:00:00', 0.001, '2025-06-01 16:00:00'),
('TEST_A_binance_bybit', 'bybit', '2025-06-01 08:00:00', -0.001, '2025-06-01 16:00:00'),
('TEST_A_binance_bybit', 'binance', '2025-06-02 08:00:00', 0.0015, '2025-06-02 16:00:00'),
('TEST_A_binance_bybit', 'bybit', '2025-06-02 08:00:00', -0.0008, '2025-06-02 16:00:00'),
('TEST_A_binance_bybit', 'binance', '2025-06-03 08:00:00', 0.0012, '2025-06-03 16:00:00'),
('TEST_A_binance_bybit', 'bybit', '2025-06-03 08:00:00', -0.0009, '2025-06-03 16:00:00'),
('TEST_A_binance_bybit', 'binance', '2025-06-04 08:00:00', 0.0018, '2025-06-04 16:00:00'),
('TEST_A_binance_bybit', 'bybit', '2025-06-04 08:00:00', -0.0012, '2025-06-04 16:00:00'),
('TEST_A_binance_bybit', 'binance', '2025-06-05 08:00:00', 0.0014, '2025-06-05 16:00:00'),
('TEST_A_binance_bybit', 'bybit', '2025-06-05 08:00:00', -0.0011, '2025-06-05 16:00:00'),

-- TEST_B：波動收益
('TEST_B_binance_bybit', 'binance', '2025-06-01 08:00:00', 0.002, '2025-06-01 16:00:00'),
('TEST_B_binance_bybit', 'bybit', '2025-06-01 08:00:00', -0.0015, '2025-06-01 16:00:00'),
('TEST_B_binance_bybit', 'binance', '2025-06-02 08:00:00', -0.001, '2025-06-02 16:00:00'),
('TEST_B_binance_bybit', 'bybit', '2025-06-02 08:00:00', 0.0008, '2025-06-02 16:00:00'),
('TEST_B_binance_bybit', 'binance', '2025-06-03 08:00:00', 0.003, '2025-06-03 16:00:00'),
('TEST_B_binance_bybit', 'bybit', '2025-06-03 08:00:00', -0.002, '2025-06-03 16:00:00'),
('TEST_B_binance_bybit', 'binance', '2025-06-04 08:00:00', -0.0005, '2025-06-04 16:00:00'),
('TEST_B_binance_bybit', 'bybit', '2025-06-04 08:00:00', 0.0003, '2025-06-04 16:00:00'),
('TEST_B_binance_bybit', 'binance', '2025-06-05 08:00:00', 0.0025, '2025-06-05 16:00:00'),
('TEST_B_binance_bybit', 'bybit', '2025-06-05 08:00:00', -0.0018, '2025-06-05 16:00:00'),

-- TEST_C：負收益
('TEST_C_binance_bybit', 'binance', '2025-06-01 08:00:00', -0.001, '2025-06-01 16:00:00'),
('TEST_C_binance_bybit', 'bybit', '2025-06-01 08:00:00', 0.0008, '2025-06-01 16:00:00'),
('TEST_C_binance_bybit', 'binance', '2025-06-02 08:00:00', -0.0012, '2025-06-02 16:00:00'),
('TEST_C_binance_bybit', 'bybit', '2025-06-02 08:00:00', 0.0009, '2025-06-02 16:00:00'),
('TEST_C_binance_bybit', 'binance', '2025-06-03 08:00:00', -0.0008, '2025-06-03 16:00:00'),
('TEST_C_binance_bybit', 'bybit', '2025-06-03 08:00:00', 0.0006, '2025-06-03 16:00:00'),
('TEST_C_binance_bybit', 'binance', '2025-06-04 08:00:00', -0.0015, '2025-06-04 16:00:00'),
('TEST_C_binance_bybit', 'bybit', '2025-06-04 08:00:00', 0.0011, '2025-06-04 16:00:00'),
('TEST_C_binance_bybit', 'binance', '2025-06-05 08:00:00', -0.001, '2025-06-05 16:00:00'),
('TEST_C_binance_bybit', 'bybit', '2025-06-05 08:00:00', 0.0007, '2025-06-05 16:00:00');

-- 插入對應的return_metrics數據
INSERT INTO return_metrics (trading_pair, date, return_1d, roi_1d, return_7d, roi_7d) VALUES
-- TEST_A：預期高Sharpe Ratio + 高Win Rate
('TEST_A_binance_bybit', '2025-06-01', 0.002, 1.002, 0.002, 1.002),
('TEST_A_binance_bybit', '2025-06-02', 0.0023, 1.0023, 0.0043, 1.0043),
('TEST_A_binance_bybit', '2025-06-03', 0.0021, 1.0021, 0.0064, 1.0064),
('TEST_A_binance_bybit', '2025-06-04', 0.003, 1.003, 0.0094, 1.0094),
('TEST_A_binance_bybit', '2025-06-05', 0.0025, 1.0025, 0.0119, 1.0119),

-- TEST_B：預期中等Sharpe Ratio + 中等Win Rate
('TEST_B_binance_bybit', '2025-06-01', 0.0005, 1.0005, 0.0005, 1.0005),
('TEST_B_binance_bybit', '2025-06-02', -0.0018, 0.9982, -0.0013, 0.9987),
('TEST_B_binance_bybit', '2025-06-03', 0.001, 1.001, -0.0003, 0.9997),
('TEST_B_binance_bybit', '2025-06-04', -0.0008, 0.9992, -0.0011, 0.9989),
('TEST_B_binance_bybit', '2025-06-05', 0.0007, 1.0007, -0.0004, 0.9996),

-- TEST_C：預期低Sharpe Ratio + 低Win Rate
('TEST_C_binance_bybit', '2025-06-01', -0.0002, 0.9998, -0.0002, 0.9998),
('TEST_C_binance_bybit', '2025-06-02', -0.0003, 0.9997, -0.0005, 0.9995),
('TEST_C_binance_bybit', '2025-06-03', -0.0002, 0.9998, -0.0007, 0.9993),
('TEST_C_binance_bybit', '2025-06-04', -0.0004, 0.9996, -0.0011, 0.9989),
('TEST_C_binance_bybit', '2025-06-05', -0.0003, 0.9997, -0.0014, 0.9986);
```

#### 2. 邊界測試數據
```sql
-- 極值測試數據
INSERT INTO return_metrics (trading_pair, date, return_1d, roi_1d, return_7d, roi_7d) VALUES
-- 極大正值
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-01', 0.1, 1.1, 0.1, 1.1),
-- 極大負值  
('TEST_EXTREME_LOW_binance_bybit', '2025-06-01', -0.1, 0.9, -0.1, 0.9),
-- 零值
('TEST_ZERO_binance_bybit', '2025-06-01', 0.0, 1.0, 0.0, 1.0),
-- NULL值測試（應該被跳過）
('TEST_NULL_binance_bybit', '2025-06-01', NULL, NULL, NULL, NULL);
```

### 預期結果設計

#### 1. 因子分數預期結果
- **TEST_A**：高Sharpe Ratio（正收益，低波動）+ 高Win Rate（80%）
- **TEST_B**：中等Sharpe Ratio（正負混合）+ 中等Win Rate（40%）
- **TEST_C**：低Sharpe Ratio（負收益）+ 低Win Rate（0%）

#### 2. Z-Score標準化預期
- TEST_A 應該有最高的標準化分數
- TEST_C 應該有最低的標準化分數
- TEST_B 介於中間

### 驗證SQL

#### 1. 檢查因子策略是否生成
```sql
-- 檢查策略是否成功生成
SELECT 
    strategy_name,
    COUNT(*) as record_count,
    MIN(date) as start_date,
    MAX(date) as end_date
FROM strategy_ranking 
WHERE strategy_name LIKE 'TEST_%'
GROUP BY strategy_name
ORDER BY strategy_name;
```

#### 2. 驗證排名邏輯
```sql
-- 檢查TEST數據的排名（應該是A>B>C）
SELECT 
    trading_pair,
    final_ranking_score,
    rank_position,
    long_term_score,
    short_term_score
FROM strategy_ranking 
WHERE strategy_name = 'TEST_SR_WR_W20_1D_D20_S0_EQ' 
  AND date = '2025-06-05'
  AND trading_pair LIKE 'TEST_%'
ORDER BY rank_position;
```

#### 3. 驗證因子分數計算
```sql
-- 檢查原始因子分數是否合理
SELECT 
    trading_pair,
    long_term_score as sharpe_factor,
    short_term_score as win_rate_factor,
    final_ranking_score
FROM strategy_ranking 
WHERE strategy_name = 'TEST_SR_WR_W20_1D_D20_S0_EQ' 
  AND date = '2025-06-05'
  AND trading_pair LIKE 'TEST_%'
ORDER BY final_ranking_score DESC;
```

---

## 🎯 階段二：回測引擎測試

### 測試目標
- 驗證回測引擎能正確讀取strategy_ranking數據
- 驗證交易邏輯（進場/離場）
- 驗證資金費率收益計算
- 驗證backtest_results和backtest_trades數據準確性

### 測試方式
使用階段一生成的策略排名數據，執行短期回測，驗證交易決策和收益計算。

### 測試配置設計
```yaml
# test_backtest_config.yaml
parameters:
  available_factors: [calculate_sharpe_ratio, calculate_win_rate]
  windows: [20]
  input_columns: [roi_1d]
  min_data_days: [20]
  skip_first_n_days: [0]
  max_factors_per_strategy: 2
  min_factors_per_strategy: 2
  weight_methods: [equal]

execution:
  mode: "sampling"
  n_strategies: 1
  max_parallel_jobs: 1
  
backtest_settings:
  start_date: "2025-06-01"
  end_date: "2025-06-05"
  initial_capital: 10000
  position_size: 0.25
  max_positions: 2
  entry_top_n: 2
  exit_threshold: 3
```

### 預期回測行為
1. **2025-06-02**：進場TEST_A（排名1）和TEST_B（排名2）
2. **2025-06-03-05**：持續持有，計算資金費率收益
3. **最終結果**：TEST_A貢獻正收益，TEST_B波動收益

### 驗證SQL

#### 1. 檢查回測結果摘要
```sql
-- 檢查回測是否成功執行
SELECT 
    backtest_id,
    strategy_name,
    start_date,
    end_date,
    initial_capital,
    final_capital,
    total_return,
    total_return_pct,
    sharpe_ratio,
    max_drawdown
FROM backtest_results 
WHERE strategy_name LIKE 'TEST_%'
ORDER BY created_at DESC;
```

#### 2. 檢查交易明細
```sql
-- 檢查交易決策是否正確
SELECT 
    backtest_id,
    date,
    event_type,
    trading_pair,
    amount,
    funding_rate_diff,
    cash_balance_before,
    cash_balance_after
FROM backtest_trades 
WHERE backtest_id LIKE 'TEST_%'
ORDER BY date, id;
```

#### 3. 驗證收益計算
```sql
-- 計算預期 vs 實際收益
WITH daily_pnl AS (
    SELECT 
        date,
        SUM(CASE WHEN event_type = 'funding_rate_pnl' THEN funding_rate_diff * amount ELSE 0 END) as daily_funding_pnl
    FROM backtest_trades 
    WHERE backtest_id LIKE 'TEST_%'
    GROUP BY date
)
SELECT 
    date,
    daily_funding_pnl,
    SUM(daily_funding_pnl) OVER (ORDER BY date) as cumulative_pnl
FROM daily_pnl
ORDER BY date;
```

---

## 🎯 階段三：數據一致性測試

### 測試目標
- 驗證策略排名與回測交易的一致性
- 驗證不同組件間的數據傳遞正確性
- 驗證併發執行時的數據完整性

### 驗證SQL

#### 1. 策略排名一致性檢查
```sql
-- 檢查回測中的交易對是否都在對應日期的前N名
WITH backtest_entries AS (
    SELECT DISTINCT 
        bt.backtest_id,
        bt.trading_pair,
        bt.date as entry_date
    FROM backtest_trades bt
    WHERE bt.event_type = 'enter_position'
      AND bt.backtest_id LIKE 'TEST_%'
),
ranking_check AS (
    SELECT 
        be.backtest_id,
        be.trading_pair,
        be.entry_date,
        sr.rank_position,
        CASE WHEN sr.rank_position <= 2 THEN 'VALID' ELSE 'INVALID' END as status
    FROM backtest_entries be
    JOIN strategy_ranking sr ON 
        be.trading_pair = sr.trading_pair 
        AND DATE(be.entry_date) = sr.date
        AND sr.strategy_name LIKE 'TEST_%'
)
SELECT * FROM ranking_check WHERE status = 'INVALID';
-- 預期結果：無記錄（所有進場都應該符合前N名規則）
```

#### 2. 資金平衡檢查
```sql
-- 檢查現金 + 持倉 = 總資金
WITH balance_check AS (
    SELECT 
        backtest_id,
        date,
        cash_balance_after as cash,
        position_balance_after as positions,
        (cash_balance_after + position_balance_after) as total_calculated,
        total_balance_after as total_recorded,
        ABS((cash_balance_after + position_balance_after) - total_balance_after) as diff
    FROM backtest_trades 
    WHERE backtest_id LIKE 'TEST_%'
      AND total_balance_after IS NOT NULL
)
SELECT * FROM balance_check WHERE diff > 0.01;
-- 預期結果：無記錄（差異應該小於0.01）
```

---

## 🎯 階段四：性能和壓力測試

### 測試目標
- 驗證系統在大數據量下的穩定性
- 測試併發執行能力
- 檢查內存和時間消耗

### 大數據量測試數據生成
```sql
-- 生成100個測試交易對，30天數據
WITH RECURSIVE 
date_series AS (
    SELECT '2025-05-01' as date
    UNION ALL
    SELECT DATE(date, '+1 day')
    FROM date_series
    WHERE date < '2025-05-30'
),
pair_series AS (
    SELECT 'TEST_PERF_' || printf('%03d', value) || '_binance_bybit' as trading_pair
    FROM generate_series(1, 100)
)
INSERT INTO return_metrics (trading_pair, date, return_1d, roi_1d, return_7d, roi_7d)
SELECT 
    p.trading_pair,
    d.date,
    (RANDOM() - 0.5) * 0.01 as return_1d,  -- -0.5% to +0.5%
    1 + (RANDOM() - 0.5) * 0.01 as roi_1d,
    (RANDOM() - 0.5) * 0.05 as return_7d,  -- -2.5% to +2.5%
    1 + (RANDOM() - 0.5) * 0.05 as roi_7d
FROM pair_series p 
CROSS JOIN date_series d;
```

### 性能監控SQL
```sql
-- 監控策略生成性能
SELECT 
    strategy_name,
    COUNT(*) as record_count,
    MIN(created_at) as start_time,
    MAX(created_at) as end_time,
    (JULIANDAY(MAX(created_at)) - JULIANDAY(MIN(created_at))) * 24 * 60 as duration_minutes
FROM strategy_ranking 
WHERE strategy_name LIKE 'TEST_PERF_%'
GROUP BY strategy_name;

-- 監控回測性能
SELECT 
    backtest_id,
    COUNT(*) as trade_count,
    MIN(created_at) as start_time,
    MAX(created_at) as end_time,
    (JULIANDAY(MAX(created_at)) - JULIANDAY(MIN(created_at))) * 24 * 60 as duration_minutes
FROM backtest_trades 
WHERE backtest_id LIKE 'TEST_PERF_%'
GROUP BY backtest_id;
```

---

## 🎯 階段五：集成測試

### 測試目標
完整端到端測試，驗證整個超參數調優流程

### 測試執行計劃
1. **準備測試數據**：執行所有測試數據插入SQL
2. **運行完整流程**：`python main.py --config test_integration_config.yaml`
3. **驗證結果**：執行所有驗證SQL
4. **清理測試數據**：刪除所有TEST_開頭的數據

### 集成測試配置
```yaml
# test_integration_config.yaml
parameters:
  available_factors:
    - calculate_sharpe_ratio
    - calculate_win_rate
  windows: [20, 30]
  input_columns: [roi_1d, roi_7d]
  min_data_days: [20, 30]
  skip_first_n_days: [0, 1]
  max_factors_per_strategy: 2
  min_factors_per_strategy: 1
  weight_methods: [equal, factor_strength]

execution:
  mode: "sampling"
  n_strategies: 5
  max_parallel_jobs: 2

backtest_settings:
  start_date: "2025-06-01"
  end_date: "2025-06-05"
  initial_capital: 10000
  position_size: 0.25
```

### 最終驗證清單
- [ ] 所有策略成功生成
- [ ] 所有回測成功執行
- [ ] 數據一致性檢查通過
- [ ] 性能指標在可接受範圍內
- [ ] 無數據丟失或損壞
- [ ] 錯誤處理機制正常工作

---

## 🧹 測試數據清理

### 清理SQL
```sql
-- 清理所有測試數據
DELETE FROM funding_rates WHERE trading_pair LIKE 'TEST_%';
DELETE FROM return_metrics WHERE trading_pair LIKE 'TEST_%';
DELETE FROM strategy_ranking WHERE strategy_name LIKE 'TEST_%';
DELETE FROM backtest_results WHERE strategy_name LIKE 'TEST_%';
DELETE FROM backtest_trades WHERE backtest_id LIKE 'TEST_%';
DELETE FROM backtest_equity_curve WHERE backtest_id LIKE 'TEST_%';

-- 驗證清理完成
SELECT 'funding_rates' as table_name, COUNT(*) as remaining FROM funding_rates WHERE trading_pair LIKE 'TEST_%'
UNION ALL
SELECT 'return_metrics', COUNT(*) FROM return_metrics WHERE trading_pair LIKE 'TEST_%'
UNION ALL
SELECT 'strategy_ranking', COUNT(*) FROM strategy_ranking WHERE strategy_name LIKE 'TEST_%'
UNION ALL
SELECT 'backtest_results', COUNT(*) FROM backtest_results WHERE strategy_name LIKE 'TEST_%'
UNION ALL
SELECT 'backtest_trades', COUNT(*) FROM backtest_trades WHERE backtest_id LIKE 'TEST_%'
UNION ALL
SELECT 'backtest_equity_curve', COUNT(*) FROM backtest_equity_curve WHERE backtest_id LIKE 'TEST_%';
```

---

## 📊 測試報告模板

### 測試執行記錄
- 測試日期：
- 測試環境：
- 測試數據量：
- 執行時間：

### 測試結果
- [ ] 階段一：因子策略生成 ✅/❌
- [ ] 階段二：回測引擎 ✅/❌  
- [ ] 階段三：數據一致性 ✅/❌
- [ ] 階段四：性能測試 ✅/❌
- [ ] 階段五：集成測試 ✅/❌

### 發現的問題
- 問題1：描述
- 問題2：描述

### 建議改進
- 建議1：描述
- 建議2：描述

---

## 🚀 執行指南

1. **準備階段**：備份現有數據庫
2. **執行測試**：按階段依序執行
3. **記錄結果**：填寫測試報告
4. **清理數據**：執行清理SQL
5. **總結分析**：評估系統穩定性

這個測試計劃涵蓋了功能測試、邊界測試、性能測試和集成測試，能夠全面驗證超參數調優系統的正確性和穩定性。 