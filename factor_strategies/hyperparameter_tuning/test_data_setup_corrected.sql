-- 修正版測試數據插入腳本
-- 清理測試數據
DELETE FROM funding_rate_history WHERE symbol LIKE 'TEST%';
DELETE FROM return_metrics WHERE trading_pair LIKE 'TEST_%';
DELETE FROM strategy_ranking WHERE strategy_name LIKE 'TEST_%';

-- 清理可能的回測結果
DELETE FROM backtest_results WHERE trading_pair LIKE 'TEST_%';
DELETE FROM backtest_trades WHERE trading_pair LIKE 'TEST_%';

BEGIN TRANSACTION;

-- 插入測試用的資金費率數據（使用funding_rate_history表）
INSERT INTO funding_rate_history (timestamp_utc, symbol, exchange, funding_rate) VALUES
-- TEST_A：穩定正收益（Binance正，Bybit負，套利收益穩定）
('2025-06-01 08:00:00', 'TESTA', 'binance', 0.001),
('2025-06-01 08:00:00', 'TESTA', 'bybit', -0.001),
('2025-06-02 08:00:00', 'TESTA', 'binance', 0.0015),
('2025-06-02 08:00:00', 'TESTA', 'bybit', -0.0008),
('2025-06-03 08:00:00', 'TESTA', 'binance', 0.0012),
('2025-06-03 08:00:00', 'TESTA', 'bybit', -0.0009),
('2025-06-04 08:00:00', 'TESTA', 'binance', 0.0018),
('2025-06-04 08:00:00', 'TESTA', 'bybit', -0.0012),
('2025-06-05 08:00:00', 'TESTA', 'binance', 0.0014),
('2025-06-05 08:00:00', 'TESTA', 'bybit', -0.0011),

-- TEST_B：波動收益（收益有正有負）
('2025-06-01 08:00:00', 'TESTB', 'binance', 0.002),
('2025-06-01 08:00:00', 'TESTB', 'bybit', -0.0015),
('2025-06-02 08:00:00', 'TESTB', 'binance', -0.001),
('2025-06-02 08:00:00', 'TESTB', 'bybit', 0.0008),
('2025-06-03 08:00:00', 'TESTB', 'binance', 0.003),
('2025-06-03 08:00:00', 'TESTB', 'bybit', -0.002),
('2025-06-04 08:00:00', 'TESTB', 'binance', -0.0005),
('2025-06-04 08:00:00', 'TESTB', 'bybit', 0.0003),
('2025-06-05 08:00:00', 'TESTB', 'binance', 0.0025),
('2025-06-05 08:00:00', 'TESTB', 'bybit', -0.0018),

-- TEST_C：負收益（Binance負，Bybit正，套利虧錢）
('2025-06-01 08:00:00', 'TESTC', 'binance', -0.001),
('2025-06-01 08:00:00', 'TESTC', 'bybit', 0.0008),
('2025-06-02 08:00:00', 'TESTC', 'binance', -0.0012),
('2025-06-02 08:00:00', 'TESTC', 'bybit', 0.0009),
('2025-06-03 08:00:00', 'TESTC', 'binance', -0.0008),
('2025-06-03 08:00:00', 'TESTC', 'bybit', 0.0006),
('2025-06-04 08:00:00', 'TESTC', 'binance', -0.0015),
('2025-06-04 08:00:00', 'TESTC', 'bybit', 0.0011),
('2025-06-05 08:00:00', 'TESTC', 'binance', -0.001),
('2025-06-05 08:00:00', 'TESTC', 'bybit', 0.0007);

-- 插入對應的return_metrics數據
INSERT INTO return_metrics (trading_pair, date, return_1d, roi_1d, return_7d, roi_7d) VALUES
-- TEST_A：預期高Sharpe Ratio + 高Win Rate（5天全勝）
('TEST_A_binance_bybit', '2025-06-01', 0.002, 1.002, 0.002, 1.002),
('TEST_A_binance_bybit', '2025-06-02', 0.0023, 1.0023, 0.0043, 1.0043),
('TEST_A_binance_bybit', '2025-06-03', 0.0021, 1.0021, 0.0064, 1.0064),
('TEST_A_binance_bybit', '2025-06-04', 0.003, 1.003, 0.0094, 1.0094),
('TEST_A_binance_bybit', '2025-06-05', 0.0025, 1.0025, 0.0119, 1.0119),

-- TEST_B：預期中等Sharpe Ratio + 中等Win Rate（5天中3勝2負）
('TEST_B_binance_bybit', '2025-06-01', 0.0005, 1.0005, 0.0005, 1.0005),
('TEST_B_binance_bybit', '2025-06-02', -0.0018, 0.9982, -0.0013, 0.9987),
('TEST_B_binance_bybit', '2025-06-03', 0.001, 1.001, -0.0003, 0.9997),
('TEST_B_binance_bybit', '2025-06-04', -0.0008, 0.9992, -0.0011, 0.9989),
('TEST_B_binance_bybit', '2025-06-05', 0.0007, 1.0007, -0.0004, 0.9996),

