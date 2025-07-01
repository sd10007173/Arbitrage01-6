-- 超參數調優系統測試數據設置
-- 執行前請確保已備份數據庫

-- ===========================================
-- 階段一：清理舊的測試數據
-- ===========================================
DELETE FROM funding_rates WHERE trading_pair LIKE 'TEST_%';
DELETE FROM return_metrics WHERE trading_pair LIKE 'TEST_%';
DELETE FROM strategy_ranking WHERE strategy_name LIKE 'TEST_%';
DELETE FROM backtest_results WHERE strategy_name LIKE 'TEST_%';
DELETE FROM backtest_trades WHERE backtest_id LIKE 'TEST_%';
DELETE FROM backtest_equity_curve WHERE backtest_id LIKE 'TEST_%';

-- ===========================================
-- 階段二：插入基礎測試數據
-- ===========================================

-- 插入測試用的資金費率數據
INSERT INTO funding_rates (trading_pair, exchange, timestamp, funding_rate, next_funding_time) VALUES
-- TEST_A：穩定正收益（預期高Sharpe Ratio + 高Win Rate）
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

-- TEST_B：波動收益（預期中等Sharpe Ratio + 中等Win Rate）
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

-- TEST_C：負收益（預期低Sharpe Ratio + 低Win Rate）
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
-- TEST_A：預期高Sharpe Ratio + 高Win Rate（80%勝率）
('TEST_A_binance_bybit', '2025-06-01', 0.002, 1.002, 0.002, 1.002),
('TEST_A_binance_bybit', '2025-06-02', 0.0023, 1.0023, 0.0043, 1.0043),
('TEST_A_binance_bybit', '2025-06-03', 0.0021, 1.0021, 0.0064, 1.0064),
('TEST_A_binance_bybit', '2025-06-04', 0.003, 1.003, 0.0094, 1.0094),
('TEST_A_binance_bybit', '2025-06-05', 0.0025, 1.0025, 0.0119, 1.0119),

-- TEST_B：預期中等Sharpe Ratio + 中等Win Rate（40%勝率）
('TEST_B_binance_bybit', '2025-06-01', 0.0005, 1.0005, 0.0005, 1.0005),
('TEST_B_binance_bybit', '2025-06-02', -0.0018, 0.9982, -0.0013, 0.9987),
('TEST_B_binance_bybit', '2025-06-03', 0.001, 1.001, -0.0003, 0.9997),
('TEST_B_binance_bybit', '2025-06-04', -0.0008, 0.9992, -0.0011, 0.9989),
('TEST_B_binance_bybit', '2025-06-05', 0.0007, 1.0007, -0.0004, 0.9996),

-- TEST_C：預期低Sharpe Ratio + 低Win Rate（0%勝率）
('TEST_C_binance_bybit', '2025-06-01', -0.0002, 0.9998, -0.0002, 0.9998),
('TEST_C_binance_bybit', '2025-06-02', -0.0003, 0.9997, -0.0005, 0.9995),
('TEST_C_binance_bybit', '2025-06-03', -0.0002, 0.9998, -0.0007, 0.9993),
('TEST_C_binance_bybit', '2025-06-04', -0.0004, 0.9996, -0.0011, 0.9989),
('TEST_C_binance_bybit', '2025-06-05', -0.0003, 0.9997, -0.0014, 0.9986);

-- ===========================================
-- 階段三：插入邊界測試數據
-- ===========================================

-- 極值測試數據
INSERT INTO return_metrics (trading_pair, date, return_1d, roi_1d, return_7d, roi_7d) VALUES
-- 極大正值
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-01', 0.1, 1.1, 0.1, 1.1),
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-02', 0.05, 1.05, 0.15, 1.15),
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-03', 0.08, 1.08, 0.23, 1.23),
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-04', 0.06, 1.06, 0.29, 1.29),
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-05', 0.04, 1.04, 0.33, 1.33),

-- 極大負值  
('TEST_EXTREME_LOW_binance_bybit', '2025-06-01', -0.1, 0.9, -0.1, 0.9),
('TEST_EXTREME_LOW_binance_bybit', '2025-06-02', -0.05, 0.95, -0.15, 0.85),
('TEST_EXTREME_LOW_binance_bybit', '2025-06-03', -0.08, 0.92, -0.23, 0.77),
('TEST_EXTREME_LOW_binance_bybit', '2025-06-04', -0.06, 0.94, -0.29, 0.71),
('TEST_EXTREME_LOW_binance_bybit', '2025-06-05', -0.04, 0.96, -0.33, 0.67),

-- 零值
('TEST_ZERO_binance_bybit', '2025-06-01', 0.0, 1.0, 0.0, 1.0),
('TEST_ZERO_binance_bybit', '2025-06-02', 0.0, 1.0, 0.0, 1.0),
('TEST_ZERO_binance_bybit', '2025-06-03', 0.0, 1.0, 0.0, 1.0),
('TEST_ZERO_binance_bybit', '2025-06-04', 0.0, 1.0, 0.0, 1.0),
('TEST_ZERO_binance_bybit', '2025-06-05', 0.0, 1.0, 0.0, 1.0);

-- NULL值測試（應該被跳過）
INSERT INTO return_metrics (trading_pair, date, return_1d, roi_1d, return_7d, roi_7d) VALUES
('TEST_NULL_binance_bybit', '2025-06-01', NULL, NULL, NULL, NULL),
('TEST_NULL_binance_bybit', '2025-06-02', NULL, NULL, NULL, NULL),
('TEST_NULL_binance_bybit', '2025-06-03', NULL, NULL, NULL, NULL),
('TEST_NULL_binance_bybit', '2025-06-04', NULL, NULL, NULL, NULL),
('TEST_NULL_binance_bybit', '2025-06-05', NULL, NULL, NULL, NULL);

-- ===========================================
-- 驗證測試數據是否正確插入
-- ===========================================

-- 檢查插入的數據量
SELECT 
    'funding_rates' as table_name, 
    COUNT(*) as count,
    COUNT(DISTINCT trading_pair) as unique_pairs,
    MIN(timestamp) as earliest_date,
    MAX(timestamp) as latest_date
FROM funding_rates 
WHERE trading_pair LIKE 'TEST_%'

UNION ALL

SELECT 
    'return_metrics' as table_name, 
    COUNT(*) as count,
    COUNT(DISTINCT trading_pair) as unique_pairs,
    MIN(date) as earliest_date,
    MAX(date) as latest_date
FROM return_metrics 
WHERE trading_pair LIKE 'TEST_%';

-- 檢查各個測試交易對的數據完整性
SELECT 
    trading_pair,
    COUNT(*) as record_count,
    MIN(date) as start_date,
    MAX(date) as end_date,
    AVG(return_1d) as avg_return_1d,
    AVG(return_7d) as avg_return_7d,
    SUM(CASE WHEN return_1d > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate_pct
FROM return_metrics 
WHERE trading_pair LIKE 'TEST_%'
  AND return_1d IS NOT NULL
GROUP BY trading_pair
ORDER BY trading_pair;

-- 預期結果驗證：
-- TEST_A: 高平均收益率，高勝率（80%）
-- TEST_B: 中等平均收益率，中等勝率（40%）
-- TEST_C: 負平均收益率，低勝率（0%）
-- TEST_EXTREME_HIGH: 極高收益率
-- TEST_EXTREME_LOW: 極低收益率
-- TEST_ZERO: 零收益率
-- TEST_NULL: 應該被跳過，不會出現在結果中

COMMIT; 