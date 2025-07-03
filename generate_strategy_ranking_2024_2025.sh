#!/bin/bash

# 大規模生成 strategy_ranking 數據腳本
# 時間範圍: 2024-04-03 到 2025-06-20 (443天)

cd factor_strategies

echo "🚀 開始生成 cerebrum_core 策略排名數據..."
echo "📅 完整時間範圍: 2024-04-03 到 2025-06-20 (約443天)"
echo ""

# Q2 2024: 2024-04-03 到 2024-06-30
echo "📊 第1季: 2024-04-03 到 2024-06-30"
python run_factor_strategies.py --start_date 2024-04-03 --end_date 2024-06-30 --strategy cerebrum_core
echo "✅ Q2 2024 完成"
echo ""

# Q3 2024: 2024-07-01 到 2024-09-30  
echo "📊 第2季: 2024-07-01 到 2024-09-30"
python run_factor_strategies.py --start_date 2024-07-01 --end_date 2024-09-30 --strategy cerebrum_core
echo "✅ Q3 2024 完成"
echo ""

# Q4 2024: 2024-10-01 到 2024-12-31
echo "📊 第3季: 2024-10-01 到 2024-12-31"
python run_factor_strategies.py --start_date 2024-10-01 --end_date 2024-12-31 --strategy cerebrum_core
echo "✅ Q4 2024 完成"
echo ""

# Q1 2025: 2025-01-01 到 2025-03-31
echo "📊 第4季: 2025-01-01 到 2025-03-31"
python run_factor_strategies.py --start_date 2025-01-01 --end_date 2025-03-31 --strategy cerebrum_core
echo "✅ Q1 2025 完成"
echo ""

# Q2 2025: 2025-04-01 到 2025-06-20
echo "📊 第5季: 2025-04-01 到 2025-06-20"
python run_factor_strategies.py --start_date 2025-04-01 --end_date 2025-06-20 --strategy cerebrum_core
echo "✅ Q2 2025 完成"
echo ""

echo "🎉 所有批次完成！"
echo "📊 最終統計:"
cd ..
sqlite3 data/funding_rate.db "SELECT strategy_name, COUNT(DISTINCT date) as days, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as total_records FROM strategy_ranking WHERE strategy_name='cerebrum_core' GROUP BY strategy_name;" 