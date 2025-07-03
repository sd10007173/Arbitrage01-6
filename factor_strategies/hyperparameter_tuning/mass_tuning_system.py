#!/usr/bin/env python3
"""
大規模超參數調優系統 - 主程序
Mass Hyperparameter Tuning System

按照PRD設計實現的核心系統，支持：
- BR-001: 參數空間窮舉
- BR-002: 真實回測執行  
- BR-003: 大規模處理

新增交互式界面，提供更友好的用戶體驗

Author: System Architect
Version: v2.0
"""

import argparse
import sys
import os
import logging
import time
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from factor_strategies.hyperparameter_tuning.core import (
    ParameterSpaceGenerator,
    BatchExecutionEngine,
    ProgressManager,
    ResultCollector,
    DatabaseManager
)
from factor_strategies.hyperparameter_tuning.config import ConfigManager

class MassTuningSystem:
    """大規模超參數調優系統主類"""
    
    def __init__(self, config_path: str = None):
        """初始化系統"""
        self.config_manager = ConfigManager(config_path)
        self.db_manager = DatabaseManager()
        self.progress_manager = ProgressManager(self.db_manager)
        self.param_generator = ParameterSpaceGenerator(self.config_manager)
        self.execution_engine = BatchExecutionEngine(
            self.db_manager, 
            self.progress_manager,
            self.config_manager
        )
        self.result_collector = ResultCollector(self.db_manager)
        
        # 設置日誌
        self._setup_logging()
        
    def _setup_logging(self):
        """設置日誌系統"""
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"mass_tuning_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("大規模超參數調優系統初始化完成")
        
    def generate_strategies(self, mode: str = "sampling", size: Optional[int] = None) -> str:
        """
        生成策略參數組合 (BR-001)
        
        Args:
            mode: "exhaustive" 或 "sampling"
            size: 抽樣數量（sampling模式下使用）
            
        Returns:
            session_id: 會話ID
        """
        self.logger.info(f"開始生成策略參數組合 - 模式: {mode}")
        
        try:
            # 生成參數組合
            strategies = self.param_generator.generate_strategies(mode=mode, size=size)
            
            # 創建會話
            session_id = self.progress_manager.create_session(
                mode=mode,
                total_strategies=len(strategies)
            )
            
            # 保存到策略隊列
            self.progress_manager.add_strategies_to_queue(session_id, strategies)
            
            self.logger.info(f"成功生成 {len(strategies)} 個策略配置")
            self.logger.info(f"會話ID: {session_id}")
            
            return session_id
            
        except Exception as e:
            self.logger.error(f"生成策略參數組合失敗: {e}")
            raise
            
    def execute_strategies(self, session_id: str = None, parallel: int = 4, 
                          resume: bool = False) -> bool:
        """
        執行批量真實回測 (BR-002, BR-003)
        
        Args:
            session_id: 會話ID，為空則使用最新會話
            parallel: 並發數量
            resume: 是否斷點續跑
            
        Returns:
            執行是否成功
        """
        try:
            if not session_id:
                session_id = self.progress_manager.get_latest_session()
                if not session_id:
                    raise ValueError("沒有找到可執行的會話")
                    
            self.logger.info(f"開始執行批量回測 - 會話: {session_id}, 並發: {parallel}")
            
            # 執行策略
            success = self.execution_engine.execute_batch(
                session_id=session_id,
                parallel_count=parallel,
                resume=resume
            )
            
            if success:
                self.logger.info("批量回測執行完成")
            else:
                self.logger.error("批量回測執行失敗")
                
            return success
            
        except Exception as e:
            self.logger.error(f"執行批量回測失敗: {e}")
            raise
            
    def get_status(self, session_id: str = None, detailed: bool = False) -> Dict[str, Any]:
        """查看執行狀態"""
        try:
            if not session_id:
                session_id = self.progress_manager.get_latest_session()
                
            if not session_id:
                return {"error": "沒有找到會話"}
                
            status = self.progress_manager.get_session_status(session_id, detailed)
            return status
            
        except Exception as e:
            self.logger.error(f"獲取狀態失敗: {e}")
            return {"error": str(e)}
            
    def clean_data(self, session_id: str = None, failed_only: bool = False) -> bool:
        """清理數據"""
        try:
            if not session_id:
                self.logger.info("清理所有數據")
                return self.db_manager.clean_all_data(failed_only)
            else:
                self.logger.info(f"清理會話數據: {session_id}")
                return self.db_manager.clean_session_data(session_id, failed_only)
                
        except Exception as e:
            self.logger.error(f"清理數據失敗: {e}")
            return False


