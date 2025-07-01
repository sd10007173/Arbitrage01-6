# 大規模超參數調優系統

**Mass Hyperparameter Tuning System**

一個專為因子策略設計的大規模超參數調優系統，支持參數空間窮舉、真實回測執行和大規模並行處理。

## 🎯 系統概述

本系統按照PRD設計，實現了以下核心業務需求：
- **BR-001**: 參數空間窮舉 - 系統性生成所有參數組合
- **BR-002**: 真實回測執行 - 調用真實的回測腳本
- **BR-003**: 大規模處理 - 支持10000+策略並行執行

## 🏗️ 系統架構

### 五大核心組件

1. **參數空間生成器** (ParameterSpaceGenerator)
   - 窮舉式參數組合生成
   - 智能抽樣（隨機、拉丁超立方、網格、Sobol）
   - 參數空間大小計算

2. **批量執行引擎** (BatchExecutionEngine)  
   - 真實回測腳本調用
   - 並行執行管理
   - 錯誤處理和重試

3. **進度管理器** (ProgressManager)
   - 執行進度追蹤
   - 斷點續跑支持
   - 會話狀態管理

4. **結果收集器** (ResultCollector)
   - 回測結果收集
   - 性能指標分析
   - 結果導出功能

5. **數據庫管理器** (DatabaseManager)
   - 臨時數據庫管理
   - 執行隊列管理
   - 結果持久化

## 📦 安裝與配置

### 環境要求

- Python 3.8+
- 依賴模塊：pandas, numpy, sqlite3, yaml, concurrent.futures
- 現有回測系統：backtest_v5.py

### 配置文件

系統使用 `mass_tuning_config.yaml` 配置文件，包含：

```yaml
# 系統配置
system:
  database_path: "hyperparameter_tuning.db"
  max_parallel: 4
  timeout_minutes: 30

# 參數空間配置
parameters:
  factors:
    type: "choice"
    choices: [["SR"], ["ST"], ["DD"], ["SR", "ST"], ...]
  window_size:
    type: "choice" 
    choices: [5, 10, 20, 30, 60, 90, ...]
  # ... 更多參數
```

## 🚀 快速開始

### 1. 系統測試

```bash
# 進入系統目錄
cd factor_strategies/hyperparameter_tuning

# 執行系統測試
python test_system.py
```

### 2. 生成策略參數組合

```bash
# 隨機抽樣1000個策略
python mass_tuning_system.py generate --mode sampling --size 1000

# 使用拉丁超立方抽樣
python mass_tuning_system.py generate --mode sampling --size 500 --method latin_hypercube

# 窮舉式生成（注意：可能產生大量組合）
python mass_tuning_system.py generate --mode exhaustive --size 10000
```

### 3. 執行批量回測

```bash
# 執行回測（4個並發）
python mass_tuning_system.py execute --parallel 4

# 斷點續跑
python mass_tuning_system.py execute --parallel 4 --resume

# 指定會話執行
python mass_tuning_system.py execute --session session_20241201_143022 --parallel 2
```

### 4. 查看執行狀態

```bash
# 查看最新會話狀態
python mass_tuning_system.py status

# 查看詳細狀態
python mass_tuning_system.py status --detailed

# 查看特定會話
python mass_tuning_system.py status --session session_20241201_143022 --detailed
```

### 5. 數據清理

```bash
# 清理失敗記錄
python mass_tuning_system.py clean --failed_only

# 清理特定會話
python mass_tuning_system.py clean --session session_20241201_143022

# 清理所有數據
python mass_tuning_system.py clean
```

## 📊 結果分析

### 使用Python API

```python
from factor_strategies.hyperparameter_tuning.mass_tuning_system import MassTuningSystem

# 初始化系統
system = MassTuningSystem()

# 獲取會話結果
session_id = "session_20241201_143022"
results = system.result_collector.get_session_results(session_id, limit=10)

# 生成匯總報告
report = system.result_collector.generate_summary_report(session_id)
print(f"最佳夏普比率: {report['statistics']['best_sharpe_ratio']}")

# 導出結果
system.result_collector.export_results(session_id, format="csv")
```

### 最佳策略查看

```python
# 獲取前10個最佳策略
top_performers = system.result_collector.get_top_performers(session_id, top_n=10)

for performer in top_performers:
    print(f"策略 {performer.strategy_id}:")
    print(f"  夏普比率: {performer.sharpe_ratio:.4f}")
    print(f"  年化收益: {performer.annual_return:.4f}")
    print(f"  最大回撤: {performer.max_drawdown:.4f}")
```

## 🔧 高級用法

### 自定義參數空間

```python
# 修改配置文件或使用API
param_info = system.param_generator.get_parameter_space_info()
print(f"當前參數空間大小: {param_info['total_combinations']:,}")

# 生成特定參數組合
strategies = system.param_generator.generate_strategies(
    mode="sampling",
    size=1000,
    method="sobol",  # 使用Sobol序列
    seed=42         # 固定隨機種子
)
```

