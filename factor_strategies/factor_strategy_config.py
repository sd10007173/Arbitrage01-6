"""
因子策略設定檔 (Factor Strategy Configuration) - 數據庫版本

此檔案是所有基於歷史數據的因子策略的控制中心。
每個策略都在 FACTOR_STRATEGIES 字典中進行完整、獨立的定義。

您可以通過修改此檔案來：
- 新增一個全新的因子策略。
- 調整現有策略的數據准入規則 (如所需歷史天數)。
- 為策略新增、移除或修改因子。
- 調整因子計算所需的回看窗口 (window) 或特殊參數 (params)。
- 調整最終排名時各個因子的權重 (weights)。

數據庫版本修改：
- 數據來源：從 return_metrics 表讀取
- 數據輸出：寫入 strategy_ranking 表
- 使用 database_operations.py 的函數進行數據庫操作
"""

FACTOR_STRATEGIES = {
    'cerebrum_core': {
        'name': 'Cerebrum-Core v1.0',
        'description': '結合長期趨勢、風險調整回報、穩定性和勝率的綜合因子模型。',

        # --- 數據准入規則 ---
        'data_requirements': {
            'min_data_days': 30,         # 最少需要30天的歷史數據
            'skip_first_n_days': 3,      # 跳過前3天的數據（新幣穩定期）
        },

        # --- 因子定義 (此策略需要哪些因子以及如何計算) ---
        'factors': {
            # 因子名稱: {計算細節}
            'F_trend': {
                'function': 'calculate_trend_slope',     # 對應 factor_library.py 中的函式名
                'window': 90,                            # 計算所需的回看天數
                'input_col': 'roi_1d',                   # 計算所需的數據欄位（數據庫版本）
            },
            'F_sharpe': {
                'function': 'calculate_sharpe_ratio',
                'window': 60,
                'input_col': 'roi_1d',                   # 使用1日ROI計算夏普比率
                'params': {'annualizing_factor': 365}    # 傳遞給計算函式的額外參數
            },
            'F_stability': {
                'function': 'calculate_inv_std_dev',
                'window': 60,
                'input_col': 'roi_1d',
                'params': {'epsilon': 1e-9}
            },
            'F_winrate': {
                'function': 'calculate_win_rate',
                'window': 60,
                'input_col': 'roi_1d',
            }
        },

        # --- 最終排名邏輯 (如何組合這些因子) ---
        'ranking_logic': {
            'indicators': ['F_trend', 'F_sharpe', 'F_stability', 'F_winrate'], # 必須與上面定義的因子名稱對應
            'weights': [0.10, 0.40, 0.30, 0.20]                               # 權重總和應為1
        }
    },

    'cerebrum_momentum': {
        'name': 'Cerebrum-Momentum v1.0',
        'description': '專注於動量和趨勢的因子策略，適合趨勢明顯的市場環境。',
        'data_requirements': {
            'min_data_days': 60,
            'skip_first_n_days': 5,
        },
        'factors': {
            'F_trend_long': {
                'function': 'calculate_trend_slope',
                'window': 90,
                'input_col': 'roi_7d',                   # 使用7日ROI計算長期趨勢
            },
            'F_trend_short': {
                'function': 'calculate_trend_slope',
                'window': 30,
                'input_col': 'roi_1d',                   # 使用1日ROI計算短期趨勢
            },
            'F_sharpe_momentum': {
                'function': 'calculate_sharpe_ratio',
                'window': 30,
                'input_col': 'roi_1d',
                'params': {'annualizing_factor': 365}
            },
        },
        'ranking_logic': {
            'indicators': ['F_trend_long', 'F_trend_short', 'F_sharpe_momentum'],
            'weights': [0.50, 0.30, 0.20]
        }
    },

    'cerebrum_stability': {
        'name': 'Cerebrum-Stability v1.0', 
        'description': '專注於穩定性和風險控制的因子策略，適合保守型投資。',
        'data_requirements': {
            'min_data_days': 90,
            'skip_first_n_days': 7,
        },
        'factors': {
            'F_stability_long': {
                'function': 'calculate_inv_std_dev',
                'window': 90,
                'input_col': 'roi_7d',
                'params': {'epsilon': 1e-9}
            },
            'F_stability_short': {
                'function': 'calculate_inv_std_dev',
                'window': 30,
                'input_col': 'roi_1d',
                'params': {'epsilon': 1e-9}
            },
            'F_winrate_consistent': {
                'function': 'calculate_win_rate',
                'window': 90,
                'input_col': 'roi_1d',
            },
            'F_sharpe_stable': {
                'function': 'calculate_sharpe_ratio',
                'window': 90,
                'input_col': 'roi_7d',
                'params': {'annualizing_factor': 52}     # 週化夏普比率
            }
        },
        'ranking_logic': {
            'indicators': ['F_stability_long', 'F_stability_short', 'F_winrate_consistent', 'F_sharpe_stable'],
            'weights': [0.35, 0.25, 0.25, 0.15]
        }
    },
    'sharp_only_v1': {
        'name': 'sharp only v1',
        'description': '純sharp ratio。',

        # --- 數據准入規則 ---
        'data_requirements': {
            'min_data_days': 30,         # 最少需要30天的歷史數據
            'skip_first_n_days': 3,      # 跳過前3天的數據（新幣穩定期）
        },

        # --- 因子定義 (此策略需要哪些因子以及如何計算) ---
        'factors': {
            # 因子名稱: {計算細節}
            'F_sharpe': {
                'function': 'calculate_sharpe_ratio',
                'window': 60,
                'input_col': 'roi_1d',                   # 使用1日ROI計算夏普比率
                'params': {'annualizing_factor': 365}    # 傳遞給計算函式的額外參數
            },
        },

        'ranking_logic': {
            'indicators': ['F_sharpe'], # 必須與上面定義的因子名稱對應
            'weights': [1.0]            # 權重總和應為1
        }
    },

    'sharp_only_v2': {
        'name': 'sharp only v2',
        'description': '純sharp ratio。',

        # --- 數據准入規則 ---
        'data_requirements': {
            'min_data_days': 30,         # 最少需要30天的歷史數據
            'skip_first_n_days': 3,      # 跳過前3天的數據（新幣穩定期）
        },

        # --- 因子定義 (此策略需要哪些因子以及如何計算) ---
        'factors': {
            # 因子名稱: {計算細節}
            'F_sharpe': {
                'function': 'calculate_sharpe_ratio',
                'window': 30,
                'input_col': 'roi_1d',                   # 使用1日ROI計算夏普比率
                'params': {'annualizing_factor': 365}    # 傳遞給計算函式的額外參數
            },
        },

        'ranking_logic': {
            'indicators': ['F_sharpe'], # 必須與上面定義的因子名稱對應
            'weights': [1.0]            # 權重總和應為1
        }
    },

    'sharp_only_v3': {
        'name': 'sharp only v3',
        'description': '純sharp ratio。',

        # --- 數據准入規則 ---
        'data_requirements': {
            'min_data_days': 10,         # 最少需要30天的歷史數據
            'skip_first_n_days': 3,      # 跳過前3天的數據（新幣穩定期）
        },

        # --- 因子定義 (此策略需要哪些因子以及如何計算) ---
        'factors': {
            # 因子名稱: {計算細節}
            'F_sharpe': {
                'function': 'calculate_sharpe_ratio',
                'window': 10,
                'input_col': 'roi_1d',                   # 使用1日ROI計算夏普比率
                'params': {'annualizing_factor': 365}    # 傳遞給計算函式的額外參數
            },
        },

        'ranking_logic': {
            'indicators': ['F_sharpe'], # 必須與上面定義的因子名稱對應
            'weights': [1.0]            # 權重總和應為1
        }
    },

    'sharp_only_v4': {
        'name': 'sharp only v4',
        'description': '純sharp ratio。',

        # --- 數據准入規則 ---
        'data_requirements': {
            'min_data_days': 90,         # 最少需要30天的歷史數據
            'skip_first_n_days': 3,      # 跳過前3天的數據（新幣穩定期）
        },

        # --- 因子定義 (此策略需要哪些因子以及如何計算) ---
        'factors': {
            # 因子名稱: {計算細節}
            'F_sharpe': {
                'function': 'calculate_sharpe_ratio',
                'window': 90,
                'input_col': 'roi_1d',                   # 使用1日ROI計算夏普比率
                'params': {'annualizing_factor': 365}    # 傳遞給計算函式的額外參數
            },
        },

        'ranking_logic': {
            'indicators': ['F_sharpe'], # 必須與上面定義的因子名稱對應
            'weights': [1.0]            # 權重總和應為1
        }
    },


    'trend_only_v1': {
        'name': 'trend only v1.0',
        'description': '無。',

        # --- 數據准入規則 ---
        'data_requirements': {
            'min_data_days': 30,         # 最少需要30天的歷史數據
            'skip_first_n_days': 3,      # 跳過前3天的數據（新幣穩定期）
        },

        # --- 因子定義 (此策略需要哪些因子以及如何計算) ---
        'factors': {
            # 因子名稱: {計算細節}
            'F_trend': {
                'function': 'calculate_trend_slope',     # 對應 factor_library.py 中的函式名
                'window': 60,                            # 計算所需的回看天數
                'input_col': 'roi_1d',                   # 計算所需的數據欄位（數據庫版本）
            },
        },
        # --- 最終排名邏輯 (如何組合這些因子) ---
        'ranking_logic': {
            'indicators': ['F_trend'], # 必須與上面定義的因子名稱對應
            'weights': [1.0]                               # 權重總和應為1
        }
    },

    'trend_only_v2': {
        'name': 'trend only v2.0',
        'description': '無。',

        # --- 數據准入規則 ---
        'data_requirements': {
            'min_data_days': 30,         # 最少需要30天的歷史數據
            'skip_first_n_days': 3,      # 跳過前3天的數據（新幣穩定期）
        },

        # --- 因子定義 (此策略需要哪些因子以及如何計算) ---
        'factors': {
            # 因子名稱: {計算細節}
            'F_trend': {
                'function': 'calculate_trend_slope',     # 對應 factor_library.py 中的函式名
                'window': 30,                            # 計算所需的回看天數
                'input_col': 'roi_1d',                   # 計算所需的數據欄位（數據庫版本）
            },
        },
        # --- 最終排名邏輯 (如何組合這些因子) ---
        'ranking_logic': {
            'indicators': ['F_trend'], # 必須與上面定義的因子名稱對應
            'weights': [1.0]                               # 權重總和應為1
        }
    },
    # --- 測試專用策略 ---
    'test_factor_simple': {
        'name': 'Simple Factor Test Strategy',
        'description': '用於測試因子計算系統的簡單策略。',
        'data_requirements': {
            'min_data_days': 7,          # 最小化數據需求
            'skip_first_n_days': 0,
        },
        'factors': {
            'F_simple_trend': {
                'function': 'calculate_trend_slope',     # 只用一個簡單的因子
                'window': 7,                             # 短回看週期
                'input_col': 'roi_1d'
            },
        },
        'ranking_logic': {
            'indicators': ['F_simple_trend'],
            'weights': [1.0]                             # 權重為1，結果就是因子本身
        }
    }
}