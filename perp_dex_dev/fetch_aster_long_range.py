#!/usr/bin/env python3
"""
Aster 长时间范围数据获取脚本
自动分段获取超过 7 天的数据并合并
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
import csv

def fetch_aster_long_range(symbol, start_date, end_date, output_file=None):
    """
    分段获取 Aster 数据并合并

    Args:
        symbol: 交易对（如 ETHUSDT）
        start_date: 开始日期字符串 (YYYY-MM-DD)
        end_date: 结束日期字符串 (YYYY-MM-DD)
        output_file: 输出文件路径（可选）
    """
    # 解析日期
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # 计算总天数
    total_days = (end_dt - start_dt).days
    print(f"总时间范围: {total_days} 天")

    if total_days <= 7:
        print("时间范围不超过 7 天，直接获取...")
        cmd = [
            "python", "-m", "src.main", "aster",
            "--symbol", symbol,
            "--start-date", start_date,
            "--end-date", end_date
        ]
        if output_file:
            cmd.extend(["--output", output_file])
        subprocess.run(cmd)
        return

    # 分段获取
    print(f"需要分 {(total_days // 7) + 1} 段获取...\n")

    temp_files = []
    all_records = []

    current_start = start_dt
    segment = 1

    while current_start < end_dt:
        # 计算这一段的结束日期（最多 7 天）
        current_end = min(current_start + timedelta(days=7), end_dt)

        start_str = current_start.strftime("%Y-%m-%d")
        end_str = current_end.strftime("%Y-%m-%d")

        print(f"第 {segment} 段: {start_str} 到 {end_str}")

        # 临时文件名
        temp_file = f"data/.temp_aster_{symbol}_{segment}.csv"
        temp_files.append(temp_file)

        # 执行命令
        cmd = [
            "python", "-m", "src.main", "aster",
            "--symbol", symbol,
            "--start-date", start_str,
            "--end-date", end_str,
            "--output", temp_file
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"错误：第 {segment} 段获取失败")
            print(result.stderr)
            # 清理临时文件
            for f in temp_files:
                Path(f).unlink(missing_ok=True)
            return

        print(f"第 {segment} 段完成\n")

        # 移动到下一段
        current_start = current_end
        segment += 1

    # 合并所有数据
    print("合并数据...")

    header = None
    for i, temp_file in enumerate(temp_files):
        with open(temp_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            # 保存表头（只需要一次）
            if header is None:
                header = reader.fieldnames

            # 读取所有记录
            for row in reader:
                all_records.append(row)

    # 按时间戳排序（确保数据连续）
    all_records.sort(key=lambda x: int(x['timestamp']))

    # 生成输出文件名
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"data/aster_{symbol}_{start_date.replace('-', '')}_to_{end_date.replace('-', '')}_{timestamp}.csv"

    # 写入合并后的数据
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(all_records)

    # 清理临时文件
    for temp_file in temp_files:
        Path(temp_file).unlink(missing_ok=True)

    print(f"\n✅ 完成！")
    print(f"总记录数: {len(all_records)}")
    print(f"输出文件: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("使用方法:")
        print("  python fetch_aster_long_range.py <交易对> <开始日期> <结束日期> [输出文件]")
        print("\n示例:")
        print("  python fetch_aster_long_range.py ETHUSDT 2025-01-01 2025-01-31")
        print("  python fetch_aster_long_range.py ETHUSDT 2025-01-01 2025-01-31 data/eth_jan.csv")
        sys.exit(1)

    symbol = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    output_file = sys.argv[4] if len(sys.argv) > 4 else None

    fetch_aster_long_range(symbol, start_date, end_date, output_file)
