#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易對收益圖表繪製工具 (V2版本)

功能：
1. 從數據庫讀取 return_metrics 數據
2. 為每個交易對生成包含兩個子圖的圖表：
   - 累積收益圖（線性累加）
   - 每日收益圖
3. 保存到 data/picture/ 目錄
4. V2版本改進：X軸每個月都標記（而非每2個月）
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from database_operations import DatabaseManager
import os
from datetime import datetime
import argparse

# 設置中文字體支持（如果需要）
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False

class ReturnMetricsVisualizer:
    
    def __init__(self, output_dir="data/picture"):
        self.db = DatabaseManager()
        self.output_dir = output_dir
        self.ensure_output_directory()
    
    def ensure_output_directory(self):
        """確保輸出目錄存在"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"✅ 創建輸出目錄: {self.output_dir}")
        else:
            print(f"📁 輸出目錄已存在: {self.output_dir}")
    
    def load_return_metrics_data(self, trading_pair=None):
        """
        從數據庫讀取 return_metrics 數據
        
        Args:
            trading_pair: 指定交易對，None則讀取所有
            
        Returns:
            DataFrame: 包含收益數據的DataFrame
        """
        print("📊 正在從數據庫讀取 return_metrics 數據...")
        
        if trading_pair:
            df = self.db.get_return_metrics(trading_pair=trading_pair)
            print(f"🔍 讀取指定交易對 {trading_pair} 的數據: {len(df)} 條記錄")
        else:
            df = self.db.get_return_metrics()
            print(f"📋 讀取所有交易對數據: {len(df)} 條記錄")
        
        if df.empty:
            print("⚠️ 沒有找到任何 return_metrics 數據")
            return df
        
        # 轉換日期格式
        df['date'] = pd.to_datetime(df['date'])
        
        # 過濾掉 return_1d 為空的記錄
        initial_count = len(df)
        df = df.dropna(subset=['return_1d'])
        filtered_count = len(df)
        
        if initial_count > filtered_count:
            print(f"🧹 過濾掉 {initial_count - filtered_count} 條 return_1d 為空的記錄")
        
        # 按交易對和日期排序
        df = df.sort_values(['trading_pair', 'date'])
        
        return df
    
    def create_return_charts(self, trading_pair, data):
        """
        為單個交易對創建包含兩個子圖的圖表
        
        Args:
            trading_pair: 交易對名稱
            data: 該交易對的收益數據
        """
        if data.empty:
            print(f"⚠️ {trading_pair} 沒有有效數據，跳過")
            return
        
        # 確保數據按日期排序
        data = data.sort_values('date')
        
        # 計算累積收益（線性累加）
        data = data.copy()
        data['cumulative_return'] = data['return_1d'].cumsum()
        
        # 創建包含兩個子圖的figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # 子圖1：累積收益
        ax1.plot(data['date'], data['cumulative_return'], 
                linewidth=2, color='#2E86AB', alpha=0.8)
        ax1.set_title(f'{trading_pair} - Cumulative Return', 
                     fontsize=14, fontweight='bold', pad=20)
        ax1.set_ylabel('Cumulative Return (%)', fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5)
        
        # 格式化x軸日期 - 每個月標記
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        
        # 子圖2：每日收益
        colors = ['green' if x >= 0 else 'red' for x in data['return_1d']]
        ax2.bar(data['date'], data['return_1d'], 
               color=colors, alpha=0.6, width=1)
        ax2.set_title(f'{trading_pair} - Daily Return', 
                     fontsize=14, fontweight='bold', pad=20)
        ax2.set_ylabel('Daily Return (%)', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.8, linewidth=1)
        
        # 格式化x軸日期 - 每個月標記
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        
        # 旋轉日期標籤
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        # 添加統計信息到圖表
        total_return = data['cumulative_return'].iloc[-1]
        avg_daily_return = data['return_1d'].mean()
        std_daily_return = data['return_1d'].std()
        
        stats_text = f'Total Return: {total_return:.2f}%\n'
        stats_text += f'Avg Daily: {avg_daily_return:.3f}%\n'
        stats_text += f'Std Daily: {std_daily_return:.3f}%'
        
        ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', 
                facecolor='wheat', alpha=0.8), fontsize=10)
        
        # 調整布局
        plt.tight_layout()
        
        # 生成文件名
        start_date = data['date'].min().strftime('%Y-%m-%d')
        end_date = data['date'].max().strftime('%Y-%m-%d')
        filename = f"{trading_pair}_{start_date}-{end_date}_return_pic.png"
        filepath = os.path.join(self.output_dir, filename)
        
        # 保存圖片
        plt.savefig(filepath, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"✅ 已生成圖表: {filename}")
        print(f"   📈 總收益: {total_return:.2f}%")
        print(f"   📊 數據點: {len(data)} 天")
        print(f"   📅 時間範圍: {start_date} 到 {end_date}")
    
    def process_all_trading_pairs(self, specific_pair=None):
        """
        處理所有交易對或指定交易對
        
        Args:
            specific_pair: 指定的交易對，None則處理所有
        """
        print("🚀 開始生成交易對收益圖表... (V2版本 - 每月標記)")
        print("=" * 60)
        
        # 讀取數據
        df = self.load_return_metrics_data(trading_pair=specific_pair)
        
        if df.empty:
            print("❌ 沒有可用的數據")
            return
        
        # 獲取所有交易對
        if specific_pair:
            trading_pairs = [specific_pair]
        else:
            trading_pairs = df['trading_pair'].unique()
        
        print(f"📋 找到 {len(trading_pairs)} 個交易對需要處理")
        print("=" * 60)
        
        # 處理每個交易對
        success_count = 0
        for i, trading_pair in enumerate(trading_pairs, 1):
            print(f"\n[{i}/{len(trading_pairs)}] 處理交易對: {trading_pair}")
            
            # 獲取該交易對的數據
            pair_data = df[df['trading_pair'] == trading_pair].copy()
            
            try:
                self.create_return_charts(trading_pair, pair_data)
                success_count += 1
            except Exception as e:
                print(f"❌ 處理 {trading_pair} 時發生錯誤: {e}")
        
        print("\n" + "=" * 60)
        print(f"🎉 處理完成！")
        print(f"✅ 成功生成: {success_count} 個圖表")
        print(f"📁 輸出目錄: {self.output_dir}")
        
        if success_count < len(trading_pairs):
            print(f"⚠️ 失敗: {len(trading_pairs) - success_count} 個")

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='生成交易對收益圖表 (V2版本)')
    parser.add_argument('--trading-pair', type=str, 
                       help='指定要處理的交易對，例如：BTCUSDT_binance_bybit')
    parser.add_argument('--output-dir', type=str, default='data/picture',
                       help='輸出目錄，默認為 data/picture')
    
    args = parser.parse_args()
    
    # 創建可視化器
    visualizer = ReturnMetricsVisualizer(output_dir=args.output_dir)
    
    # 處理交易對
    visualizer.process_all_trading_pairs(specific_pair=args.trading_pair)

if __name__ == "__main__":
    main()