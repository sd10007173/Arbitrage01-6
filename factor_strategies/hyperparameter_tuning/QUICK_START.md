# 🚀 超參數調優系統 - 快速開始指南

## 🎯 三種使用方式

### 1️⃣ 互動式界面（推薦）
```bash
python main.py
```
- 無參數啟動，進入圖形化選單
- 抽樣模式：10-50000個策略（隨機抽樣）
- 全測模式：1,033,200個策略（完整窮舉）
- 智能預估時間和資源消耗

### 2️⃣ 命令行模式（快速）
```bash
# 抽樣模式 - 隨機抽樣N個策略
python main.py --sampling 10     # 測試10個策略 (<1分鐘)
python main.py --sampling 100    # 測試100個策略 (5-15分鐘)
python main.py --sampling 1000   # 測試1000個策略 (30-90分鐘)
python main.py --sampling 5000   # 測試5000個策略 (2-6小時)

# 全測模式 - 執行所有1,033,200個組合
python main.py --full

# 自定義配置文件
python main.py --config my_config.yaml --sampling 50
```

### 3️⃣ 向下兼容（舊版本）
```bash
# 舊參數仍然支持，但會顯示棄用警告
python main.py --test --test-strategies 10
```

## 🎲 抽樣模式選項

| 策略數 | 預估時間 | 適用場景 |
|--------|----------|----------|
| 10     | <1分鐘   | 快速測試、驗證系統 |
| 50     | 1-3分鐘  | 初步探索、參數調試 |
| 100    | 5-15分鐘 | 配置文件設定（可調整）|
| 500    | 15-45分鐘| 中等規模研究 |
| 1000   | 30-90分鐘| 大規模研究 |
| 2500-10000 | 1-12小時 | 超大規模研究 |

## 📋 全測模式

| 模式 | 策略數 | 預估時間 | 適用場景 |
|------|--------|----------|----------|
| 全測 | 1,033,200 | 數天至數週 | 終極完整分析 |

## 📋 輸出結果

每次執行都會創建時間戳目錄：
```
results/
├── sampling_100_20250701_131135/
│   ├── final_results/
│   │   └── batch_results_*.json          # 完整結果數據
│   ├── reports/
│   │   └── analysis_report_*.txt         # 分析報告
│   ├── logs/
│   │   └── batch_execution_*.log         # 執行日誌
│   └── temp_configs/
│       └── *.json                        # 策略配置
```

## 🔧 系統狀態檢查

使用互動式界面的「系統狀態」功能，或：
```bash
python check_environment.py
```

## ⚡ 快速示例

```bash
# 1. 測試系統是否正常
python main.py --sampling 5

# 2. 查看結果報告
cat results/*/reports/analysis_report_*.txt

# 3. 大規模分析
python main.py --sampling 1000
```

## 🎯 下一步

1. 查看詳細文檔：`USAGE_GUIDE_DETAILED.md`
2. 配置範例：`config_examples.yaml`
3. 環境檢查：`check_environment.py`

---

🎉 **恭喜！您已經準備好使用超參數調優系統了！** 