### 性能監控

```python
# 獲取執行性能統計
perf_stats = system.execution_engine.get_performance_stats()
print(f"平均執行時間: {perf_stats['avg_time']:.2f}秒")
print(f"最近平均時間: {perf_stats['recent_avg']:.2f}秒")

# 檢查執行狀態
if system.execution_engine.is_running():
    current_session = system.execution_engine.get_current_session()
    print(f"正在執行會話: {current_session}")
```

### 多會話對比

```python
# 對比多個會話的結果
session_ids = ["session_20241201_143022", "session_20241201_150000"]
comparison = system.result_collector.get_comparison_report(session_ids)

print("最佳整體策略:")
best = comparison['best_overall']
print(f"  會話: {best['session_id']}")
print(f"  策略: {best['strategy_id']}")
print(f"  夏普比率: {best['sharpe_ratio']}")
```

## 📁 項目結構

```
factor_strategies/hyperparameter_tuning/
├── mass_tuning_system.py          # 主程序入口
├── mass_tuning_config.yaml        # 配置文件
├── test_system.py                 # 測試腳本
├── README.md                      # 使用說明
├── core/                          # 核心模塊
│   ├── __init__.py
│   ├── parameter_generator.py     # 參數空間生成器
│   ├── execution_engine.py        # 批量執行引擎
│   ├── progress_manager.py        # 進度管理器
│   ├── result_collector.py        # 結果收集器
│   └── database_manager.py        # 數據庫管理器
├── config/                        # 配置模塊
│   ├── __init__.py
│   └── config_manager.py          # 配置管理器
└── logs/                          # 日誌目錄
```

## ⚠️ 注意事項

### 數據庫設計

- **開發期**: 使用隔離的 `hyperparameter_tuning.db`
- **正式期**: 結果需要保存到 `funding_rate.db` 的正式表
  - `strategy_ranking` - 策略排名
  - `backtest_trades` - 交易記錄  
  - `backtest_result` - 回測結果

### 執行環境

- 系統會調用真實的回測腳本 `backtest_v5.py`
- 確保回測環境正確配置
- 建議在服務器環境執行大規模測試

### 性能考慮

- 默認並發數為4，可根據硬件調整
- 大規模執行時注意磁盤空間
- 建議定期清理舊數據

## 📈 使用場景

### 1. 策略優化

```bash
# 生成大量參數組合
python mass_tuning_system.py generate --mode sampling --size 5000

# 執行批量回測
python mass_tuning_system.py execute --parallel 8

# 分析最佳參數
python -c "
from factor_strategies.hyperparameter_tuning.mass_tuning_system import MassTuningSystem
system = MassTuningSystem()
session_id = system.progress_manager.get_latest_session()
report = system.result_collector.generate_summary_report(session_id)
print('最佳策略參數:', report['best_strategies'][0])
"
```

### 2. 參數敏感性分析

```bash
# 使用網格抽樣進行參數掃描
python mass_tuning_system.py generate --mode sampling --size 1000 --method grid

# 生成參數性能分析報告
python -c "
from factor_strategies.hyperparameter_tuning.mass_tuning_system import MassTuningSystem
system = MassTuningSystem()
session_id = system.progress_manager.get_latest_session()
report = system.result_collector.generate_summary_report(session_id)
param_analysis = report['parameter_analysis']
print('窗口大小分析:', param_analysis['window_size'])
print('重平衡頻率分析:', param_analysis['rebalance_frequency'])
"
```

### 3. 批量測試不同因子組合

```bash
# 專注測試多因子組合的效果
# 可以修改配置文件，只包含多因子組合
python mass_tuning_system.py generate --mode exhaustive --size 10000
python mass_tuning_system.py execute --parallel 6
```

## 🆘 故障排除

### 常見問題

1. **環境驗證失敗**
   ```bash
   python test_system.py  # 檢查具體問題
   ```

2. **執行卡住**
   ```bash
   python mass_tuning_system.py status --detailed  # 查看詳細狀態
   ```

3. **內存不足**
   - 減少並發數：`--parallel 2`
   - 分批執行：使用較小的`--size`

4. **數據庫鎖定**
   ```bash
   python mass_tuning_system.py clean --failed_only  # 清理失敗記錄
   ```

### 日誌查看

```bash
# 查看最新日誌
ls -la logs/
tail -f logs/mass_tuning_*.log
```

## 📞 支持

如有問題，請檢查：
1. 系統測試是否通過：`python test_system.py`
2. 配置文件是否正確：`mass_tuning_config.yaml`
3. 回測環境是否可用：檢查 `backtest_v5.py`
4. 日誌文件：`logs/` 目錄下的錯誤信息

---

**版本**: v1.0  
**創建日期**: 2024-12-01  
**最後更新**: 2024-12-01 