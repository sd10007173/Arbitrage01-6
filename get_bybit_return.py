#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit永续合约资金费用查询工具 - 基于你的工作代码
查询指定日期范围内收到的资金费用
"""

import hashlib
import hmac
import time
import os
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd


class BybitFundingFeeChecker:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = 'https://api.bybit.com'

    def generate_signature(self, params: dict) -> str:
        """
        生成 Bybit API 签名 - 基于你的代码
        """
        sorted_params = sorted(params.items())
        query_string = '&'.join(f"{key}={value}" for key, value in sorted_params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def get_funding_fee_single_batch(self, start_time=None, end_time=None, limit=50):
        """
        获取单批资金费用记录 - 基于你的get_funding_fee函数
        """
        endpoint = "/v5/account/transaction-log"
        url = self.base_url + endpoint

        timestamp = int(time.time() * 1000)

        params = {
            "api_key": self.api_key,
            "accountType": "UNIFIED",
            "type": "SETTLEMENT",  # 过滤为资金费用类型
            "limit": str(limit),
            "timestamp": str(timestamp),
        }

        # 添加时间范围参数（如果提供）
        if start_time:
            params["startTime"] = str(start_time)
        if end_time:
            params["endTime"] = str(end_time)

        # 生成签名
        sign = self.generate_signature(params)
        params["sign"] = sign

        print(f"正在查询资金费用记录...")
        print(f"参数: {dict((k, v) for k, v in params.items() if k not in ['sign', 'api_key'])}")

        # 发送请求
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            print(f"API响应: retCode={data.get('retCode')}, retMsg={data.get('retMsg')}")

            if data["retCode"] == 0:
                records = data["result"]["list"]
                print(f"找到 {len(records)} 条记录")
                return records
            else:
                print(f"API错误: {data['retMsg']}")
                return []
        else:
            print(f"HTTP错误: {response.status_code}")
            return []

    def get_funding_fee_batch(self, start_date, end_date, limit=50):
        """
        批量获取资金费用记录（处理7天限制）
        """
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        all_records = []
        current_dt = start_dt

        print(f"查询时间范围: {start_date} 至 {end_date}")
        print("=" * 50)

        while current_dt <= end_dt:
            # 计算批次结束日期（最多6天，给7天限制留余量）
            batch_end_dt = min(current_dt + timedelta(days=6), end_dt)

            # 转换为时间戳（毫秒）
            start_timestamp = int(current_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            end_timestamp = int((batch_end_dt + timedelta(days=1) - timedelta(seconds=1)).replace(
                tzinfo=timezone.utc).timestamp() * 1000)

            batch_start = current_dt.strftime('%Y-%m-%d')
            batch_end = batch_end_dt.strftime('%Y-%m-%d')

            print(f"\n批次查询: {batch_start} 至 {batch_end}")

            # 查询这个批次的数据
            batch_records = self.get_funding_fee_single_batch(
                start_time=start_timestamp,
                end_time=end_timestamp,
                limit=limit
            )

            if batch_records:
                all_records.extend(batch_records)
                print(f"本批次找到 {len(batch_records)} 条记录")
            else:
                print("本批次没有找到记录")

            # 移动到下一个批次
            current_dt = batch_end_dt + timedelta(days=1)

            # 添加延迟避免请求过于频繁
            if current_dt <= end_dt:
                print("等待1秒...")
                time.sleep(1)

        print(f"\n总共找到 {len(all_records)} 条资金费用记录")
        return all_records

    def format_funding_fee_data(self, records):
        """
        格式化资金费用数据
        """
        if not records:
            return pd.DataFrame()

        # 转换为DataFrame
        df = pd.DataFrame(records)

        # 转换时间戳为可读日期 (保持UTC+0)
        df['transactionTime'] = pd.to_datetime(df['transactionTime'], unit='ms', utc=True)
        # 保持UTC+0时区，不进行时区转换

        # 转换数值字段
        df['funding'] = df['funding'].astype(float)
        if 'cashBalance' in df.columns:
            df['cashBalance'] = df['cashBalance'].astype(float)

        # 选择和重命名列
        columns_to_keep = ['transactionTime', 'symbol', 'side', 'qty', 'funding', 'feeRate', 'currency']
        available_columns = [col for col in columns_to_keep if col in df.columns]

        df_formatted = df[available_columns].copy()

        # 重命名列为中文
        column_rename = {
            'transactionTime': '交易时间(UTC)',
            'symbol': '交易对',
            'side': '方向',
            'qty': '数量',
            'funding': '资金费用',
            'feeRate': '费率',
            'currency': '货币'
        }

        df_formatted = df_formatted.rename(
            columns={k: v for k, v in column_rename.items() if k in df_formatted.columns})

        # 按时间排序
        df_formatted = df_formatted.sort_values('交易时间(UTC)', ascending=False)

        return df_formatted

    def test_connection(self):
        """
        测试连接
        """
        print("正在测试API连接...")

        # 测试基本的资金费用查询（不带时间范围）
        records = self.get_funding_fee_single_batch(limit=5)

        if records:
            print("✓ API连接成功")
            print(f"✓ 获取到 {len(records)} 条最近的资金费用记录")
            if len(records) > 0:
                latest_record = records[0]
                print(
                    f"✓ 最新记录: {latest_record.get('symbol')} - {latest_record.get('funding')} {latest_record.get('currency')}")
            return True
        else:
            print("✗ API连接失败")
            return False


    def ensure_output_directory(self, output_dir="csv/Return"):
        """
        确保输出目录存在，如果不存在则创建

        Args:
            output_dir (str): 输出目录路径

        Returns:
            str: 输出目录路径
        """
        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                print(f"✓ 已创建输出目录: {output_dir}")
            else:
                print(f"✓ 输出目录已存在: {output_dir}")
            return output_dir
        except Exception as e:
            print(f"✗ 创建输出目录失败: {str(e)}")
            print("将使用当前目录作为输出路径")
            return "."

    def save_to_csv(self, df, start_date, end_date, output_dir="csv/Return"):
        """
        保存数据到CSV文件

        Args:
            df (pandas.DataFrame): 要保存的数据框
            start_date (str): 开始日期
            end_date (str): 结束日期
            output_dir (str): 输出目录

        Returns:
            str: 保存的文件路径
        """
        # 确保输出目录存在
        output_dir = self.ensure_output_directory(output_dir)

        # 生成文件名
        csv_filename = f"bybit_funding_fees_{start_date}_to_{end_date}.csv"
        csv_filepath = os.path.join(output_dir, csv_filename)

        try:
            # 保存CSV文件
            df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
            print(f"✓ 数据已保存到文件: {csv_filepath}")
            return csv_filepath
        except Exception as e:
            print(f"✗ 保存CSV文件失败: {str(e)}")
            return None

    def get_funding_fee_summary(self, df, start_date, end_date):
        """
        获取资金费用统计摘要

        Args:
            df (pandas.DataFrame): 格式化后的数据框
            start_date (str): 开始日期
            end_date (str): 结束日期

        Returns:
            dict: 统计摘要
        """
        if df.empty:
            return {'message': '指定期间内无资金费用记录'}

        summary = {
            '查询期间': f"{start_date} 至 {end_date}",
            '总记录数': len(df),
            '总资金费用': df['资金费用'].sum(),
            '平均资金费用': df['资金费用'].mean(),
            '最大单次费用': df['资金费用'].max(),
            '最小单次费用': df['资金费用'].min(),
            '涉及交易对': df['交易对'].nunique(),
            '交易对列表': df['交易对'].unique().tolist()
        }

        # 按交易对统计
        if len(df) > 0:
            symbol_summary = df.groupby('交易对')['资金费用'].agg(['sum', 'count', 'mean']).round(6)
            symbol_summary.columns = ['总费用', '次数', '平均费用']
            summary['按交易对统计'] = symbol_summary.to_dict('index')

        return summary


def main():
    """主函数"""

    # API密钥配置
    API_KEY = "zFeh1WkAvXVecEvEY8"
    API_SECRET = "hWA7mgDqRkH366WhZjCIEDFx4Kp6YtTr8rpJ"

    # 创建查询器实例
    checker = BybitFundingFeeChecker(API_KEY, API_SECRET)

    print("=" * 60)
    print("Bybit永续合约资金费用查询工具 (UTC时区)")
    print("=" * 60)
    print("注意：所有时间都显示为UTC+0时区")

    try:
        # 测试连接
        print("步骤1: 测试API连接")
        print("-" * 40)

        if not checker.test_connection():
            print("\n❌ API连接测试失败")
            return

        print("\n步骤2: 查询历史资金费用")
        print("-" * 40)

        # 设置查询日期范围
        start_date = "2025-06-05"  # 开始日期
        end_date = "2025-07-02"  # 结束日期

        # 获取资金费用历史记录
        raw_data = checker.get_funding_fee_batch(start_date, end_date, limit=100)

        if raw_data:
            print("\n步骤3: 处理和导出数据")
            print("-" * 40)

            # 格式化数据
            df = checker.format_funding_fee_data(raw_data)

            if not df.empty:
                print(f"\n找到 {len(df)} 条资金费用记录:")
                print("-" * 60)

                # 显示前10条记录
                print("前10条记录预览:")
                print(df.head(10).to_string(index=False))

                # 获取并显示统计摘要
                summary = checker.get_funding_fee_summary(df, start_date, end_date)
                print(f"\n" + "=" * 60)
                print("统计摘要:")
                print("=" * 60)

                for key, value in summary.items():
                    if key != '按交易对统计':
                        print(f"{key}: {value}")

                # 按交易对统计
                if '按交易对统计' in summary:
                    print(f"\n按交易对统计:")
                    print("-" * 40)
                    for symbol, stats in summary['按交易对统计'].items():
                        print(
                            f"{symbol}: 总费用={stats['总费用']:.6f}, 次数={stats['次数']}, 平均={stats['平均费用']:.6f}")

                # 保存到CSV文件到指定目录
                print("\n步骤4: 保存数据到CSV文件")
                print("-" * 40)
                saved_file = checker.save_to_csv(df, start_date, end_date, "csv/Return")

                if saved_file:
                    print(f"✓ 文件保存成功: {saved_file}")
                else:
                    print("✗ 文件保存失败")

            else:
                print("数据格式化后为空")
        else:
            print(f"在 {start_date} 至 {end_date} 期间没有找到资金费用记录")
            print("这可能是因为：")
            print("1. 在这个时间段内没有持有永续合约仓位")
            print("2. 没有跨越资金费用收取时间点")
            print("3. 日期范围设置有误")

    except Exception as e:
        print(f"发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n查询完成！")


if __name__ == "__main__":
    print("请确保已安装依赖包:")
    print("pip install requests pandas")
    print()

    main()