-- TEST_C：預期低Sharpe Ratio + 低Win Rate（5天全敗）
('TEST_C_binance_bybit', '2025-06-01', -0.0002, 0.9998, -0.0002, 0.9998),
('TEST_C_binance_bybit', '2025-06-02', -0.0003, 0.9997, -0.0005, 0.9995),
('TEST_C_binance_bybit', '2025-06-03', -0.0002, 0.9998, -0.0007, 0.9993),
('TEST_C_binance_bybit', '2025-06-04', -0.0004, 0.9996, -0.0011, 0.9989),
('TEST_C_binance_bybit', '2025-06-05', -0.0003, 0.9997, -0.0014, 0.9986),

-- 邊界測試數據
-- 極大正值
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-01', 0.1, 1.1, 0.1, 1.1),
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-02', 0.1, 1.1, 0.2, 1.2),
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-03', 0.1, 1.1, 0.3, 1.3),
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-04', 0.1, 1.1, 0.4, 1.4),
('TEST_EXTREME_HIGH_binance_bybit', '2025-06-05', 0.1, 1.1, 0.5, 1.5),

-- 極大負值  
('TEST_EXTREME_LOW_binance_bybit', '2025-06-01', -0.1, 0.9, -0.1, 0.9),
('TEST_EXTREME_LOW_binance_bybit', '2025-06-02', -0.1, 0.9, -0.2, 0.8),
('TEST_EXTREME_LOW_binance_bybit', '2025-06-03', -0.1, 0.9, -0.3, 0.7),
('TEST_EXTREME_LOW_binance_bybit', '2025-06-04', -0.1, 0.9, -0.4, 0.6),
('TEST_EXTREME_LOW_binance_bybit', '2025-06-05', -0.1, 0.9, -0.5, 0.5),

-- 零值
('TEST_ZERO_binance_bybit', '2025-06-01', 0.0, 1.0, 0.0, 1.0),
('TEST_ZERO_binance_bybit', '2025-06-02', 0.0, 1.0, 0.0, 1.0),
('TEST_ZERO_binance_bybit', '2025-06-03', 0.0, 1.0, 0.0, 1.0),
('TEST_ZERO_binance_bybit', '2025-06-04', 0.0, 1.0, 0.0, 1.0),
('TEST_ZERO_binance_bybit', '2025-06-05', 0.0, 1.0, 0.0, 1.0);

-- 性能測試數據（100個交易對，30天數據）
-- 使用程式化生成，簡化版示例
INSERT INTO return_metrics (trading_pair, date, return_1d, roi_1d, return_7d, roi_7d) VALUES
-- PERF測試交易對 (只插入幾個示例，真實測試可能需要更多)
('PERF_001_binance_bybit', '2025-06-01', 0.001, 1.001, 0.001, 1.001),
('PERF_001_binance_bybit', '2025-06-02', 0.0015, 1.0015, 0.0025, 1.0025),
('PERF_001_binance_bybit', '2025-06-03', -0.0005, 0.9995, 0.002, 1.002),
('PERF_002_binance_bybit', '2025-06-01', -0.002, 0.998, -0.002, 0.998),
('PERF_002_binance_bybit', '2025-06-02', 0.001, 1.001, -0.001, 0.999),
('PERF_002_binance_bybit', '2025-06-03', 0.0008, 1.0008, -0.0002, 0.9998);

COMMIT;

-- 驗證數據插入結果
SELECT 'TEST數據插入完成，檢查結果：' AS status;

-- 檢查return_metrics測試數據
SELECT 
    trading_pair,
    COUNT(*) as record_count,
    MIN(date) as start_date,
    MAX(date) as end_date,
    AVG(return_1d) as avg_return,
    AVG(roi_7d) as avg_roi_7d,
    SUM(CASE WHEN return_1d > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
FROM return_metrics 
WHERE trading_pair LIKE 'TEST_%'
GROUP BY trading_pair
ORDER BY trading_pair;

-- 檢查funding_rate_history測試數據
SELECT 'Funding Rate History 測試數據：' AS info;
SELECT 
    symbol,
    exchange,
    COUNT(*) as record_count,
    MIN(timestamp_utc) as start_time,
    MAX(timestamp_utc) as end_time,
    AVG(funding_rate) as avg_funding_rate
FROM funding_rate_history 
WHERE symbol LIKE 'TEST%'
GROUP BY symbol, exchange
ORDER BY symbol, exchange; 