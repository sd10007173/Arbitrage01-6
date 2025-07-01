#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超參數調優系統主程序
整合所有模組，提供完整的超參數調優流程
"""

import os
import sys
import yaml
import time
import argparse
from datetime import datetime
from typing import Dict, Any, List

# 添加當前目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from param_generator import ParameterGenerator
from batch_runner import BatchRunner
from result_analyzer import ResultAnalyzer


class InteractiveUI:
    """互動式用戶界面"""
    
    def __init__(self, tuner):
        self.tuner = tuner
        
    def show_main_menu(self):
        """顯示主選單"""
        while True:
            print("\n" + "=" * 80)
            print("🎯 超參數調優系統")
            print("=" * 80)
            
            # 檢查系統狀態
            try:
                space_info = self.tuner.param_generator.get_space_info()
                print(f"✅ 環境檢查: 通過")
                print(f"📊 參數空間: {space_info['total_combinations']:,} 個策略組合")
                print(f"📁 配置文件: {self.tuner.config_file}")
            except Exception as e:
                print(f"⚠️  環境檢查: {str(e)}")
            
            print("\n請選擇執行模式:\n")
            print("  🎲 [1] 抽樣模式  - 隨機抽樣指定數量的策略")
            print("  📋 [2] 全測模式  - 完整執行配置文件設定")
            print("  ⚙️  [3] 系統狀態  - 查看環境和歷史記錄")
            print("  🚪 [4] 退出系統")
            
            choice = input("\n請輸入選擇 (1-4): ").strip()
            
            if choice == '1':
                self.show_sampling_menu()
            elif choice == '2':
                self.show_full_test_menu()
            elif choice == '3':
                self.show_system_status()
            elif choice == '4':
                print("\n👋 感謝使用超參數調優系統！")
                return
            else:
                print("❌ 無效選擇，請重新輸入...")
                
    def show_sampling_menu(self):
        """顯示抽樣模式選單"""
        while True:
            print("\n" + "=" * 80)
            print("🎲 抽樣模式")
            print("=" * 80)
            
            try:
                space_info = self.tuner.param_generator.get_space_info()
                total_combinations = space_info['total_combinations']
                print(f"從 {total_combinations:,} 個策略組合中隨機抽樣")
            except:
                total_combinations = 1000000
                print(f"從 {total_combinations:,} 個策略組合中隨機抽樣")
            
            # 顯示config.yaml中的設定
            config_n_strategies = self.tuner.config['execution'].get('n_strategies', 100)
            
            print("\n🚀 快速選項:")
            print("  [1] 10個策略     (<1分鐘)")
            print("  [2] 50個策略     (1-3分鐘)")
            print(f"  [3] {config_n_strategies}個策略     (config.yaml設定)")
            print("  [4] 500個策略    (15-45分鐘)")
            print("  [5] 1000個策略   (30-90分鐘)")
            
            print("\n🎯 進階選項:")
            print("  [6] 大規模抽樣   (2500-10000個策略)")
            print("  [7] 自定義數量   (任意數量)")
            print("  [0] 返回主選單")
            
            choice = input("\n請輸入選擇 (0-7): ").strip()
            
            if choice == '0':
                return
            elif choice == '1':
                if self.confirm_execution('抽樣模式', 10):
                    self.execute_sampling_mode(10)
                    return
            elif choice == '2':
                if self.confirm_execution('抽樣模式', 50):
                    self.execute_sampling_mode(50)
                    return
            elif choice == '3':
                if self.confirm_execution('抽樣模式', config_n_strategies):
                    self.execute_sampling_mode(config_n_strategies)
                    return
            elif choice == '4':
                if self.confirm_execution('抽樣模式', 500):
                    self.execute_sampling_mode(500)
                    return
            elif choice == '5':
                if self.confirm_execution('抽樣模式', 1000):
                    self.execute_sampling_mode(1000)
                    return
            elif choice == '6':
                n_strategies = self.get_large_scale_strategy_count()
                if n_strategies and self.confirm_execution('抽樣模式', n_strategies):
                    self.execute_sampling_mode(n_strategies)
                    return
            elif choice == '7':
                n_strategies = self.get_custom_strategy_count()
                if n_strategies and self.confirm_execution('抽樣模式', n_strategies):
                    self.execute_sampling_mode(n_strategies)
                    return
            else:
                print("❌ 無效選擇，請重新輸入...")
                
    def show_full_test_menu(self):
        """顯示全測模式選單"""
        while True:
            print("\n" + "=" * 80)
            print("📋 全測模式")
            print("=" * 80)
            
            # 獲取參數空間信息
            try:
                space_info = self.tuner.param_generator.get_space_info()
                total_combinations = space_info['total_combinations']
            except:
                total_combinations = 1000000
            
            parallel = self.tuner.config['execution'].get('max_parallel_jobs', 4)
            time_estimate = self._estimate_time(total_combinations)
            
            print("全測模式將執行所有可能的策略組合：")
            print(f"\n📊 策略總數: {total_combinations:,} 個組合")
            print(f"⏰ 預估時間: {time_estimate}")
            print(f"🔄 並行數: {parallel}")
            print(f"💾 預估結果大小: ~{total_combinations//1000}GB")
            
            print(f"\n⚠️  全測模式注意事項:")
            print(f"     - 這是超大規模執行，可能需要數天至數週")
            print(f"     - 請確保硬碟空間充足 (建議至少{total_combinations//500}GB)")
            print(f"     - 建議在穩定的環境中運行，避免中斷")
            print(f"     - 可能會產生大量日誌和結果文件")
            
            print("\n選擇操作:\n")
            print("  🎯 [1] 開始全測     - 執行所有策略組合")
            print("  📝 [2] 修改配置     - 調整並行數等設定")
            print("  [0] 返回主選單")
            
            choice = input("\n請輸入選擇 (0-2): ").strip()
            
            if choice == '0':
                return
            elif choice == '1':
                # 全測模式確認
                if self.confirm_execution('全測模式', total_combinations):
                    self.execute_exhaustive_mode()
                    return
            elif choice == '2':
                self.show_config_modification_menu()
            else:
                print("❌ 無效選擇，請重新輸入...")
                
    def show_system_status(self):
        """顯示系統狀態"""
        print("\n" + "=" * 80)
        print("⚙️ 系統狀態")
        print("=" * 80)
        
        # 環境信息
        print("\n🔧 環境信息:")
        try:
            import sys
            print(f"  ✅ Python版本: {sys.version.split()[0]}")
            
            # 檢查套件
            required_packages = ['yaml', 'pandas', 'numpy', 'matplotlib', 'seaborn']
            for package in required_packages:
                try:
                    __import__(package)
                    print(f"  ✅ {package}: 已安裝")
                except ImportError:
                    print(f"  ❌ {package}: 未安裝")
            
            print(f"  ✅ 配置文件: 語法正確")
        except Exception as e:
            print(f"  ❌ 環境錯誤: {str(e)}")
        
        # 參數空間信息
        print("\n📊 參數空間:")
        try:
            space_info = self.tuner.param_generator.get_space_info()
            print(f"  - 總組合數: {space_info['total_combinations']:,}")
            print(f"  - 因子數量: {space_info.get('factors_count', 'N/A')}種")
            print(f"  - 窗口期選項: {space_info.get('windows_count', 'N/A')}種")
            print(f"  - 時間框架: {space_info.get('input_columns_count', 'N/A')}種")
        except Exception as e:
            print(f"  ❌ 無法計算: {str(e)}")
        
        # 歷史記錄
        print("\n📁 歷史記錄:")
        try:
            results_dir = os.path.join(current_dir, 'results')
            if os.path.exists(results_dir):
                subdirs = [d for d in os.listdir(results_dir) if os.path.isdir(os.path.join(results_dir, d))]
                subdirs.sort(reverse=True)  # 最新的在前
                
                if subdirs:
                    for i, subdir in enumerate(subdirs[:5]):  # 顯示最近5次
                        # 解析目錄名獲取信息
                        parts = subdir.split('_')
                        if len(parts) >= 3:
                            mode_type = parts[0]
                            strategies = parts[1] if parts[1].isdigit() else 'N/A'
                            date_time = '_'.join(parts[2:])
                            print(f"  - {date_time}: {strategies}策略 ({mode_type}模式) ✅")
                else:
                    print("  - 暫無執行記錄")
            else:
                print("  - 結果目錄不存在")
        except Exception as e:
            print(f"  ❌ 無法讀取歷史記錄: {str(e)}")
        
        # 系統資源
        print("\n💻 系統資源:")
        try:
            import psutil
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            print(f"  - CPU: {cpu_count}核心 (當前使用: {psutil.cpu_percent()}%)")
            print(f"  - 記憶體: {memory.total//1024//1024//1024}GB (當前使用: {memory.percent}%)")
        except ImportError:
            print("  - 需要安裝 psutil 套件來顯示系統資源")
        except Exception as e:
            print(f"  - 無法獲取系統資源信息: {str(e)}")
        
        input("\n按 Enter 鍵返回主選單...")
        
    def get_custom_strategy_count(self):
        """獲取自定義策略數量"""
        while True:
            try:
                print("\n自定義抽樣數量")
                print("=" * 20)
                n_strategies = int(input("請輸入策略數量 (1-10000): "))
                
                if 1 <= n_strategies <= 10000:
                    time_estimate = self._estimate_time(n_strategies)
                    size_estimate = f"~{n_strategies * 0.1:.1f}MB"
                    
                    print(f"\n⏰ 預估執行時間: {time_estimate}")
                    print(f"💾 預估結果大小: {size_estimate}")
                    
                    return n_strategies
                else:
                    print("❌ 數量必須在1-10000之間")
                    
            except ValueError:
                print("❌ 請輸入有效的數字")
            except KeyboardInterrupt:
                return None
                
    def get_large_scale_strategy_count(self):
        """獲取大規模策略數量"""
        while True:
            print("\n🚀 大規模模式選項")
            print("=" * 30)
            print("  [1] 1,000個策略   (30-90分鐘)")
            print("  [2] 2,500個策略   (1-3小時)")
            print("  [3] 5,000個策略   (2-6小時)")
            print("  [4] 10,000個策略  (4-12小時)")
            print("  [5] 自定義數量    (1000-50000)")
            print("  [0] 返回")
            
            choice = input("\n請選擇 (0-5): ").strip()
            
            scale_counts = {
                '1': 1000, '2': 2500, '3': 5000, '4': 10000
            }
            
            if choice == '0':
                return None
            elif choice in scale_counts:
                return scale_counts[choice]
            elif choice == '5':
                try:
                    n_strategies = int(input("請輸入策略數量 (1000-50000): "))
                    if 1000 <= n_strategies <= 50000:
                        return n_strategies
                    else:
                        print("❌ 數量必須在1000-50000之間")
                except ValueError:
                    print("❌ 請輸入有效的數字")
            else:
                print("❌ 無效選擇，請重新輸入...")
            
    def confirm_execution(self, mode, n_strategies):
        """執行確認"""
        print("\n" + "=" * 80)
        print("🚀 準備執行")
        print("=" * 80)
        
        time_estimate = self._estimate_time(n_strategies)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if mode == '抽樣模式':
            output_dir = f"results/sampling_{n_strategies}_{timestamp}"
        else:
            output_dir = f"results/full_{n_strategies}_{timestamp}"
        
        print("執行摘要:")
        print(f"  🎲 模式: {mode}")
        
        # 處理大數量的顯示
        if n_strategies >= 1000000:
            print(f"  📊 策略數量: {n_strategies:,}個 (超大規模)")
        elif n_strategies >= 10000:
            print(f"  📊 策略數量: {n_strategies:,}個 (大規模)")
        else:
            print(f"  📊 策略數量: {n_strategies}個")
            
        print(f"  ⏰ 預估時間: {time_estimate}")
        print(f"  📁 輸出目錄: {output_dir}")
        print(f"  🔄 並行數: {self.tuner.config['execution'].get('max_parallel_jobs', 4)}")
        
        # 針對大規模執行的特別警告
        if n_strategies >= 100000:
            print(f"\n⚠️  超大規模執行注意事項:")
            print(f"     - 執行時間可能需要數天")
            print(f"     - 請確保硬碟空間充足 (預估需要 {n_strategies//1000}GB)")
            print(f"     - 建議在穩定的環境中運行")
        elif n_strategies >= 10000:
            print(f"\n⚠️  大規模執行注意事項:")
            print(f"     - 執行時間較長，請耐心等待")
            print(f"     - 建議不要同時運行其他重載程序")
        
        print(f"\n⚠️  執行期間請勿關閉程序")
        
        while True:
            choice = input(f"\n確定要開始執行嗎？\n  [y] 確定執行\n  [n] 取消返回\n  [d] 詳細配置預覽\n\n請輸入選擇 (y/n/d): ").strip().lower()
            
            if choice == 'y':
                return True
            elif choice == 'n':
                return False
            elif choice == 'd':
                self._show_detailed_config()
            else:
                print("❌ 請輸入 y、n 或 d")
                
    def _estimate_time(self, n_strategies):
        """預估執行時間"""
        if n_strategies <= 10:
            return "<1分鐘"
        elif n_strategies <= 50:
            return "1-3分鐘"
        elif n_strategies <= 200:
            return "5-15分鐘"
        elif n_strategies <= 500:
            return "15-45分鐘"
        elif n_strategies <= 1000:
            return "30-90分鐘"
        elif n_strategies <= 2500:
            return "1-3小時"
        elif n_strategies <= 5000:
            return "2-6小時"
        elif n_strategies <= 10000:
            return "4-12小時"
        elif n_strategies <= 50000:
            return "8-24小時"
        elif n_strategies <= 100000:
            return "1-3天"
        else:
            return "數天至數週"
            
    def _show_detailed_config(self):
        """顯示詳細配置"""
        print("\n📋 詳細配置:")
        print(f"  - 配置文件: {self.tuner.config_file}")
        
        exec_config = self.tuner.config['execution']
        print(f"  - 執行模式: {exec_config.get('mode', 'sampling')}")
        print(f"  - 最大並行: {exec_config.get('max_parallel_jobs', 4)}")
        print(f"  - 保存中間結果: {exec_config.get('save_intermediate_results', True)}")
        
        backtest_config = self.tuner.config['backtest']
        print(f"  - 回測開始: {backtest_config.get('start_date', 'N/A')}")
        print(f"  - 回測結束: {backtest_config.get('end_date', 'N/A')}")
        print(f"  - 初始資金: {backtest_config.get('initial_capital', 'N/A')}")
        
    def execute_sampling_mode(self, n_strategies):
        """執行抽樣模式"""
        print(f"\n🎲 開始執行抽樣模式 - {n_strategies}個策略")
        
        try:
            # 臨時修改配置
            original_n = self.tuner.config['execution'].get('n_strategies', 100)
            self.tuner.config['execution']['n_strategies'] = n_strategies
            
            # 執行優化
            summary = self.tuner.run_full_optimization()
            
            # 恢復配置
            self.tuner.config['execution']['n_strategies'] = original_n
            
            input(f"\n✅ 抽樣模式執行完成！按Enter返回主選單...")
            
        except KeyboardInterrupt:
            print(f"\n❌ 用戶中斷執行")
            input("按Enter返回主選單...")
        except Exception as e:
            print(f"\n❌ 執行失敗: {str(e)}")
            input("按Enter返回主選單...")
            
    def execute_exhaustive_mode(self):
        """執行全測模式"""
        print(f"\n🎯 開始執行全測模式 - 所有可能組合")
        
        try:
            # 臨時修改配置為窮舉模式
            original_mode = self.tuner.config['execution']['mode']
            self.tuner.config['execution']['mode'] = 'exhaustive'
            
            # 執行優化
            summary = self.tuner.run_full_optimization()
            
            # 恢復配置
            self.tuner.config['execution']['mode'] = original_mode
            
            input(f"\n✅ 全測模式執行完成！按Enter返回主選單...")
            
        except KeyboardInterrupt:
            print(f"\n❌ 用戶中斷執行")
            input("按Enter返回主選單...")
        except Exception as e:
            print(f"\n❌ 執行失敗: {str(e)}")
            input("按Enter返回主選單...")
            

            
    def show_config_modification_menu(self):
        """顯示配置修改選單"""
        # 簡化實現，留待後續擴展
        print("\n📝 配置修改功能開發中...")
        input("按Enter返回...")
        
    def show_preset_config_menu(self):
        """顯示預設配置選單"""
        # 簡化實現，留待後續擴展
        print("\n📋 預設配置功能開發中...")
        input("按Enter返回...")


class HyperparameterTuner:
    """超參數調優主控制器"""
    
    def __init__(self, config_file: str = 'config.yaml'):
        """
        初始化調優器
        :param config_file: 配置文件路徑
        """
        self.config_file = config_file
        self.config = self._load_config()
        
        # 創建輸出目錄
        self.output_dir = self._create_output_directory()
        
        # 初始化各模組
        self.param_generator = ParameterGenerator(self.config)
        self.batch_runner = BatchRunner(self.config, self.output_dir)
        self.result_analyzer = ResultAnalyzer(self.config, self.output_dir)
        
        # 運行狀態
        self.generated_strategies = []
        self.execution_results = []
        
    def _load_config(self) -> Dict[str, Any]:
        """載入配置文件"""
        config_path = os.path.join(current_dir, self.config_file)
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print(f"✅ 配置文件載入成功: {config_path}")
        return config
    
    def _create_output_directory(self) -> str:
        """創建輸出目錄"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if self.config['execution']['mode'] == 'exhaustive':
            output_dir = f"results/exhaustive_{timestamp}"
        else:
            n_strategies = self.config['execution']['n_strategies']
            output_dir = f"results/sampling_{n_strategies}_{timestamp}"
        
        output_path = os.path.join(current_dir, output_dir)
        os.makedirs(output_path, exist_ok=True)
        
        print(f"📁 輸出目錄已創建: {output_path}")
        return output_path
    
    def run_full_optimization(self) -> Dict[str, Any]:
        """運行完整的超參數調優流程"""
        print("\n" + "=" * 80)
        print("🚀 超參數調優系統啟動")
        print("=" * 80)
        
        start_time = time.time()
        
        try:
            # 第1步：生成策略配置
            print("\n📝 第1步：生成策略配置...")
            self._generate_strategies()
            
            # 第2步：批量執行回測
            print("\n🔄 第2步：批量執行回測...")
            execution_stats = self._execute_batch_backtest()
            
            # 第3步：分析結果
            print("\n📊 第3步：分析結果...")
            analysis_results = self._analyze_results()
            
            # 第4步：生成報告
            print("\n📋 第4步：生成報告...")
            report_files = self._generate_reports()
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # 最終總結
            final_summary = {
                'execution_summary': execution_stats,
                'analysis_results': analysis_results,
                'report_files': report_files,
                'total_execution_time': total_time,
                'output_directory': self.output_dir
            }
            
            self._print_final_summary(final_summary)
            
            return final_summary
            
        except Exception as e:
            print(f"❌ 運行過程中發生錯誤: {str(e)}")
            raise
    
    def _generate_strategies(self):
        """生成策略配置"""
        # 顯示參數空間信息
        space_info = self.param_generator.get_space_info()
        print("📊 參數空間信息:")
        for key, value in space_info.items():
            print(f"  - {key}: {value}")
        
        # 生成策略配置
        if self.config['execution']['mode'] == 'exhaustive':
            print(f"🎯 窮舉模式: 將生成所有 {space_info['total_combinations']} 個策略配置")
            self.generated_strategies = self.param_generator.generate_all_combinations()
            
        else:
            n_strategies = self.config['execution']['n_strategies']
            print(f"🎲 抽樣模式: 從 {space_info['total_combinations']} 個組合中隨機選擇 {n_strategies} 個")
            self.generated_strategies = self.param_generator.generate_sample_combinations(n_strategies)
        
        print(f"✅ 成功生成 {len(self.generated_strategies)} 個策略配置")
        
        # 顯示前3個策略示例
        print("\n📋 策略配置示例:")
        for i, strategy in enumerate(self.generated_strategies[:3]):
            print(f"\n策略 {i+1}: {strategy['strategy_id']}")
            print(f"  - 因子: {[f['function'] for f in strategy['factors']]}")
            print(f"  - 窗口: {strategy['factors'][0]['window']}")
            print(f"  - 輸入列: {strategy['factors'][0]['input_column']}")
    
    def _execute_batch_backtest(self) -> Dict[str, Any]:
        """執行批量回測"""
        if not self.generated_strategies:
            raise ValueError("沒有可執行的策略配置")
        
        print(f"🚀 開始批量回測 {len(self.generated_strategies)} 個策略...")
        
        # 執行批量回測
        execution_stats = self.batch_runner.run_batch_backtest(self.generated_strategies)
        
        # 獲取結果
        self.execution_results = self.batch_runner.get_results()
        
        return execution_stats
    
    def _analyze_results(self) -> Dict[str, Any]:
        """分析結果"""
        if not self.execution_results:
            print("⚠️  沒有可分析的執行結果")
            return {}
        
        print(f"📊 開始分析 {len(self.execution_results)} 個策略結果...")
        
        # 載入結果數據
        results_df = self.result_analyzer.load_results(self.execution_results)
        
        # 分析頂級策略
        top_n = self.config['output'].get('top_n_strategies', 20)
        top_strategies = self.result_analyzer.analyze_top_strategies(top_n)
        
        # 分析參數重要性
        parameter_importance = self.result_analyzer.analyze_parameter_importance()
        
        analysis_results = {
            'total_analyzed': len(results_df),
            'top_strategies_count': len(top_strategies),
            'parameter_importance': parameter_importance
        }
        
        return analysis_results
    
    def _generate_reports(self) -> List[str]:
        """生成報告"""
        report_files = []
        
        # 生成總結報告
        summary_report = self.result_analyzer.generate_summary_report()
        report_files.append(summary_report)
        
        # 保存最終結果
        final_results_file = self.batch_runner.save_final_results()
        report_files.append(final_results_file)
        
        return report_files
    
    def _print_final_summary(self, summary: Dict[str, Any]):
        """打印最終總結"""
        print("\n" + "=" * 80)
        print("🎯 超參數調優完成！")
        print("=" * 80)
        
        # 執行統計
        exec_stats = summary['execution_summary']
        print(f"📊 執行統計:")
        print(f"  - 總策略數: {exec_stats['total_strategies']}")
        print(f"  - 成功執行: {exec_stats['successful']}")
        print(f"  - 執行失敗: {exec_stats['failed']}")
        print(f"  - 成功率: {exec_stats['success_rate']:.1f}%")
        print(f"  - 總耗時: {exec_stats['execution_time_minutes']:.1f} 分鐘")
        
        # 分析結果
        analysis = summary['analysis_results']
        if analysis:
            print(f"\n🔍 分析結果:")
            print(f"  - 分析策略數: {analysis['total_analyzed']}")
            print(f"  - 頂級策略數: {analysis['top_strategies_count']}")
        
        # 輸出文件
        print(f"\n📁 輸出目錄: {summary['output_directory']}")
        print(f"📋 報告文件:")
        for report_file in summary['report_files']:
            print(f"  - {os.path.basename(report_file)}")
        
        print(f"\n⏱️  總耗時: {summary['total_execution_time']/60:.1f} 分鐘")
        print("=" * 80)
    
    def run_sampling_test(self, n_strategies: int = 5):
        """運行抽樣測試"""
        print(f"\n🎲 抽樣測試模式 - 測試 {n_strategies} 個策略")
        
        # 臨時修改配置
        original_mode = self.config['execution']['mode']
        original_n = self.config['execution'].get('n_strategies', 100)
        
        self.config['execution']['mode'] = 'sampling'
        self.config['execution']['n_strategies'] = n_strategies
        
        try:
            # 運行完整流程
            summary = self.run_full_optimization()
            return summary
            
        finally:
            # 恢復原始配置
            self.config['execution']['mode'] = original_mode
            self.config['execution']['n_strategies'] = original_n


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='超參數調優系統')
    parser.add_argument('--config', '-c', default='config.yaml', help='配置文件路徑')
    
    # 向下兼容的舊參數
    parser.add_argument('--test', '-t', action='store_true', help='運行抽樣測試模式（已棄用，請使用 --sampling）')
    parser.add_argument('--test-strategies', '-n', type=int, default=5, help='測試模式下的策略數量（已棄用）')
    
    # 新的參數設計
    parser.add_argument('--sampling', '-s', type=int, metavar='N', help='抽樣模式：隨機抽樣N個策略')
    parser.add_argument('--full', '-f', action='store_true', help='全測模式：完整執行config.yaml設定')
    
    args = parser.parse_args()
    
    try:
        # 創建調優器
        tuner = HyperparameterTuner(args.config)
        
        # 判斷執行模式
        if args.sampling:
            # 新的抽樣模式
            print(f"🎲 抽樣模式啟動 - {args.sampling}個策略")
            summary = tuner.run_sampling_test(args.sampling)
            
        elif args.test:
            # 向下兼容的舊測試模式
            print("⚠️  注意: --test 參數已棄用，請使用 --sampling")
            print(f"舊: python main.py --test --test-strategies {args.test_strategies}")
            print(f"新: python main.py --sampling {args.test_strategies}")
            print(f"\n🎲 抽樣模式啟動 - {args.test_strategies}個策略")
            summary = tuner.run_sampling_test(args.test_strategies)
            
        elif args.full:
            # 全測模式
            print("📋 全測模式啟動")
            summary = tuner.run_full_optimization()
            
        elif len(sys.argv) == 1:
            # 無參數時進入互動式模式
            ui = InteractiveUI(tuner)
            ui.show_main_menu()
            return
            
        else:
            # 默認為全測模式
            print("📋 全測模式啟動（默認）")
            summary = tuner.run_full_optimization()
        
        print("\n✅ 程序執行完成！")
        
    except KeyboardInterrupt:
        print("\n❌ 用戶中斷執行")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ 程序執行失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 