-- 超參數調優系統測試結果驗證
-- 用於驗證測試執行後的結果正確性

-- ===========================================
-- 階段一：基礎數據驗證
-- ===========================================

-- 1. 檢查測試數據是否正確插入
SELECT 
    '=== 測試數據插入驗證 ===' as section,
    NULL as metric,
    NULL as value,
    NULL as expected,
    NULL as status

UNION ALL

SELECT 
    'funding_rates',
    'record_count',
    CAST(COUNT(*) as TEXT),
    '30 (3對×10天)',
    CASE WHEN COUNT(*) = 30 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM funding_rates 
WHERE trading_pair LIKE 'TEST_%' AND trading_pair NOT LIKE 'TEST_EXTREME_%' 
  AND trading_pair NOT LIKE 'TEST_ZERO_%' AND trading_pair NOT LIKE 'TEST_NULL_%'

UNION ALL

SELECT 
    'return_metrics',
    'record_count',
    CAST(COUNT(*) as TEXT),
    '35 (7對×5天)',
    CASE WHEN COUNT(*) = 35 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM return_metrics 
WHERE trading_pair LIKE 'TEST_%';

-- ===========================================
-- 階段二：因子策略生成驗證
-- ===========================================

-- 2. 檢查策略是否成功生成
SELECT 
    '=== 因子策略生成驗證 ===' as section,
    NULL, NULL, NULL, NULL

UNION ALL

SELECT 
    'strategy_ranking',
    'strategy_count',
    CAST(COUNT(DISTINCT strategy_name) as TEXT),
    '至少1個',
    CASE WHEN COUNT(DISTINCT strategy_name) >= 1 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM strategy_ranking 
WHERE strategy_name LIKE 'TEST_%'

UNION ALL

SELECT 
    'strategy_ranking',
    'total_records',
    CAST(COUNT(*) as TEXT),
    '取決於策略數×日期數×交易對數',
    CASE WHEN COUNT(*) > 0 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM strategy_ranking 
WHERE strategy_name LIKE 'TEST_%';

-- 3. 驗證排名邏輯（TEST_A應該排名最高）
SELECT 
    '=== 排名邏輯驗證 ===' as section,
    NULL, NULL, NULL, NULL

UNION ALL

SELECT 
    'ranking_logic',
    'TEST_A_vs_TEST_C',
    CASE 
        WHEN a.final_ranking_score > c.final_ranking_score THEN 'TEST_A > TEST_C ✅'
        ELSE 'TEST_A <= TEST_C ❌'
    END,
    'TEST_A 應該 > TEST_C',
    CASE 
        WHEN a.final_ranking_score > c.final_ranking_score THEN '✅ PASS'
        ELSE '❌ FAIL'
    END
FROM 
    (SELECT final_ranking_score FROM strategy_ranking 
     WHERE strategy_name LIKE 'TEST_%' AND trading_pair = 'TEST_A_binance_bybit' 
     AND date = '2025-06-05' LIMIT 1) a
CROSS JOIN
    (SELECT final_ranking_score FROM strategy_ranking 
     WHERE strategy_name LIKE 'TEST_%' AND trading_pair = 'TEST_C_binance_bybit' 
     AND date = '2025-06-05' LIMIT 1) c;

-- 4. 檢查TEST數據的詳細排名
SELECT 
    '=== 詳細排名檢查 ===' as section,
    trading_pair,
    CAST(final_ranking_score as TEXT),
    CAST(rank_position as TEXT),
    CASE 
        WHEN trading_pair = 'TEST_A_binance_bybit' AND rank_position <= 3 THEN '✅ GOOD'
        WHEN trading_pair = 'TEST_C_binance_bybit' AND rank_position > 5 THEN '✅ GOOD'
        ELSE '⚠️ CHECK'
    END