class MassTuningInteractiveUI:
    """大規模超參數調優系統交互界面"""
    
    def __init__(self, system: MassTuningSystem):
        self.system = system
        self.logger = logging.getLogger(__name__)
        
    def show_main_menu(self):
        """顯示主選單"""
        while True:
            try:
                # 清屏
                self._clear_screen()
                
                # 顯示系統狀態
                self._show_system_header()
                
                print("\n請選擇功能模塊:\n")
                print("  🎲 [1] 策略生成  - 生成參數組合（抽樣/窮舉）")
                print("  🚀 [2] 批量執行  - 執行真實回測")
                print("  📊 [3] 進度監控  - 查看執行狀態和結果")
                print("  🗂️  [4] 數據管理  - 會話管理和數據清理")
                print("  ⚙️  [5] 系統設置  - 配置查看和環境檢查")
                print("  🚪 [6] 退出系統")
                
                choice = input("\n請輸入選擇 (1-6): ").strip()
                
                if choice == '1':
                    self.show_generation_menu()
                elif choice == '2':
                    self.show_execution_menu()
                elif choice == '3':
                    self.show_monitoring_menu()
                elif choice == '4':
                    self.show_management_menu()
                elif choice == '5':
                    self.show_settings_menu()
                elif choice == '6':
                    print("\n👋 感謝使用大規模超參數調優系統！")
                    return
                else:
                    self._show_error("無效選擇，請重新輸入...")
                    self._wait_for_enter()
                    
            except KeyboardInterrupt:
                print("\n\n👋 用戶中斷，退出系統")
                return
            except Exception as e:
                self._show_error(f"系統錯誤: {e}")
                self._wait_for_enter()
                
    def show_generation_menu(self):
        """顯示策略生成選單"""
        while True:
            try:
                self._clear_screen()
                print("🎲 策略生成")
                print("=" * 80)
                
                # 獲取參數空間信息
                param_info = self.system.param_generator.get_parameter_space_info()
                total_combinations = param_info['total_combinations']
                print(f"從 {total_combinations:,} 個策略組合中生成執行計劃\n")
                
                print("🚀 快速生成:")
                print("  [1] 小規模測試     (10個策略, <1分鐘)")
                print("  [2] 中等規模       (100個策略, 5-15分鐘)")
                print("  [3] 大規模抽樣     (1,000個策略, 30-90分鐘)")
                print("  [4] 超大規模       (10,000個策略, 4-12小時)\n")
                
                print("🎯 生成模式:")
                print("  [5] 隨機抽樣       - 完全隨機選擇")
                print("  [6] 智能抽樣       - 拉丁超立方/Sobol序列")
                print("  [7] 網格抽樣       - 均勻網格分佈")
                print(f"  [8] 窮舉模式       - 所有可能組合 (⚠️ {total_combinations:,}個)\n")
                
                print("📋 其他選項:")
                print("  [9] 自定義數量     - 指定任意數量")
                print("  [0] 返回主選單")
                
                choice = input("\n請輸入選擇 (0-9): ").strip()
                
                if choice == '0':
                    return
                elif choice == '1':
                    self._execute_generation("sampling", 10, "random")
                elif choice == '2':
                    self._execute_generation("sampling", 100, "random")
                elif choice == '3':
                    self._execute_generation("sampling", 1000, "random")
                elif choice == '4':
                    self._execute_generation("sampling", 10000, "random")
                elif choice == '5':
                    size = self._get_custom_size()
                    if size:
                        self._execute_generation("sampling", size, "random")
                elif choice == '6':
                    size = self._get_custom_size()
                    if size:
                        self._execute_generation("sampling", size, "lhs")
                elif choice == '7':
                    size = self._get_custom_size()
                    if size:
                        self._execute_generation("sampling", size, "grid")
                elif choice == '8':
                    if self._confirm_exhaustive_mode(total_combinations):
                        self._execute_generation("exhaustive", None, None)
                elif choice == '9':
                    size = self._get_custom_size()
                    if size:
                        method = self._select_generation_method()
                        self._execute_generation("sampling", size, method)
                else:
                    self._show_error("無效選擇，請重新輸入...")
                    self._wait_for_enter()
                    
            except KeyboardInterrupt:
                return
            except Exception as e:
                self._show_error(f"操作失敗: {e}")
                self._wait_for_enter()
                
    def show_execution_menu(self):
        """顯示執行控制選單"""
        while True:
            try:
                self._clear_screen()
                print("🚀 批量執行")
                print("=" * 80)
                
                # 獲取會話列表
                sessions = self._get_executable_sessions()
                
                if not sessions:
                    print("暫無可執行的會話")
                    print("\n[g] 先生成策略  [0] 返回主選單")
                    choice = input("\n請輸入選擇: ").strip().lower()
                    if choice == 'g':
                        self.show_generation_menu()
                        continue
                    elif choice == '0':
                        return
                    continue
                
                # 顯示可執行會話
                print(f"📋 可執行會話: {len(sessions)} 個")
                for i, session in enumerate(sessions[:5]):  # 只顯示前5個
                    status_icon = self._get_status_icon(session['status'])
                    print(f"├─ [{i+1}] {status_icon} {session['session_id']}: {session['total_strategies']}個策略 ({session['status']})")
                
                if len(sessions) > 5:
                    print(f"└─ ... 還有 {len(sessions)-5} 個會話")
                
                print(f"\n執行選項:")
                print(f"  [1] 執行最新會話   - {sessions[0]['session_id']}")
                print(f"  [2] 選擇會話執行   - 從列表中選擇")
                print(f"  [3] 斷點續跑       - 繼續中斷的執行")
                print(f"  [4] 批量執行設置   - 調整並發數/超時等\n")
                
                print(f"監控選項:")
                print(f"  [5] 實時監控       - 查看執行進度")
                print(f"  [6] 執行日誌       - 查看詳細日誌")
                print(f"  [0] 返回主選單")
                
                choice = input("\n請輸入選擇 (0-6): ").strip()
                
                if choice == '0':
                    return
                elif choice == '1':
                    self._execute_session(sessions[0]['session_id'])
                elif choice == '2':
                    session_id = self._select_session_from_list(sessions)
                    if session_id:
                        self._execute_session(session_id)
                elif choice == '3':
                    self._resume_execution()
                elif choice == '4':
                    self._show_execution_settings()
                elif choice == '5':
                    self._show_live_monitoring()
                elif choice == '6':
                    self._show_execution_logs()
                else:
                    self._show_error("無效選擇，請重新輸入...")
                    self._wait_for_enter()
                    
            except KeyboardInterrupt:
                return
            except Exception as e:
                self._show_error(f"操作失敗: {e}")
                self._wait_for_enter()
                
    def show_monitoring_menu(self):
        """顯示監控選單"""
        while True:
            try:
                self._clear_screen()
                print("📊 進度監控")
                print("=" * 80)
                
                # 獲取所有會話狀態
                sessions = self._get_all_sessions_status()
                
                if not sessions:
                    print("暫無會話記錄")
                    self._wait_for_enter()
                    return
                
                # 顯示會話狀態總覽
                print("📋 會話狀態總覽:\n")
                for i, session in enumerate(sessions[:10]):  # 顯示前10個
                    status_icon = self._get_status_icon(session['status'])
                    progress = session.get('progress_percent', 0)
                    print(f"  [{i+1}] {status_icon} {session['session_id']}")
                    print(f"      📊 進度: {progress:.1f}% ({session['completed_strategies']}/{session['total_strategies']})")
                    print(f"      📅 創建: {session['created_at']}")
                
                print(f"\n監控選項:")
                print(f"  [詳情] 輸入會話編號查看詳情")
                print(f"  [live] 實時監控最新會話")
                print(f"  [summary] 執行總結報表")
                print(f"  [export] 導出結果數據")
                print(f"  [0] 返回主選單")
                
                choice = input("\n請輸入選擇: ").strip().lower()
                
                if choice == '0':
                    return
                elif choice == 'live':
                    self._show_live_monitoring()
                elif choice == 'summary':
                    self._show_execution_summary()
                elif choice == 'export':
                    self._export_results()
                elif choice.isdigit() and 1 <= int(choice) <= min(10, len(sessions)):
                    session_id = sessions[int(choice)-1]['session_id']
                    self._show_session_details(session_id)
                else:
                    self._show_error("無效選擇，請重新輸入...")
                    self._wait_for_enter()
                    
            except KeyboardInterrupt:
                return
            except Exception as e:
                self._show_error(f"操作失敗: {e}")
                self._wait_for_enter()
                
    def show_management_menu(self):
        """顯示數據管理選單"""
        while True:
            try:
                self._clear_screen()
                print("🗂️ 數據管理")
                print("=" * 80)
                
                # 獲取數據庫統計信息
                stats = self._get_database_stats()
                
                print("📊 數據庫統計:")
                print(f"  - 總會話數: {stats.get('total_sessions', 0)}")
                print(f"  - 活躍會話: {stats.get('active_sessions', 0)}")
                print(f"  - 完成會話: {stats.get('completed_sessions', 0)}")
                print(f"  - 失敗策略: {stats.get('failed_strategies', 0)}")
                print(f"  - 數據庫大小: {stats.get('db_size', 'N/A')}")
                
                print(f"\n管理選項:")
                print(f"  [1] 會話管理       - 查看和管理會話")
                print(f"  [2] 清理失敗記錄   - 清理失敗的策略記錄")
                print(f"  [3] 清理完成會話   - 清理已完成的會話")
                print(f"  [4] 數據庫維護     - 優化和壓縮數據庫")
                print(f"  [5] 備份數據       - 備份重要數據")
                print(f"  [0] 返回主選單")
                
                choice = input("\n請輸入選擇 (0-5): ").strip()
                
                if choice == '0':
                    return
                elif choice == '1':
                    self._show_session_management()
                elif choice == '2':
                    self._clean_failed_records()
                elif choice == '3':
                    self._clean_completed_sessions()
                elif choice == '4':
                    self._database_maintenance()
                elif choice == '5':
                    self._backup_data()
                else:
                    self._show_error("無效選擇，請重新輸入...")
                    self._wait_for_enter()
                    
            except KeyboardInterrupt:
                return
            except Exception as e:
                self._show_error(f"操作失敗: {e}")
                self._wait_for_enter()
                
    def show_settings_menu(self):
        """顯示系統設置選單"""
        while True:
            try:
                self._clear_screen()
                print("⚙️ 系統設置")
                print("=" * 80)
                
                # 顯示當前配置
                self._show_current_config()
                
                print(f"\n設置選項:")
                print(f"  [1] 查看完整配置   - 顯示所有配置參數")
                print(f"  [2] 環境檢查       - 檢查執行環境")
                print(f"  [3] 參數空間信息   - 查看參數空間詳情")
                print(f"  [4] 執行設置       - 調整並發數等")
                print(f"  [5] 日誌管理       - 查看和管理日誌")
                print(f"  [0] 返回主選單")
                
                choice = input("\n請輸入選擇 (0-5): ").strip()
                
                if choice == '0':
                    return
                elif choice == '1':
                    self._show_full_config()
                elif choice == '2':
                    self._check_environment()
                elif choice == '3':
                    self._show_parameter_space_info()
                elif choice == '4':
                    self._modify_execution_settings()
                elif choice == '5':
                    self._show_log_management()
                else:
                    self._show_error("無效選擇，請重新輸入...")
                    self._wait_for_enter()
                    
            except KeyboardInterrupt:
                return
            except Exception as e:
                self._show_error(f"操作失敗: {e}")
                self._wait_for_enter()
    
    # ========== 輔助方法實現 ==========
    
    def _clear_screen(self):
        """清屏"""
        try:
            # 設置 TERM 環境變量以避免警告
            if os.name == 'posix' and 'TERM' not in os.environ:
                os.environ['TERM'] = 'xterm'
            os.system('clear' if os.name == 'posix' else 'cls')
        except:
            # 如果清屏失敗，使用簡單的換行代替
            print('\n' * 50)
        
    def _show_error(self, message: str):
        """顯示錯誤信息"""
        print(f"\n❌ {message}")
        
    def _wait_for_enter(self):
        """等待用戶按Enter"""
        input("\n按Enter繼續...")
        
    def _show_system_header(self):
        """顯示系統頭部信息"""
        print("🎯 大規模超參數調優系統")
        print("=" * 80)
        
        try:
            # 環境檢查
            env_check = self.system.execution_engine.validate_environment()
            env_status = "✅ 通過" if env_check['valid'] else "⚠️ 有問題"
            
            # 參數空間信息
            param_info = self.system.param_generator.get_parameter_space_info()
            total_combinations = param_info['total_combinations']
            
            print(f"✅ 環境檢查: {env_status}")
            print(f"📊 參數空間: {total_combinations:,} 個策略組合")
            print(f"📁 配置文件: {self.system.config_manager.config_path}")
            
        except Exception as e:
            print(f"⚠️ 系統狀態檢查失敗: {e}")
            
    def _execute_generation(self, mode: str, size: Optional[int], method: Optional[str]):
        """執行策略生成"""
        try:
            print(f"\n🎲 開始生成策略...")
            print(f"模式: {mode}, 數量: {size or '全部'}, 方法: {method or '默認'}")
            
            if not self._confirm_generation(mode, size):
                return
                
            print("\n⏳ 正在生成策略參數組合...")
            session_id = self.system.generate_strategies(mode=mode, size=size)
            
            print(f"✅ 策略生成完成！")
            print(f"📋 會話ID: {session_id}")
            
            # 詢問是否立即執行
            if input("\n是否立即執行這些策略？(y/n): ").lower() == 'y':
                self._execute_session(session_id)
            else:
                self._wait_for_enter()
                
        except Exception as e:
            self._show_error(f"生成策略失敗: {e}")
            self._wait_for_enter()
            
    def _confirm_generation(self, mode: str, size: Optional[int]) -> bool:
        """確認策略生成"""
        time_estimate = self._estimate_time(size or 1000000)
        
        print(f"\n🚀 準備生成策略")
        print("=" * 40)
        print(f"模式: {mode}")
        print(f"數量: {size or '全部'}")
        print(f"預估時間: {time_estimate}")
        
        if size and size >= 100000:
            print(f"\n⚠️ 超大規模生成注意事項:")
            print(f"   - 生成時間較長，請耐心等待")
            print(f"   - 將消耗較多系統資源")
            
        choice = input(f"\n確定要開始生成嗎？(y/n): ").lower()
        return choice == 'y'
        
    def _estimate_time(self, n_strategies: int) -> str:
        """預估執行時間"""
        if n_strategies <= 10:
            return "<1分鐘"
        elif n_strategies <= 100:
            return "1-5分鐘"
        elif n_strategies <= 1000:
            return "30-90分鐘"
        elif n_strategies <= 10000:
            return "4-12小時"
        elif n_strategies <= 100000:
            return "1-3天"
        else:
            return "數天至數週"
            
    def _get_custom_size(self) -> Optional[int]:
        """獲取自定義數量"""
        try:
            size = int(input("請輸入策略數量: "))
            if size <= 0:
                self._show_error("數量必須大於0")
                return None
            return size
        except ValueError:
            self._show_error("請輸入有效的數字")
            return None
            
    def _select_generation_method(self) -> str:
        """選擇生成方法"""
        print("\n選擇生成方法:")
        print("  [1] random - 隨機抽樣")
        print("  [2] lhs - 拉丁超立方")
        print("  [3] grid - 網格抽樣")
        
        choice = input("請選擇 (1-3): ").strip()
        methods = {'1': 'random', '2': 'lhs', '3': 'grid'}
        return methods.get(choice, 'random')
        
    def _confirm_exhaustive_mode(self, total_combinations: int) -> bool:
        """確認窮舉模式"""
        print(f"\n⚠️ 窮舉模式確認")
        print("=" * 40)
        print(f"將生成所有 {total_combinations:,} 個策略組合")
        print(f"預估執行時間: 數天至數週")
        print(f"請確保有足夠的存儲空間和時間")
        
        choice = input(f"\n確定要使用窮舉模式嗎？(y/n): ").lower()
        return choice == 'y'
        
    def _execute_session(self, session_id: str):
        """執行會話"""
        try:
            print(f"\n🚀 開始執行會話: {session_id}")
            
            # 獲取並發數
            parallel = self._get_parallel_count()
            
            print(f"⏳ 正在執行批量回測...")
            success = self.system.execute_strategies(
                session_id=session_id,
                parallel=parallel,
                resume=False
            )
            
            if success:
                print(f"✅ 批量回測執行完成！")
            else:
                print(f"❌ 批量回測執行失敗")
                
            self._wait_for_enter()
            
        except Exception as e:
            self._show_error(f"執行失敗: {e}")
            self._wait_for_enter()
            
    def _get_parallel_count(self) -> int:
        """獲取並發數"""
        try:
            default_parallel = self.system.config_manager.get_system_config().max_parallel
            parallel = input(f"請輸入並發數 (默認: {default_parallel}): ").strip()
            return int(parallel) if parallel else default_parallel
        except ValueError:
            return 4
            
    # 簡化的選單方法實現
    def show_execution_menu(self):
        """執行控制選單 - 簡化版"""
        self._clear_screen()
        print("🚀 批量執行")
        print("=" * 80)
        print("執行控制功能開發中...")
        
        # 獲取最新會話
        try:
            latest_session = self.system.progress_manager.get_latest_session()
            if latest_session:
                print(f"發現最新會話: {latest_session}")
                if input("是否執行此會話？(y/n): ").lower() == 'y':
                    self._execute_session(latest_session)
            else:
                print("沒有找到可執行的會話")
        except Exception as e:
            self._show_error(f"獲取會話失敗: {e}")
            
        self._wait_for_enter()
        
    def show_monitoring_menu(self):
        """監控選單 - 簡化版"""
        self._clear_screen()
        print("📊 進度監控")
        print("=" * 80)
        
        try:
            # 獲取最新會話狀態
            latest_session = self.system.progress_manager.get_latest_session()
            if latest_session:
                status = self.system.get_status(latest_session, detailed=True)
                print("最新會話狀態:")
                for key, value in status.items():
                    print(f"  {key}: {value}")
            else:
                print("沒有找到會話記錄")
        except Exception as e:
            self._show_error(f"獲取狀態失敗: {e}")
            
        self._wait_for_enter()
        
    def show_management_menu(self):
        """數據管理選單 - 簡化版"""
        self._clear_screen()
        print("🗂️ 數據管理")
        print("=" * 80)
        
        print("管理選項:")
        print("  [1] 清理失敗記錄")
        print("  [2] 清理所有數據")
        print("  [0] 返回主選單")
        
        choice = input("\n請選擇 (0-2): ").strip()
        
        if choice == '1':
            if input("確定要清理失敗記錄嗎？(y/n): ").lower() == 'y':
                success = self.system.clean_data(failed_only=True)
                if success:
                    print("✅ 清理完成")
                else:
                    print("❌ 清理失敗")
        elif choice == '2':
            if input("⚠️ 確定要清理所有數據嗎？(y/n): ").lower() == 'y':
                success = self.system.clean_data(failed_only=False)
                if success:
                    print("✅ 清理完成")
                else:
                    print("❌ 清理失敗")
                    
        if choice != '0':
            self._wait_for_enter()
            
    def show_settings_menu(self):
        """系統設置選單 - 簡化版"""
        self._clear_screen()
        print("⚙️ 系統設置")
        print("=" * 80)
        
        try:
            # 顯示當前配置
            config = self.system.config_manager.get_system_config()
            print("當前配置:")
            print(f"  - 數據庫路徑: {config.database_path}")
            print(f"  - 最大並發: {config.max_parallel}")
            print(f"  - 超時時間: {config.timeout_minutes} 分鐘")
            
            # 參數空間信息
            param_info = self.system.param_generator.get_parameter_space_info()
            print(f"\n參數空間信息:")
            print(f"  - 參數數量: {param_info['parameter_count']}")
            print(f"  - 總組合數: {param_info['total_combinations']:,}")
            
        except Exception as e:
            self._show_error(f"獲取配置失敗: {e}")
            
        self._wait_for_enter()


