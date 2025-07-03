#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
币安永续合约资金费用查询工具
查询指定日期范围内收到的资金费用
"""

import requests
import hmac
import hashlib
import time
import os
from datetime import datetime, timezone
import pandas as pd
from urllib.parse import urlencode


class BinanceFundingFeeChecker:
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = 'https://fapi.binance.com'

    def _generate_signature(self, query_string):
        """生成API签名"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, endpoint, params=None):
        """发送API请求"""
        if params is None:
            params = {}

        # 添加时间戳
        params['timestamp'] = int(time.time() * 1000)

        # 生成查询字符串
        query_string = urlencode(params)

        # 生成签名
        signature = self._generate_signature(query_string)

        # 添加签名到参数
        params['signature'] = signature

        # 设置请求头
        headers = {
            'X-MBX-APIKEY': self.api_key
        }

        # 发送请求
        url = f"{self.base_url}{endpoint}"

        try:
            print(f"正在请求: {url}")
            print(f"参数: {dict((k, v) for k, v in params.items() if k != 'signature')}")

            response = requests.get(url, params=params, headers=headers, timeout=30)

            print(f"响应状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"返回数据条数: {len(result) if isinstance(result, list) else '非列表数据'}")
                if isinstance(result, list) and len(result) > 0:
                    print(f"第一条数据示例: {result[0]}")
                elif isinstance(result, dict):
                    print(f"返回字典数据: {result}")
                return result
            else:
                print(f"API请求失败: {response.status_code}")
                print(f"错误信息: {response.text}")
                print(f"请求URL: {response.url}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"网络请求异常: {str(e)}")
            return None
        except Exception as e:
            print(f"其他异常: {str(e)}")
            return None

    def test_connection(self):
        """测试API连接和密钥是否有效"""
        print("正在测试API连接...")

        # 先测试不需要签名的公共接口
        try:
            public_url = "https://fapi.binance.com/fapi/v1/ping"
            response = requests.get(public_url, timeout=10)
            if response.status_code == 200:
                print("✓ 网络连接正常，可以访问币安API")
            else:
                print("✗ 无法访问币安公共API")
                return False
        except Exception as e:
            print(f"✗ 网络连接失败: {str(e)}")
            return False

        # 测试账户信息接口（需要签名）
        try:
            endpoint = '/fapi/v2/account'
            result = self._make_request(endpoint)

            if result:
                print("✓ API密钥验证成功")
                print(f"✓ 账户总余额: {result.get('totalWalletBalance', 'N/A')} USDT")
                return True
            else:
                print("✗ API密钥验证失败")
                return False

        except Exception as e:
            print(f"✗ API密钥测试异常: {str(e)}")
            return False

    def get_funding_fee_history(self, start_date, end_date, symbol=None, limit=1000):
        """
        获取资金费用历史记录

        Args:
            start_date (str): 开始日期，格式: 'YYYY-MM-DD'
            end_date (str): 结束日期，格式: 'YYYY-MM-DD'
            symbol (str, optional): 交易对符号，如 'BTCUSDT'
            limit (int): 返回记录数量限制 (默认1000, 最大1000)

        Returns:
            list: 资金费用记录列表
        """

        # 将日期字符串转换为时间戳（毫秒）
        start_timestamp = int(datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_timestamp = int(datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').replace(
            tzinfo=timezone.utc).timestamp() * 1000)

        params = {
            'startTime': start_timestamp,
            'endTime': end_timestamp,
            'limit': limit
        }

        if symbol:
            params['symbol'] = symbol.upper()

        endpoint = '/fapi/v1/income'
        params['incomeType'] = 'FUNDING_FEE'  # 指定收入类型为资金费用

        result = self._make_request(endpoint, params)

        # 处理返回数据格式
        if result:
            # 如果返回的是包含data字段的对象
            if isinstance(result, dict) and 'data' in result:
                return result['data']
            # 如果直接返回数组
            elif isinstance(result, list):
                return result
            else:
                print(f"未知的数据格式: {result}")
                return None

        return result

    def format_funding_fee_data(self, data):
        """
        格式化资金费用数据为易读格式

        Args:
            data (list): API返回的原始数据

        Returns:
            pandas.DataFrame: 格式化后的数据框
        """
        if not data:
            return pd.DataFrame()

        # 转换为DataFrame
        df = pd.DataFrame(data)

        # 检查数据字段并适配不同的API响应格式
        if 'time' in df.columns:
            # 转换时间戳为可读日期 (保持UTC+0)
            df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True)
            # 保持UTC+0时区，不进行时区转换
            time_col = 'time'
        else:
            print("警告: 未找到时间字段")
            return pd.DataFrame()

        # 处理收入金额字段
        if 'balanceDelta' in df.columns:
            df['income'] = df['balanceDelta'].astype(float)
        elif 'income' in df.columns:
            df['income'] = df['income'].astype(float)
        else:
            print("警告: 未找到收入金额字段")
            return pd.DataFrame()

        # 选择需要的列并重命名
        try:
            df_formatted = df[[time_col, 'symbol', 'income', 'asset']].copy()
            df_formatted.columns = ['时间(UTC)', '交易对', '资金费用', '资产']
        except KeyError as e:
            print(f"字段缺失: {e}")
            print(f"可用字段: {df.columns.tolist()}")
            # 使用可用的字段
            available_cols = []
            col_mapping = {}

            if time_col in df.columns:
                available_cols.append(time_col)
                col_mapping[time_col] = '时间(UTC)'
            if 'symbol' in df.columns:
                available_cols.append('symbol')
                col_mapping['symbol'] = '交易对'
            if 'income' in df.columns:
                available_cols.append('income')
                col_mapping['income'] = '资金费用'
            elif 'balanceDelta' in df.columns:
                available_cols.append('balanceDelta')
                col_mapping['balanceDelta'] = '资金费用'
            if 'asset' in df.columns:
                available_cols.append('asset')
                col_mapping['asset'] = '资产'

            df_formatted = df[available_cols].copy()
            df_formatted.columns = [col_mapping[col] for col in available_cols]

        # 按时间排序
        df_formatted = df_formatted.sort_values('时间(UTC)', ascending=False)

        return df_formatted

    def get_funding_fee_summary(self, start_date, end_date, symbol=None):
        """
        获取资金费用统计摘要

        Args:
            start_date (str): 开始日期
            end_date (str): 结束日期
            symbol (str, optional): 交易对符号

        Returns:
            dict: 统计摘要
        """
        data = self.get_funding_fee_history(start_date, end_date, symbol)

        if not data:
            return {'error': '无法获取数据'}

        df = self.format_funding_fee_data(data)

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
        symbol_summary = df.groupby('交易对')['资金费用'].agg(['sum', 'count', 'mean']).round(6)
        symbol_summary.columns = ['总费用', '次数', '平均费用']
        summary['按交易对统计'] = symbol_summary.to_dict('index')

        return summary

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
        csv_filename = f"binance_funding_fees_{start_date}_to_{end_date}.csv"
        csv_filepath = os.path.join(output_dir, csv_filename)

        try:
            # 保存CSV文件
            df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
            print(f"✓ 数据已保存到文件: {csv_filepath}")
            return csv_filepath
        except Exception as e:
            print(f"✗ 保存CSV文件失败: {str(e)}")
            return None


def main():
    """主函数 - 使用示例"""

    # API密钥配置
    API_KEY = "scuwWKVolZwWXovCaCmmLTvkTxRiJYwIRN5ars9UFXSHf4SqAmo3TU4lAsVSpfUK"
    SECRET_KEY = "wqxlGY2NmOIWZmYJEpapNf4uabfr4QUejypw1wZrqQfFzEu1ia3rcu5SdpxVtHrF"

    # 创建查询器实例
    checker = BinanceFundingFeeChecker(API_KEY, SECRET_KEY)

    # 设置查询日期范围
    start_date = "2025-06-05"  # 开始日期
    end_date = "2025-07-03"  # 结束日期

    print("=" * 60)
    print("币安永续合约资金费用查询工具 (UTC时区)")
    print("=" * 60)
    print("注意：所有时间都显示为UTC+0时区")

    try:
        # 先测试API连接
        print("步骤1: 测试API连接和密钥")
        print("-" * 40)

        if not checker.test_connection():
            print("\n❌ API连接测试失败，请检查：")
            print("1. 网络连接是否正常")
            print("2. API密钥是否正确")
            print("3. API密钥是否已启用期货交易权限")
            print("4. 是否在币安官网正确生成了期货API密钥")
            return

        print("\n步骤2: 查询资金费用历史")
        print("-" * 40)

        # 获取资金费用历史记录
        print(f"正在查询 {start_date} 至 {end_date} 的资金费用记录...")

        raw_data = checker.get_funding_fee_history(start_date, end_date)

        if raw_data is not None:
            print(f"\n✓ API查询成功")

            if isinstance(raw_data, list):
                if len(raw_data) > 0:
                    # 格式化数据
                    df = checker.format_funding_fee_data(raw_data)

                    if not df.empty:
                        print(f"\n找到 {len(df)} 条资金费用记录:")
                        print("-" * 60)
                        print(df.to_string(index=False))

                        # 显示统计摘要
                        summary = checker.get_funding_fee_summary(start_date, end_date)
                        print("\n" + "=" * 60)
                        print("统计摘要:")
                        print("=" * 60)

                        for key, value in summary.items():
                            if key != '按交易对统计':
                                print(f"{key}: {value}")

                        print(f"\n按交易对统计:")
                        print("-" * 40)
                        for symbol, stats in summary['按交易对统计'].items():
                            print(
                                f"{symbol}: 总费用={stats['总费用']:.6f}, 次数={stats['次数']}, 平均={stats['平均费用']:.6f}")

                        # 保存到CSV文件到指定目录
                        print("\n步骤3: 保存数据到CSV文件")
                        print("-" * 40)
                        saved_file = checker.save_to_csv(df, start_date, end_date, "csv/Return")

                        if saved_file:
                            print(f"✓ 文件保存成功: {saved_file}")
                        else:
                            print("✗ 文件保存失败")

                    else:
                        print("✓ API返回了数据，但格式化后为空，可能是数据结构发生了变化")
                else:
                    print(f"✓ API查询成功，但在 {start_date} 至 {end_date} 期间没有资金费用记录")
                    print("这可能是因为：")
                    print("1. 在这个时间段内没有持有永续合约仓位")
                    print("2. 没有跨越资金费用收取时间点（每8小时一次）")
                    print("3. 日期范围设置有误")
            else:
                print(f"✗ API返回了非预期的数据格式: {type(raw_data)}")
                print(f"返回内容: {raw_data}")
        else:
            print("✗ API查询失败，返回了None")
            print("这通常表示网络请求异常或API响应解析失败")

    except Exception as e:
        print(f"发生错误: {str(e)}")

    print("\n查询完成！")


if __name__ == "__main__":
    # 安装依赖包提示
    print("请确保已安装依赖包:")
    print("pip install requests pandas")
    print()

    main()