FROM strategy_ranking 
WHERE strategy_name LIKE 'TEST_%' 
  AND date = '2025-06-05'
  AND trading_pair LIKE 'TEST_%'
  AND trading_pair NOT LIKE 'TEST_EXTREME_%'
  AND trading_pair NOT LIKE 'TEST_ZERO_%'
  AND trading_pair NOT LIKE 'TEST_NULL_%'
ORDER BY rank_position;

-- ===========================================
-- 階段三：回測引擎驗證
-- ===========================================

-- 5. 檢查回測是否成功執行
SELECT 
    '=== 回測執行驗證 ===' as section,
    NULL, NULL, NULL, NULL

UNION ALL

SELECT 
    'backtest_results',
    'backtest_count',
    CAST(COUNT(*) as TEXT),
    '至少1個',
    CASE WHEN COUNT(*) >= 1 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM backtest_results 
WHERE strategy_name LIKE 'TEST_%'

UNION ALL

SELECT 
    'backtest_trades',
    'trade_count',
    CAST(COUNT(*) as TEXT),
    '> 0',
    CASE WHEN COUNT(*) > 0 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM backtest_trades 
WHERE backtest_id LIKE 'TEST_%';

-- 6. 檢查回測結果摘要
SELECT 
    '=== 回測結果詳情 ===' as section,
    backtest_id,
    CAST(final_capital as TEXT),
    CAST(total_return_pct as TEXT) || '%',
    CASE 
        WHEN final_capital >= initial_capital THEN '✅ NON-NEGATIVE'
        ELSE '⚠️ NEGATIVE'
    END
FROM backtest_results 
WHERE strategy_name LIKE 'TEST_%'
ORDER BY created_at DESC;

-- 7. 檢查交易邏輯一致性
SELECT 
    '=== 交易邏輯驗證 ===' as section,
    NULL, NULL, NULL, NULL

UNION ALL

WITH entry_check AS (
    SELECT 
        bt.backtest_id,
        bt.trading_pair,
        bt.date as entry_date,
        sr.rank_position,
        CASE WHEN sr.rank_position <= 3 THEN 'VALID' ELSE 'INVALID' END as status
    FROM backtest_trades bt
    JOIN strategy_ranking sr ON 
        bt.trading_pair = sr.trading_pair 
        AND DATE(bt.date) = sr.date
        AND sr.strategy_name LIKE 'TEST_%'
    WHERE bt.event_type = 'enter_position'
      AND bt.backtest_id LIKE 'TEST_%'
)
SELECT 
    'entry_logic',
    'invalid_entries',
    CAST(COUNT(*) as TEXT),
    '0',
    CASE WHEN COUNT(*) = 0 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM entry_check
WHERE status = 'INVALID';

-- ===========================================
-- 階段四：數據一致性驗證
-- ===========================================

-- 8. 資金平衡檢查
SELECT 
    '=== 資金平衡驗證 ===' as section,
    NULL, NULL, NULL, NULL

UNION ALL

WITH balance_check AS (
    SELECT 
        backtest_id,
        date,
        ABS((cash_balance_after + position_balance_after) - total_balance_after) as diff
    FROM backtest_trades 
    WHERE backtest_id LIKE 'TEST_%'
      AND total_balance_after IS NOT NULL
)
SELECT 
    'balance_consistency',
    'large_differences',
    CAST(COUNT(*) as TEXT),
    '0',
    CASE WHEN COUNT(*) = 0 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM balance_check
WHERE diff > 0.01;

-- 9. 交易記錄完整性
SELECT 
    '=== 交易記錄完整性 ===' as section,
    event_type,
    CAST(COUNT(*) as TEXT),
    '檢查數量',
    '✅ INFO'
FROM backtest_trades 
WHERE backtest_id LIKE 'TEST_%'
GROUP BY event_type
ORDER BY event_type;

-- ===========================================
-- 階段五：性能指標驗證
-- ===========================================