def handle_command_line_mode(system: MassTuningSystem, args):
    """處理命令行模式"""
    try:
        command = args.command or args.subcommand
        if command == 'generate':
            session_id = system.generate_strategies(
                mode=args.mode,
                size=args.size
            )
            print(f"✅ 策略生成完成，會話ID: {session_id}")
            
        elif command == 'execute':
            success = system.execute_strategies(
                session_id=getattr(args, 'session', None),
                parallel=args.parallel,
                resume=args.resume
            )
            if success:
                print("✅ 批量回測執行完成")
            else:
                print("❌ 批量回測執行失敗")
                sys.exit(1)
                
        elif command == 'status':
            status = system.get_status(
                session_id=getattr(args, 'session', None),
                detailed=args.detailed
            )
            print("📊 執行狀態:")
            for key, value in status.items():
                print(f"  {key}: {value}")
                
        elif command == 'clean':
            success = system.clean_data(
                session_id=getattr(args, 'session', None),
                failed_only=args.failed_only
            )
            if success:
                print("✅ 數據清理完成")
            else:
                print("❌ 數據清理失敗")
                sys.exit(1)
                
    except Exception as e:
        print(f"❌ 系統錯誤: {e}")
        sys.exit(1)


def main():
    """主程序入口 - 支持命令行和交互模式"""
    parser = argparse.ArgumentParser(
        description="大規模超參數調優系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令行模式示例:
  # 生成策略參數組合
  python mass_tuning_system.py generate --mode sampling --size 1000
  
  # 執行批量回測
  python mass_tuning_system.py execute --parallel 4 --resume
  
  # 查看執行狀態
  python mass_tuning_system.py status --detailed
  
  # 清理數據
  python mass_tuning_system.py clean --failed_only

交互模式:
  # 直接運行進入交互界面
  python mass_tuning_system.py
        """
    )
    
    parser.add_argument('--config', type=str, default=None, help='配置文件路徑')
    parser.add_argument('command', nargs='?', help='命令: generate/execute/status/clean')
    
    subparsers = parser.add_subparsers(dest='subcommand', help='可用命令')
    
    # generate 命令
    generate_parser = subparsers.add_parser('generate', help='生成參數空間')
    generate_parser.add_argument('--mode', choices=['exhaustive', 'sampling'], 
                               default='sampling', help='生成模式')
    generate_parser.add_argument('--size', type=int, help='抽樣數量 (sampling模式)')
    
    # execute 命令
    execute_parser = subparsers.add_parser('execute', help='執行批量回測')
    execute_parser.add_argument('--session', type=str, help='指定會話ID')
    execute_parser.add_argument('--parallel', type=int, default=4, help='並發數量')
    execute_parser.add_argument('--resume', action='store_true', help='斷點續跑')
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='查看執行狀態')
    status_parser.add_argument('--session', type=str, help='會話ID')
    status_parser.add_argument('--detailed', action='store_true', help='詳細信息')
    
    # clean 命令  
    clean_parser = subparsers.add_parser('clean', help='清理數據')
    clean_parser.add_argument('--session', type=str, help='會話ID')
    clean_parser.add_argument('--failed_only', action='store_true', help='只清理失敗記錄')
    
    args = parser.parse_args()
    
    try:
        # 初始化系統
        system = MassTuningSystem(args.config)
        
        # 判斷執行模式
        if args.command or args.subcommand:
            # 命令行模式 (向下兼容)
            if args.command and not args.subcommand:
                # 處理舊格式: python mass_tuning_system.py generate
                args.subcommand = args.command
            handle_command_line_mode(system, args)
        else:
            # 交互模式 (新功能)
            print("🚀 啟動交互式界面...")
            ui = MassTuningInteractiveUI(system)
            ui.show_main_menu()
            
    except KeyboardInterrupt:
        print("\n❌ 用戶中斷執行")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 系統錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 