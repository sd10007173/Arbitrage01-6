#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import re

def scan_overall_stat_files(directory):
    """
    掃描指定目錄，找出所有 overall_stat_YYYY_MM_DD_to_YYYY_MM_DD 格式的檔案
    """
    files = []
    pattern = r'overall_stat_\d{4}_\d{2}_\d{2}_to_\d{4}_\d{2}_\d{2}\.csv'
    
    if not os.path.exists(directory):
        print(f"目錄不存在: {directory}")
        return files
    
    for filename in os.listdir(directory):
        if re.match(pattern, filename):
            files.append(filename)
    
    return sorted(files)

def display_files_menu(files):
    """
    顯示檔案選單讓用戶選擇
    """
    if not files:
        print("未找到符合格式的檔案")
        return None
    
    print("找到以下檔案:")
    for i, filename in enumerate(files, 1):
        print(f"{i}. {filename}")
    
    while True:
        try:
            choice = input(f"\n請選擇檔案 (1-{len(files)}): ")
            choice_num = int(choice)
            if 1 <= choice_num <= len(files):
                return files[choice_num - 1]
            else:
                print(f"請輸入 1 到 {len(files)} 之間的數字")
        except ValueError:
            print("請輸入有效的數字")

def read_and_process_data(file_path):
    """
    讀取CSV檔案並提取Date和Net P&L數據
    """
    try:
        df = pd.read_csv(file_path)
        
        if 'Date' not in df.columns or 'Net P&L' not in df.columns:
            print("檔案缺少必要的欄位 (Date 或 Net P&L)")
            return None
        
        # 轉換日期格式
        df['Date'] = pd.to_datetime(df['Date'])
        
        # 按日期分組並計算每日總Net P&L
        daily_pnl = df.groupby('Date')['Net P&L'].sum().reset_index()
        
        # 計算累積損益
        daily_pnl['Cumulative P&L'] = daily_pnl['Net P&L'].cumsum()
        
        return daily_pnl
        
    except Exception as e:
        print(f"讀取檔案時發生錯誤: {e}")
        return None

def plot_pnl_chart(data, selected_file, output_dir):
    """
    繪製Net P&L圖表並保存
    """
    plt.figure(figsize=(12, 8))
    
    # 繪製每日損益
    plt.subplot(2, 1, 1)
    plt.plot(data['Date'], data['Net P&L'], marker='o', linewidth=2, markersize=4)
    plt.title('Daily Net P&L')
    plt.xlabel('Date')
    plt.ylabel('Net P&L')
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # 繪製累積損益
    plt.subplot(2, 1, 2)
    plt.plot(data['Date'], data['Cumulative P&L'], marker='o', linewidth=2, markersize=4, color='green')
    plt.title('Cumulative P&L')
    plt.xlabel('Date')
    plt.ylabel('Cumulative P&L')
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # 生成輸出檔案名稱
    base_name = selected_file.replace('.csv', '')
    output_filename = f"{base_name}_chart.png"
    output_path = os.path.join(output_dir, output_filename)
    
    try:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"圖表已保存至: {output_path}")
        plt.show()
        
        # 顯示統計資訊
        print(f"\n統計資訊:")
        print(f"總交易天數: {len(data)}")
        print(f"總Net P&L: {data['Net P&L'].sum():.4f}")
        print(f"平均每日P&L: {data['Net P&L'].mean():.4f}")
        print(f"最大單日盈利: {data['Net P&L'].max():.4f}")
        print(f"最大單日虧損: {data['Net P&L'].min():.4f}")
        
    except Exception as e:
        print(f"保存圖表時發生錯誤: {e}")

def main():
    # 設定目錄路徑
    return_dir = "csv/Return"
    
    print("=== 真實回報圖表生成器 ===")
    
    # 掃描檔案
    files = scan_overall_stat_files(return_dir)
    
    if not files:
        print("未找到符合條件的檔案")
        return
    
    # 讓用戶選擇檔案
    selected_file = display_files_menu(files)
    
    if not selected_file:
        return
    
    # 讀取並處理數據
    file_path = os.path.join(return_dir, selected_file)
    data = read_and_process_data(file_path)
    
    if data is None:
        return
    
    # 繪製圖表
    plot_pnl_chart(data, selected_file, return_dir)

if __name__ == "__main__":
    main()