-- 10. 檢查淨值曲線數據
SELECT 
    '=== 淨值曲線驗證 ===' as section,
    NULL, NULL, NULL, NULL

UNION ALL

SELECT 
    'equity_curve',
    'record_count',
    CAST(COUNT(*) as TEXT),
    '> 0',
    CASE WHEN COUNT(*) > 0 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM backtest_equity_curve 
WHERE backtest_id LIKE 'TEST_%';

-- ===========================================
-- 綜合結果摘要
-- ===========================================

-- 11. 測試摘要統計
SELECT 
    '=== 測試摘要統計 ===' as section,
    NULL, NULL, NULL, NULL

UNION ALL

SELECT 
    'summary',
    'total_test_pairs',
    CAST(COUNT(DISTINCT trading_pair) as TEXT),
    '7個',
    CASE WHEN COUNT(DISTINCT trading_pair) = 7 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM return_metrics 
WHERE trading_pair LIKE 'TEST_%'

UNION ALL

SELECT 
    'summary',
    'strategies_generated',
    CAST(COUNT(DISTINCT strategy_name) as TEXT),
    '≥ 1個',
    CASE WHEN COUNT(DISTINCT strategy_name) >= 1 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM strategy_ranking 
WHERE strategy_name LIKE 'TEST_%'

UNION ALL

SELECT 
    'summary',
    'backtests_completed',
    CAST(COUNT(*) as TEXT),
    '≥ 1個',
    CASE WHEN COUNT(*) >= 1 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM backtest_results 
WHERE strategy_name LIKE 'TEST_%';

-- ===========================================
-- 手動檢查建議
-- ===========================================

-- 提醒手動檢查項目
SELECT 
    '=== 手動檢查項目 ===' as section,
    '請手動確認以下項目：' as item,
    '' as detail,
    '' as expected,
    '' as action

UNION ALL

SELECT 
    'manual_check',
    '1. 淨值曲線圖片',
    '檢查 data/picture/backtest/ 目錄',
    '應該生成PNG圖片文件',
    '目視檢查圖表'

UNION ALL

SELECT 
    'manual_check',
    '2. 日誌文件內容',
    '檢查執行過程日誌',
    '無ERROR級別錯誤',
    '查看日誌文件'

UNION ALL

SELECT 
    'manual_check',
    '3. 配置參數',
    '驗證使用的配置正確',
    '符合測試配置',
    '對照配置文件'

UNION ALL

SELECT 
    'manual_check',
    '4. 執行時間',
    '記錄測試執行時間',
    '合理範圍內',
    '性能評估';

-- ===========================================
-- 清理指令提醒
-- ===========================================

SELECT 
    '=== 測試完成後清理 ===' as section,
    '執行以下SQL清理測試數據：' as cleanup_sql,
    '' as detail,
    '' as note,
    '' as action

UNION ALL

SELECT 
    'cleanup',
    'DELETE FROM funding_rates WHERE trading_pair LIKE ''TEST_%'';',
    '',
    '',
    ''

UNION ALL

SELECT 
    'cleanup',
    'DELETE FROM return_metrics WHERE trading_pair LIKE ''TEST_%'';',
    '',
    '',
    ''

UNION ALL

SELECT 
    'cleanup',
    'DELETE FROM strategy_ranking WHERE strategy_name LIKE ''TEST_%'';',
    '',
    '',
    ''

UNION ALL

SELECT 
    'cleanup',
    'DELETE FROM backtest_results WHERE strategy_name LIKE ''TEST_%'';',
    '',
    '',
    ''

UNION ALL

SELECT 
    'cleanup',
    'DELETE FROM backtest_trades WHERE backtest_id LIKE ''TEST_%'';',
    '',
    '',
    ''

UNION ALL

SELECT 
    'cleanup',
    'DELETE FROM backtest_equity_curve WHERE backtest_id LIKE ''TEST_%'';',
    '',
    '',
    ''; 