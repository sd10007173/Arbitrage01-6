# 超參數調優系統使用指南

## 📋 系統概述

超參數調優系統是一個自動化的因子策略優化工具，能夠：
- 自動生成大量不同的策略配置組合
- 批量執行策略回測
- 分析結果並找出最佳策略
- 提供參數重要性分析和視覺化報告

## 🏗️ 系統架構

```
📁 hyperparameter_tuning/
├── 📄 config.yaml              # 配置文件
├── 📄 param_generator.py       # 參數組合生成器
├── 📄 batch_runner.py          # 批量執行器
├── 📄 result_analyzer.py       # 結果分析器
├── 📄 main.py                  # 主程序
├── 📄 README.md               # 使用說明
└── 📁 results/                # 結果存儲目錄
    ├── strategy_configs/      # 生成的策略配置
    ├── backtest_results/      # 回測結果
    ├── analysis_reports/      # 分析報告
    ├── visualizations/        # 視覺化圖表
    └── logs/                  # 執行日誌
```

## 🚀 快速開始

### 1. 環境準備

確保已安裝必要的Python套件：
```bash
pip install pyyaml pandas numpy matplotlib seaborn
```

### 2. 配置設定

編輯 `config.yaml` 文件，配置您的參數空間：

```yaml
# 執行模式設定
execution:
  mode: "sampling"          # "exhaustive" 或 "sampling"
  n_strategies: 100         # 抽樣模式下的策略數量
  max_parallel_jobs: 4      # 並行執行數量

# 回測設定
backtest:
  start_date: "2024-01-01"
  end_date: "2025-06-20"
  initial_capital: 10000
  position_size: 0.25
```

### 3. 運行系統

#### 快速測試（推薦首次使用）
```bash
python main.py --test --test-strategies 10
```

#### 正常運行
```bash
python main.py
```

#### 指定配置文件
```bash
python main.py --config my_config.yaml
```

## ⚙️ 配置詳解

### 參數空間配置

```yaml
parameters:
  # 可用的因子函式
  available_factors:
    - calculate_trend_slope      # 趨勢斜率
    - calculate_sharpe_ratio     # 夏普比率
    - calculate_inv_std_dev      # 穩定性指標
    - calculate_win_rate         # 勝率
    - calculate_max_drawdown     # 最大回撤
    - calculate_sortino_ratio    # 索提諾比率
  
  # 窗口期選項
  windows: [5, 10, 15, 20, 30, 45, 60, 90, 120, 150, 180, 210, 240, 270, 300]
  
  # 輸入數據列
  input_columns: [roi_1d, roi_2d, roi_7d, roi_14d, roi_30d]
  
  # 數據要求參數
  min_data_days: [10, 15, 20, 30, 45, 60, 90, 120, 150, 180, 210, 240, 270, 300]
  skip_first_n_days: [0, 1, 2, 3, 5, 7, 10, 15]
  
  # 因子組合設定
  max_factors_per_strategy: 3    # 每個策略最多包含幾個因子
  min_factors_per_strategy: 1    # 每個策略最少包含幾個因子
```

### 執行模式

#### 抽樣模式 (sampling)
- 適用於快速測試和探索
- 從所有可能組合中隨機選擇指定數量進行測試
- 速度快，適合調試和驗證

#### 窮舉模式 (exhaustive)
- 測試所有可能的參數組合
- 完整覆蓋參數空間
- 適合最終分析，但耗時較長

## 📊 結果分析

### 輸出文件結構

```
results/sampling_100_20250630_180000/
├── logs/                          # 執行日誌
├── strategy_configs/              # 策略配置文件
├── backtest_results/              # 回測結果
├── analysis_reports/              # 分析報告
│   └── hyperparameter_analysis_report_xxx.txt
├── visualizations/                # 視覺化圖表
│   ├── performance_distribution.png
│   ├── parameter_importance.png
│   ├── top_strategies_comparison.png
│   └── correlation_heatmap.png
└── final_results/                 # 最終結果
    └── batch_results_xxx.json
```

### 關鍵指標

系統會分析以下關鍵績效指標：
- **年化收益率**: 策略的年化投資回報率
- **夏普比率**: 風險調整後的收益率
- **最大回撤**: 最大虧損幅度
- **勝率**: 獲利交易占比

### 參數重要性分析

系統會自動分析各參數對策略績效的影響：
- 數值參數：使用相關性分析
- 分類參數：使用方差分析
- 布林參數：使用對比分析

## 🔧 進階使用

### 自定義因子函式

在 `factor_library.py` 中添加新的因子計算函式：

```python
def calculate_my_custom_factor(data, window=30, input_column='roi_7d'):
    """
    自定義因子計算函式
    """
    # 實現您的因子計算邏輯
    return factor_values
```

然後在 `config.yaml` 中添加：

```yaml
parameters:
  available_factors:
    - calculate_my_custom_factor
```

### 調整權重分配

```yaml
parameters:
  weight_methods:
    - equal                      # 等權重
    - factor_score_weighted      # 因子分數加權
    - inverse_correlation        # 反相關加權
```

### 並行執行優化

```yaml
execution:
  max_parallel_jobs: 8           # 根據CPU核心數調整
```

## 🎯 最佳實踐

### 1. 參數空間設計原則

- **開始時使用較小的參數空間**：先用抽樣模式測試
- **逐步擴大參數範圍**：確認系統穩定後再擴大
- **避免過度細分**：太多參數組合可能導致過擬合

### 2. 執行策略

```bash
# 第1步：快速測試（5-10個策略）
python main.py --test --test-strategies 10

# 第2步：中等規模測試（100-500個策略）
# 修改 config.yaml: mode: "sampling", n_strategies: 500
python main.py

# 第3步：完整分析（如果組合數合理）
# 修改 config.yaml: mode: "exhaustive"
python main.py
```

### 3. 結果解讀

- **關注夏普比率**：比單純的收益率更重要
- **注意最大回撤**：控制風險
- **考慮樣本外表現**：避免過度優化
- **分析參數穩定性**：頂級策略的參數特徵

## 🐛 常見問題

### Q1: 執行時間太長怎麼辦？
A: 
- 使用抽樣模式而非窮舉模式
- 減少參數空間大小
- 增加並行任務數量

### Q2: 記憶體不足怎麼辦？
A:
- 減少同時執行的策略數量
- 關閉中間結果保存
- 分批次執行

### Q3: 結果不理想怎麼辦？
A:
- 檢查數據質量
- 調整參數範圍
- 增加更多因子類型
- 延長回測期間

## 📝 日誌和調試

### 查看執行日誌
```bash
tail -f results/xxx/logs/batch_execution_xxx.log
```

### 調試模式
```python
# 在 main.py 中添加
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 擴展開發

### 添加新的分析指標

在 `result_analyzer.py` 中添加新的分析函式：

```python
def analyze_custom_metric(self):
    # 實現您的自定義分析邏輯
    pass
```

### 整合其他回測引擎

修改 `batch_runner.py` 中的 `_run_backtest` 方法來整合您的回測系統。

## 📞 技術支援

如遇到問題，請檢查：
1. 配置文件格式是否正確
2. 所需的數據是否存在
3. Python套件是否完整安裝
4. 系統資源是否充足

---

**祝您使用愉快！找到最佳的交易策略！** 🚀 