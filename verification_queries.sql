-- 驗證查詢 SQL 腳本
-- 用於驗證全歷史圖片功能是否正常工作

-- 1. 檢查測試數據是否正確插入
SELECT '=== 測試數據統計 ===' as section;

SELECT 
    'funding_rate_history' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT symbol) as unique_symbols,
    COUNT(DISTINCT exchange) as unique_exchanges,
    MIN(DATE(timestamp_utc)) as earliest_date,
    MAX(DATE(timestamp_utc)) as latest_date
FROM funding_rate_history
UNION ALL
SELECT 
    'funding_rate_diff' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT symbol) as unique_symbols,
    COUNT(DISTINCT exchange_a||'_'||exchange_b) as unique_exchange_pairs,
    MIN(DATE(timestamp_utc)) as earliest_date,
    MAX(DATE(timestamp_utc)) as latest_date
FROM funding_rate_diff
UNION ALL
SELECT 
    'return_metrics' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT trading_pair) as unique_trading_pairs,
    0 as unused_column,
    MIN(date) as earliest_date,
    MAX(date) as latest_date
FROM return_metrics
UNION ALL
SELECT 
    'strategy_ranking' as table_name,
    COUNT(*) as total_records,
    COUNT(DISTINCT trading_pair) as unique_trading_pairs,
    COUNT(DISTINCT strategy_name) as unique_strategies,
    MIN(date) as earliest_date,
    MAX(date) as latest_date
FROM strategy_ranking;

-- 2. 檢查return_metrics的時間序列數據
SELECT '=== Return Metrics 時間序列 ===' as section;

SELECT 
    trading_pair,
    date,
    return_1d,
    roi_1d,
    return_all,
    roi_all
FROM return_metrics
ORDER BY trading_pair, date;

-- 3. 檢查策略排名數據
SELECT '=== 策略排名數據 ===' as section;

SELECT 
    strategy_name,
    trading_pair,
    date,
    rank_position,
    final_ranking_score
FROM strategy_ranking
WHERE strategy_name = 'original'
ORDER BY rank_position;

-- 4. 驗證全歷史數據範圍
SELECT '=== 全歷史數據範圍驗證 ===' as section;

SELECT 
    'return_metrics' as table_name,
    MIN(date) as min_date,
    MAX(date) as max_date,
    COUNT(DISTINCT date) as total_days,
    JULIANDAY(MAX(date)) - JULIANDAY(MIN(date)) + 1 as expected_days
FROM return_metrics;

-- 5. 預期生成的圖片文件名
SELECT '=== 預期生成的圖片文件名 ===' as section;

SELECT 
    trading_pair,
    trading_pair || '_full_history_return_pic.png' as full_history_filename,
    trading_pair || '_2025-07-10-2025-07-15_return_pic.png' as period_filename
FROM (
    SELECT DISTINCT trading_pair 
    FROM return_metrics
    ORDER BY trading_pair
);

-- 6. 檢查數據完整性
SELECT '=== 數據完整性檢查 ===' as section;

-- 檢查return_metrics是否有空值
SELECT 
    trading_pair,
    date,
    CASE 
        WHEN return_1d IS NULL THEN 'return_1d為空'
        WHEN roi_1d IS NULL THEN 'roi_1d為空'
        WHEN return_all IS NULL THEN 'return_all為空'
        WHEN roi_all IS NULL THEN 'roi_all為空'
        ELSE '數據完整'
    END as data_status
FROM return_metrics
WHERE return_1d IS NULL OR roi_1d IS NULL OR return_all IS NULL OR roi_all IS NULL;

-- 如果上面的查詢沒有結果，說明數據完整
SELECT 
    COUNT(*) as total_records,
    COUNT(CASE WHEN return_1d IS NOT NULL AND roi_1d IS NOT NULL AND return_all IS NOT NULL AND roi_all IS NOT NULL THEN 1 END) as complete_records,
    CASE 
        WHEN COUNT(*) = COUNT(CASE WHEN return_1d IS NOT NULL AND roi_1d IS NOT NULL AND return_all IS NOT NULL AND roi_all IS NOT NULL THEN 1 END) 
        THEN '✅ 所有數據完整'
        ELSE '❌ 存在不完整數據'
    END as integrity_status
FROM return_metrics; 