# Get Return V1 - 套利收益分析工具

## 📋 **功能概述**

這個工具整合了幣安和Bybit的資金費用、手續費、保證金數據，提供完整的套利收益分析：

1. **資金費用分析**：計算永續合約資金費用收益
2. **手續費計算**：統計交易手續費成本
3. **保證金追蹤**：增量計算保證金歷史數據
4. **收益率計算**：每日收益率和年化收益率分析
5. **多格式輸出**：生成三個CSV檔案（整合、幣安、Bybit）

## 🔧 **安裝與設定**

### 1. 安裝依賴
```bash
pip install requests pandas
```

### 2. 配置API金鑰
```bash
# 複製配置檔案範例
cp api_config.py.example api_config.py

# 編輯配置檔案，填入真實的API金鑰
nano api_config.py
```

### 3. API權限設定
確保API金鑰具有以下權限：
- **幣安**：Futures API讀取權限
- **Bybit**：統一交易帳戶讀取權限

## 🚀 **使用方法**

### 基本用法
```bash
python get_return_v1.py --start 2024-01-01 --end 2024-01-31
```

### 單日分析
```bash
python get_return_v1.py --start 2024-01-15 --end 2024-01-15
```

### 多日分析
```bash
python get_return_v1.py --start 2024-01-01 --end 2024-12-31
```

## 📊 **輸出文件**

程式會在 `csv/Return/` 目錄下生成三個CSV檔案：

### 1. overall_stat_YYYY_MM_DD.csv
**主要分析數據**，包含：
- Date: 日期
- Symbol: 交易對
- Binance FF: 幣安資金費用
- Bybit FF: Bybit資金費用
- Binance TF: 幣安手續費
- Bybit TF: Bybit手續費
- Net P&L: 淨損益
- Binance M: 幣安保證金
- Bybit M: Bybit保證金
- Total M: 總保證金
- Return: 日收益率
- ROI: 年化收益率

### 2. binance_stat_YYYY_MM_DD.csv
**幣安原始數據**，包含：
- Date: 日期
- Symbol: 交易對
- Funding_Fee: 資金費用
- Trading_Fee: 手續費
- Position_Margin: 持倉保證金
- API_Source: 數據來源

### 3. bybit_stat_YYYY_MM_DD.csv
**Bybit原始數據**，格式同幣安。

## 🔄 **保證金數據處理**

### 增量計算機制
- **當日查詢**：從API獲取最新保證金數據
- **歷史查詢**：從本地`csv/Return/margin_history.json`讀取
- **缺失數據**：標記為null，不影響其他計算

### 數據來源標記
- `current_api_call`: 當日API查詢
- `no_margin_data`: 無保證金歷史數據

## 📈 **計算公式**

### 核心指標
```
淨損益 = 幣安資金費用 + Bybit資金費用 + 幣安手續費 + Bybit手續費
日收益率 = 淨損益 / (幣安保證金 + Bybit保證金)
年化收益率 = 日收益率 × 365
```

### 數據篩選
- 只記錄有交易活動或保證金變化的記錄
- 自動過濾零值交易
- 支援所有永續合約

## 🛠️ **故障排除**

### 常見問題

1. **API金鑰錯誤**
   ```
   ❌ 請創建 api_config.py 並設定API金鑰
   ```
   解決：確保api_config.py存在且包含正確的API金鑰

2. **網路超時**
   ```
   Binance API異常: timeout
   ```
   解決：檢查網路連接，等待後重試

3. **權限不足**
   ```
   Binance API錯誤: 401 - Unauthorized
   ```
   解決：確認API金鑰權限設定

4. **保證金歷史缺失**
   - 系統會自動標記為null
   - 不影響資金費用和手續費計算
   - 只影響收益率計算

## 📋 **輸出範例**

### overall_stat_2024_01_15.csv
```csv
Date,Symbol,Binance FF,Bybit FF,Binance TF,Bybit TF,Net P&L,Binance M,Bybit M,Total M,Return,ROI
2024-01-15,BTCUSDT,12.34,-8.76,-0.50,-0.30,2.78,10000.0,15000.0,25000.0,0.0001112,0.0406
2024-01-15,ETHUSDT,5.67,-3.21,-0.20,-0.15,2.11,8000.0,12000.0,20000.0,0.0001055,0.0385
```

### binance_stat_2024_01_15.csv
```csv
Date,Symbol,Funding_Fee,Trading_Fee,Position_Margin,API_Source
2024-01-15,BTCUSDT,12.34,-0.50,10000.0,current_api_call
2024-01-15,ETHUSDT,5.67,-0.20,8000.0,current_api_call
```

## 🔍 **進階功能**

### 批次處理
```bash
# 處理整年數據
python get_return_v1.py --start 2024-01-01 --end 2024-12-31

# 處理多個月份
for month in {01..12}; do
    python get_return_v1.py --start 2024-$month-01 --end 2024-$month-31
done
```

### 數據分析
```python
import pandas as pd

# 讀取數據
df = pd.read_csv('csv/Return/overall_stat_2024_01_01_to_2024_12_31.csv')

# 計算統計指標
total_pnl = df['Net P&L'].sum()
avg_return = df['Return'].mean()
sharpe_ratio = df['Return'].mean() / df['Return'].std()
```

## 🚨 **注意事項**

1. **API頻率限制**：程式已內建延遲機制防止頻率超限
2. **歷史數據**：Bybit歷史數據查詢有時間限制
3. **保證金計算**：基於標記價格計算，可能與實際略有差異
4. **時區設定**：所有時間戳均使用UTC時區
5. **數據完整性**：建議每日執行以確保數據連續性

## 🔗 **相關工具**

- `get_binance_return.py`: 單獨幣安資金費用查詢
- `get_bybit_return.py`: 單獨Bybit資金費用查詢
- `get_binance&bybit_return.py`: 原始合併工具（已被此工具取代） 