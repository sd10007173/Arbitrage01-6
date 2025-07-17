#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邊界測試腳本
自動執行各種邊界條件測試，專門找出潛在問題
"""

import subprocess
import sys
import os
import time
import json
from datetime import datetime
import sqlite3
from setup_test_scenarios import TestScenarioSetup

class BoundaryTestRunner:
    def __init__(self):
        self.test_results = []
        self.setup = TestScenarioSetup()
        
    def run_command(self, cmd, timeout=300):
        """運行命令並捕獲輸出"""
        print(f"🚀 執行命令: {cmd}")
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            return {
                'command': cmd,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'execution_time': execution_time,
                'success': result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                'command': cmd,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Command timed out',
                'execution_time': timeout,
                'success': False
            }
        except Exception as e:
            return {
                'command': cmd,
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'execution_time': 0,
                'success': False
            }
    
    def test_calculate_fr_return_list_v3(self, test_name, scenario_setup_func=None):
        """測試 calculate_FR_return_list_v3.py 的邊界條件"""
        print(f"\n🧪 測試: {test_name}")
        print("=" * 50)
        
        # 設置測試場景
        if scenario_setup_func:
            scenario_setup_func()
            
        test_cases = []
        
        # 測試案例1: 基本執行
        test_cases.append({
            'name': f'{test_name}_basic',
            'command': 'python calculate_FR_return_list_v3.py'
        })
        
        # 測試案例2: 檢查模式
        test_cases.append({
            'name': f'{test_name}_check_only',
            'command': 'python calculate_FR_return_list_v3.py --check-only'
        })
        
        # 測試案例3: 指定日期範圍
        test_cases.append({
            'name': f'{test_name}_date_range',
            'command': 'python calculate_FR_return_list_v3.py --start_date 2025-07-01 --end_date 2025-07-16'
        })
        
        # 測試案例4: 處理最新數據
        test_cases.append({
            'name': f'{test_name}_process_latest',
            'command': 'python calculate_FR_return_list_v3.py --process-latest'
        })
        
        # 測試案例5: 使用遺留模式
        test_cases.append({
            'name': f'{test_name}_legacy',
            'command': 'python calculate_FR_return_list_v3.py --use-legacy'
        })
        
        # 測試案例6: 指定單一交易對
        test_cases.append({
            'name': f'{test_name}_single_pair',
            'command': 'python calculate_FR_return_list_v3.py --symbol BTC_binance_bybit'
        })
        
        # 執行測試
        for test_case in test_cases:
            print(f"\n📋 執行測試案例: {test_case['name']}")
            result = self.run_command(test_case['command'])
            
            # 分析結果
            test_result = {
                'test_name': test_case['name'],
                'category': 'calculate_FR_return_list_v3',
                'scenario': test_name,
                'result': result,
                'analysis': self.analyze_result(result),
                'timestamp': datetime.now().isoformat()
            }
            
            self.test_results.append(test_result)
            self.print_test_result(test_result)
            
    def test_strategy_ranking_v3(self, test_name, scenario_setup_func=None):
        """測試 strategy_ranking_v3.py 的邊界條件"""
        print(f"\n🧪 測試: {test_name}")
        print("=" * 50)
        
        # 設置測試場景
        if scenario_setup_func:
            scenario_setup_func()
            
        test_cases = []
        
        # 測試案例1: 基本執行 - original策略
        test_cases.append({
            'name': f'{test_name}_original_strategy',
            'command': 'echo "1" | python strategy_ranking_v3.py'
        })
        
        # 測試案例2: 檢查模式
        test_cases.append({
            'name': f'{test_name}_check_only',
            'command': 'python strategy_ranking_v3.py --check-only'
        })
        
        # 測試案例3: 指定策略
        test_cases.append({
            'name': f'{test_name}_momentum_strategy',
            'command': 'python strategy_ranking_v3.py --strategies momentum_focused'
        })
        
        # 測試案例4: 指定日期範圍
        test_cases.append({
            'name': f'{test_name}_date_range',
            'command': 'python strategy_ranking_v3.py --start_date 2025-07-01 --end_date 2025-07-16 --strategies original'
        })
        
        # 測試案例5: 使用遺留模式
        test_cases.append({
            'name': f'{test_name}_legacy',
            'command': 'python strategy_ranking_v3.py --use-legacy --strategies original'
        })
        
        # 測試案例6: 指定單一交易對
        test_cases.append({
            'name': f'{test_name}_single_symbol',
            'command': 'python strategy_ranking_v3.py --symbol BTC_binance_bybit --strategies original'
        })
        
        # 測試案例7: 不存在的策略
        test_cases.append({
            'name': f'{test_name}_invalid_strategy',
            'command': 'python strategy_ranking_v3.py --strategies nonexistent_strategy'
        })
        
        # 執行測試
        for test_case in test_cases:
            print(f"\n📋 執行測試案例: {test_case['name']}")
            result = self.run_command(test_case['command'])
            
            # 分析結果
            test_result = {
                'test_name': test_case['name'],
                'category': 'strategy_ranking_v3',
                'scenario': test_name,
                'result': result,
                'analysis': self.analyze_result(result),
                'timestamp': datetime.now().isoformat()
            }
            
            self.test_results.append(test_result)
            self.print_test_result(test_result)
    
    def test_master_controller_v2(self, test_name, scenario_setup_func=None):
        """測試 master_controller_v2.py 的邊界條件"""
        print(f"\n🧪 測試: {test_name}")
        print("=" * 50)
        
        # 設置測試場景
        if scenario_setup_func:
            scenario_setup_func()
            
        test_cases = []
        
        # 測試案例1: 基本執行
        test_cases.append({
            'name': f'{test_name}_basic',
            'command': 'python master_controller_v2.py'
        })
        
        # 測試案例2: 指定top_n
        test_cases.append({
            'name': f'{test_name}_top_n',
            'command': 'python master_controller_v2.py --top_n 3'
        })
        
        # 測試案例3: 使用遺留模式
        test_cases.append({
            'name': f'{test_name}_legacy',
            'command': 'python master_controller_v2.py --use-legacy'
        })
        
        # 測試案例4: 無效的top_n
        test_cases.append({
            'name': f'{test_name}_invalid_top_n',
            'command': 'python master_controller_v2.py --top_n 0'
        })
        
        # 測試案例5: 極大的top_n
        test_cases.append({
            'name': f'{test_name}_large_top_n',
            'command': 'python master_controller_v2.py --top_n 10000'
        })
        
        # 執行測試
        for test_case in test_cases:
            print(f"\n📋 執行測試案例: {test_case['name']}")
            result = self.run_command(test_case['command'])
            
            # 分析結果
            test_result = {
                'test_name': test_case['name'],
                'category': 'master_controller_v2',
                'scenario': test_name,
                'result': result,
                'analysis': self.analyze_result(result),
                'timestamp': datetime.now().isoformat()
            }
            
            self.test_results.append(test_result)
            self.print_test_result(test_result)
    
    def analyze_result(self, result):
        """分析測試結果"""
        analysis = {
            'status': 'PASS' if result['success'] else 'FAIL',
            'issues': [],
            'warnings': [],
            'performance': {
                'execution_time': result['execution_time'],
                'performance_grade': self.grade_performance(result['execution_time'])
            }
        }
        
        # 檢查常見問題
        stderr_lower = result['stderr'].lower()
        stdout_lower = result['stdout'].lower()
        
        # 錯誤檢查
        if 'error' in stderr_lower or 'exception' in stderr_lower:
            analysis['issues'].append('發現錯誤或異常')
            
        if 'traceback' in stderr_lower:
            analysis['issues'].append('發現Python traceback')
            
        if 'timeout' in stderr_lower:
            analysis['issues'].append('命令超時')
            
        if result['returncode'] != 0:
            analysis['issues'].append(f'非零返回碼: {result["returncode"]}')
        
        # 警告檢查
        if 'warning' in stderr_lower or 'warning' in stdout_lower:
            analysis['warnings'].append('發現警告信息')
            
        if result['execution_time'] > 60:
            analysis['warnings'].append('執行時間過長')
            
        if 'null' in stdout_lower and 'score' in stdout_lower:
            analysis['warnings'].append('可能存在NULL分數問題')
            
        if 'failed' in stdout_lower:
            analysis['warnings'].append('部分操作失敗')
        
        return analysis
    
    def grade_performance(self, execution_time):
        """評估性能等級"""
        if execution_time < 10:
            return 'A'
        elif execution_time < 30:
            return 'B'
        elif execution_time < 60:
            return 'C'
        elif execution_time < 120:
            return 'D'
        else:
            return 'F'
    
    def print_test_result(self, test_result):
        """打印測試結果"""
        result = test_result['result']
        analysis = test_result['analysis']
        
        status_emoji = "✅" if analysis['status'] == 'PASS' else "❌"
        print(f"{status_emoji} {test_result['test_name']}: {analysis['status']}")
        print(f"   ⏱️  執行時間: {result['execution_time']:.2f}秒 (等級: {analysis['performance']['performance_grade']})")
        print(f"   🔢 返回碼: {result['returncode']}")
        
        if analysis['issues']:
            print("   🚨 發現問題:")
            for issue in analysis['issues']:
                print(f"      - {issue}")
        
        if analysis['warnings']:
            print("   ⚠️  警告:")
            for warning in analysis['warnings']:
                print(f"      - {warning}")
        
        if result['stderr'] and result['stderr'].strip():
            print(f"   📝 錯誤輸出: {result['stderr'][:200]}...")
    
    def run_all_boundary_tests(self):
        """執行所有邊界測試"""
        print("🚀 開始執行全面邊界測試")
        print("=" * 60)
        
        # 備份數據庫
        self.setup.backup_database()
        
        # 測試場景定義
        test_scenarios = [
            ('空數據場景', self.setup.scenario_1_empty_data),
            ('稀疏數據場景', self.setup.scenario_2_sparse_data),
            ('單日數據場景', self.setup.scenario_3_single_day_data),
            ('數據缺口場景', self.setup.scenario_4_data_gaps),
            ('極端值場景', self.setup.scenario_5_extreme_values),
            ('NULL值場景', self.setup.scenario_6_null_values),
            ('相同值場景', self.setup.scenario_7_identical_values),
            ('單交易對場景', self.setup.scenario_8_single_trading_pair),
        ]
        
        # 對每個場景執行測試
        for scenario_name, scenario_func in test_scenarios:
            print(f"\n{'='*60}")
            print(f"🎯 測試場景: {scenario_name}")
            print(f"{'='*60}")
            
            try:
                # 恢復原始數據
                self.setup.restore_database()
                
                # 測試 calculate_FR_return_list_v3
                self.test_calculate_fr_return_list_v3(scenario_name, scenario_func)
                
                # 恢復原始數據
                self.setup.restore_database()
                
                # 測試 strategy_ranking_v3
                self.test_strategy_ranking_v3(scenario_name, scenario_func)
                
                # 恢復原始數據
                self.setup.restore_database()
                
                # 測試 master_controller_v2
                self.test_master_controller_v2(scenario_name, scenario_func)
                
            except Exception as e:
                print(f"❌ 場景 {scenario_name} 測試失敗: {e}")
                
        # 恢復原始數據
        self.setup.restore_database()
        
        # 生成最終報告
        self.generate_final_report()
    
    def generate_final_report(self):
        """生成最終測試報告"""
        print("\n" + "="*60)
        print("📊 最終測試報告")
        print("="*60)
        
        # 統計結果
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['analysis']['status'] == 'PASS')
        failed_tests = total_tests - passed_tests
        
        print(f"📈 測試統計:")
        print(f"   總測試數: {total_tests}")
        print(f"   通過: {passed_tests}")
        print(f"   失敗: {failed_tests}")
        print(f"   成功率: {passed_tests/total_tests*100:.1f}%")
        
        # 按類別統計
        categories = {}
        for result in self.test_results:
            category = result['category']
            if category not in categories:
                categories[category] = {'total': 0, 'passed': 0}
            categories[category]['total'] += 1
            if result['analysis']['status'] == 'PASS':
                categories[category]['passed'] += 1
        
        print(f"\n📋 按程序統計:")
        for category, stats in categories.items():
            success_rate = stats['passed'] / stats['total'] * 100
            print(f"   {category}: {stats['passed']}/{stats['total']} ({success_rate:.1f}%)")
        
        # 發現的問題
        all_issues = []
        for result in self.test_results:
            if result['analysis']['issues']:
                all_issues.extend(result['analysis']['issues'])
        
        if all_issues:
            print(f"\n🚨 發現的問題類型:")
            issue_counts = {}
            for issue in all_issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            
            for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"   {issue}: {count} 次")
        
        # 性能分析
        execution_times = [r['result']['execution_time'] for r in self.test_results]
        if execution_times:
            avg_time = sum(execution_times) / len(execution_times)
            max_time = max(execution_times)
            min_time = min(execution_times)
            
            print(f"\n⏱️  性能分析:")
            print(f"   平均執行時間: {avg_time:.2f}秒")
            print(f"   最長執行時間: {max_time:.2f}秒")
            print(f"   最短執行時間: {min_time:.2f}秒")
        
        # 保存詳細報告
        report_file = f"boundary_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'failed_tests': failed_tests,
                    'success_rate': passed_tests/total_tests*100,
                    'categories': categories,
                    'performance': {
                        'avg_time': avg_time if execution_times else 0,
                        'max_time': max_time if execution_times else 0,
                        'min_time': min_time if execution_times else 0
                    }
                },
                'detailed_results': self.test_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 詳細報告已保存: {report_file}")
        
        # 推薦修復建議
        print(f"\n🔧 修復建議:")
        if failed_tests > 0:
            print("   1. 檢查失敗的測試案例，特別關注錯誤信息")
            print("   2. 針對邊界條件加強輸入驗證")
            print("   3. 改善錯誤處理和異常捕獲")
        
        if any('執行時間過長' in str(r['analysis']['warnings']) for r in self.test_results):
            print("   4. 優化性能，特別是處理大量數據時")
            
        print("   5. 添加更多的數據驗證和完整性檢查")

def main():
    """主函數"""
    runner = BoundaryTestRunner()
    runner.run_all_boundary_tests()

if __name__ == "__main__":
    main() 