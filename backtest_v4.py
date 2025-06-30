import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import glob
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams

# 添加數據庫支持
from database_operations import DatabaseManager

# 設定中文字體
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ===== 策略參數設定（在這裡修改你的參數）=====
INITIAL_CAPITAL = 10000  # 初始資金
POSITION_SIZE = 0.25  # 每次進場資金比例 (25%)
FEE_RATE = 0.001  # 手續費率 (0.07%)
EXIT_SIZE = 1.0  # 每次離場資金比例 (100%)
MAX_POSITIONS = 4  # 最大持倉數 <<<--- 在這裡修改
ENTRY_TOP_N = 4  # 進場條件: 綜合評分前N名 <<<--- 在這裡修改
EXIT_THRESHOLD = 10  # 離場條件: 排名跌出前N名

# ===== 回測期間設定 =====
START_DATE = "2024-01-01"  # 開始日期 (修改為有數據的日期)
END_DATE = "2025-06-20"  # 結束日期 - 延長至3天以看到完整回測效果
# 移除CSV依賴，全部使用數據庫


class FundingRateBacktest:
    def __init__(self, initial_capital=10000, position_size=0.1, fee_rate=0.0007,
                 exit_size=1.0, max_positions=3, entry_top_n=3, exit_threshold=20):
        """
        初始化回測參數
        :param initial_capital: 初始資金
        :param position_size: 每次進場資金比例 (10% = 0.1)
        :param fee_rate: 手續費率 (0.07% = 0.0007)
        :param exit_size: 每次離場資金比例 (100% = 1.0)
        :param max_positions: 最大持倉數
        :param entry_top_n: 進場條件: 綜合評分前N名
        :param exit_threshold: 離場條件: 排名跌出前N名
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.fee_rate = fee_rate
        self.exit_size = exit_size
        self.max_positions = max_positions
        self.entry_top_n = entry_top_n
        self.exit_threshold = exit_threshold

        # 打印實際接收到的參數值
        print(f"[DEBUG] 初始化參數:")
        print(f"  - max_positions: {self.max_positions}")
        print(f"  - entry_top_n: {self.entry_top_n}")
        print(f"  - exit_threshold: {self.exit_threshold}")

        # 帳戶狀態
        self.cash_balance = initial_capital
        self.position_balance = 0.0
        self.total_balance = initial_capital

        # 持倉狀態
        self.positions = {}  # {交易對: 投入金額}
        self.positions_entry_date = {}  # {交易對: 進場日期} - 新增：追蹤每個倉位的進場日期

        # 記錄
        self.event_log = []
        self.position_log = []
        self.event_counter = 1

        # 回測統計
        self.max_balance = initial_capital
        self.max_drawdown = 0.0

        # 新增：勝率統計
        self.daily_pnl_records = []  # 記錄每日損益
        self.profit_days = 0  # 獲利天數
        self.loss_days = 0  # 虧損天數
        self.break_even_days = 0  # 打平天數

        # 新增：持倉天數統計
        self.holding_periods = []  # 記錄每個倉位的持倉天數
        self.position_counter = 0  # 倉位計數器（用於區分同一交易對的不同倉位）

        # 新增：回測期間追蹤
        self.start_date = None
        self.end_date = None
        self.backtest_days = 0

        # 新增：淨值曲線記錄
        self.equity_curve_data = []  # 記錄每日淨值 {date, total_balance}
        
        # 新增：策略名稱
        self.strategy_name = None  # 用於檔案命名

        # 新增：夏普比率計算所需變數
        self.daily_returns = []  # 每日收益率記錄

    def get_entry_candidates(self, date_str):
        """
        獲取進場候選交易對
        :param date_str: 日期字串
        """
        if date_str not in self.ranking_data:
            return []

        df = self.ranking_data[date_str]
        # 使用 final_ranking_score 欄位，取前N名
        top_pairs = df.head(self.entry_top_n)['trading_pair'].tolist()
        return top_pairs

    def get_exit_candidates(self, date_str):
        """
        獲取需要離場的交易對（不在前N名的持倉）
        :param date_str: 日期字串
        """
        if date_str not in self.ranking_data:
            return list(self.positions.keys())

        df = self.ranking_data[date_str]
        # 使用 final_ranking_score 欄位，取前N名
        top_pairs = set(df.head(self.exit_threshold)['trading_pair'].tolist())

        exit_pairs = []
        for pair in self.positions.keys():
            if pair not in top_pairs:
                exit_pairs.append(pair)

        return exit_pairs

    def calculate_funding_rate_pnl_with_date(self, ranking_date_str, current_time, trading_date_str):
        """
        計算當日資金費率收益（使用前一天的1d_return作為資費差）
        :param ranking_date_str: 用於查找數據的排行榜日期（前一天）
        :param current_time: 當前時間字串
        :param trading_date_str: 交易日期（用於記錄）
        """
        if ranking_date_str not in self.ranking_data or not self.positions:
            # 如果沒有持倉，當日損益為0（打平）
            if not self.positions:
                self.daily_pnl_records.append({
                    'date': trading_date_str,
                    'daily_pnl': 0.0,
                    'result': 'break_even'
                })
                self.break_even_days += 1
                # 計算收益率（為0）
                daily_return_rate = 0.0
                self.daily_returns.append(daily_return_rate)
            return

        df = self.ranking_data[ranking_date_str]
        daily_pnl_total = 0.0

        for pair in list(self.positions.keys()):  # 使用list()避免字典在循環中改變
            # 檢查是否為當天進場的倉位 - 當天進場的不能領資金費率
            if pair in self.positions_entry_date:
                entry_date = self.positions_entry_date[pair]
                if entry_date == trading_date_str:
                    print(f"跳過當天進場的標的 {pair}，不計算資金費率收益")
                    continue

            # 使用前一天ranking文件的1d_return作為資費差（注意：使用標準化後的欄位名稱）
            pair_data = df[df['trading_pair'] == pair]
            if not pair_data.empty:
                # 檢查1d_return是否為有效數值
                daily_return = pair_data.iloc[0]['1d_return']
                if pd.isna(daily_return) or not np.isfinite(daily_return):
                    print(f"警告: {pair} 在 {ranking_date_str} 的1d_return無效: {daily_return}")
                    continue

                # 使用1d_return作為當日資金費率收益率（資費差）
                daily_return_rate = daily_return
                position_amount = self.positions[pair]
                # 用於計算資金費率的倉位金額要除以2（因為是兩個交易所的套利）
                effective_position_amount = position_amount / 2
                pnl = effective_position_amount * daily_return_rate

                # 檢查計算結果
                if pd.isna(pnl) or not np.isfinite(pnl):
                    print(f"警告: {pair} 在 {ranking_date_str} 的PnL計算無效: {pnl}")
                    continue

                daily_pnl_total += pnl

                # 記錄資金費率收益 - 傳入1d_return作為資費差
                self.add_event_log(
                    current_time, '資金費率', pair, pnl, daily_return,
                    self.position_balance, self.position_balance,
                    self.cash_balance, self.cash_balance + pnl
                )

        # 更新現金餘額和總餘額
        self.cash_balance += daily_pnl_total
        self.total_balance = self.cash_balance + self.position_balance

        # 計算當日收益率
        if self.total_balance > 0:
            # 基於前一天的總餘額計算收益率
            previous_balance = self.total_balance - daily_pnl_total
            if previous_balance > 0:
                daily_return_rate = daily_pnl_total / previous_balance
            else:
                daily_return_rate = 0.0
        else:
            daily_return_rate = 0.0

        # 記錄每日收益率
        self.daily_returns.append(daily_return_rate)

        # 記錄每日損益
        self.record_daily_pnl(trading_date_str, daily_pnl_total)

        # 更新最大餘額和回撤
        self.update_max_drawdown()

        print(f"當日資金費率總收益: ${daily_pnl_total:.2f}, 總餘額: ${self.total_balance:.2f}")

    def enter_position(self, pair, current_time):
        """
        進場操作
        :param pair: 交易對
        :param current_time: 當前時間字串
        """
        # 檢查持倉數量限制
        if len(self.positions) >= self.max_positions:
            print(f"已達最大持倉數 {self.max_positions}，無法進場 {pair}")
            return

        # 計算進場金額
        entry_amount = self.cash_balance * self.position_size
        fee = entry_amount * self.fee_rate
        total_cost = entry_amount + fee

        # 檢查現金是否足夠
        if total_cost > self.cash_balance:
            print(f"現金不足，無法進場 {pair}")
            return

        # 執行進場
        self.positions[pair] = entry_amount
        self.positions_entry_date[pair] = current_time.split()[0]  # 只保存日期部分
        self.cash_balance -= total_cost
        self.position_balance += entry_amount

        # 記錄事件
        self.add_event_log(
            current_time, '進場', pair, entry_amount, 0,
            self.position_balance - entry_amount, self.position_balance,
            self.cash_balance + total_cost, self.cash_balance
        )

        print(f"✅ 進場 {pair}: ${entry_amount:.2f} (手續費: ${fee:.2f})")

    def exit_position(self, pair, current_time):
        """
        離場操作
        :param pair: 交易對
        :param current_time: 當前時間字串
        """
        if pair not in self.positions:
            print(f"沒有持倉 {pair}，無法離場")
            return

        # 計算離場金額
        position_amount = self.positions[pair]
        exit_amount = position_amount * self.exit_size
        fee = exit_amount * self.fee_rate
        net_exit_amount = exit_amount - fee

        # 執行離場
        del self.positions[pair]
        
        # 計算持倉天數
        if pair in self.positions_entry_date:
            entry_date_str = self.positions_entry_date[pair]
            current_date_str = current_time.split()[0]
            try:
                entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d')
                current_date = datetime.strptime(current_date_str, '%Y-%m-%d')
                holding_days = (current_date - entry_date).days
                self.holding_periods.append(holding_days)
            except ValueError:
                print(f"日期格式錯誤，無法計算持倉天數: {entry_date_str}, {current_date_str}")
            
            del self.positions_entry_date[pair]

        self.position_balance -= position_amount
        self.cash_balance += net_exit_amount

        # 記錄事件
        self.add_event_log(
            current_time, '離場', pair, exit_amount, 0,
            self.position_balance + position_amount, self.position_balance,
            self.cash_balance - net_exit_amount, self.cash_balance
        )

        print(f"✅ 離場 {pair}: ${exit_amount:.2f} (手續費: ${fee:.2f})")

    def format_position_detail(self):
        """格式化持倉詳情字串"""
        if not self.positions:
            return "無持倉"
        
        details = []
        for pair, amount in self.positions.items():
            details.append(f"{pair}(${amount:.0f})")
        return ", ".join(details)

    def add_event_log(self, time_str, event_type, pair, amount, funding_rate_diff,
                      before_position, after_position, before_cash, after_cash):
        """
        添加事件記錄
        """
        total_balance = after_position + after_cash
        position_detail = self.format_position_detail()
        
        event = {
            '編號': self.event_counter,
            '時間': time_str,
            '事件': event_type,
            '交易對': pair,
            '金額': amount,
            '資費差': funding_rate_diff,
            '持倉前': before_position,
            '持倉後': after_position,
            '現金前': before_cash,
            '現金後': after_cash,
            '總餘額': total_balance,
            '持倉詳情': position_detail
        }
        
        self.event_log.append(event)
        self.event_counter += 1

    def add_position_log(self, time_str):
        """
        添加持倉記錄
        """
        position_detail = self.format_position_detail()
        
        position_record = {
            '時間': time_str,
            '現金餘額': self.cash_balance,
            '持倉餘額': self.position_balance,
            '總餘額': self.total_balance,
            '持倉詳情': position_detail,
            '持倉數量': len(self.positions)
        }
        
        self.position_log.append(position_record)

    def update_max_drawdown(self):
        """更新最大回撤"""
        if self.total_balance > self.max_balance:
            self.max_balance = self.total_balance
        
        if self.max_balance > 0:
            current_drawdown = (self.max_balance - self.total_balance) / self.max_balance
            if current_drawdown > self.max_drawdown:
                self.max_drawdown = current_drawdown

    def record_daily_pnl(self, date_str, daily_pnl):
        """
        記錄每日損益
        :param date_str: 日期字串
        :param daily_pnl: 當日損益
        """
        if daily_pnl > 0:
            result = 'profit'
            self.profit_days += 1
        elif daily_pnl < 0:
            result = 'loss'
            self.loss_days += 1
        else:
            result = 'break_even'
            self.break_even_days += 1
        
        self.daily_pnl_records.append({
            'date': date_str,
            'daily_pnl': daily_pnl,
            'result': result
        })

    def add_daily_equity_record(self, date_str, total_balance):
        """
        添加每日淨值記錄
        :param date_str: 日期字串
        :param total_balance: 總餘額
        """
        self.equity_curve_data.append({
            'date': date_str,
            'total_balance': total_balance
        })

    def calculate_win_rate(self):
        """計算勝率"""
        total_pnl_days = len(self.daily_pnl_records)
        if total_pnl_days == 0:
            return 0.0
        return self.profit_days / total_pnl_days

    def calculate_average_holding_days(self):
        """計算平均持倉天數"""
        if not self.holding_periods:
            return 0.0
        return sum(self.holding_periods) / len(self.holding_periods)

    def calculate_backtest_period(self, start_date, end_date):
        """計算回測期間"""
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            self.backtest_days = (end_dt - start_dt).days
            self.start_date = start_dt
            self.end_date = end_dt
        except ValueError:
            self.backtest_days = 0

    def calculate_sharpe_ratio(self):
        """
        計算夏普比率
        :return: 夏普比率
        """
        if len(self.daily_returns) < 2:
            return 0.0
        
        # 轉換為numpy數組
        returns = np.array(self.daily_returns)
        
        # 過濾無效值
        returns = returns[np.isfinite(returns)]
        
        if len(returns) < 2:
            return 0.0
        
        # 計算平均收益率和標準差
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)  # 使用樣本標準差
        
        # 避免除零
        if std_return == 0:
            return 0.0
        
        # 計算年化夏普比率（假設無風險利率為0）
        # 年化: 日收益率 * sqrt(365)
        sharpe_ratio = mean_return / std_return * np.sqrt(365)
        
        return sharpe_ratio

    def plot_equity_curve(self, output_dir="data/picture/backtest"):
        """
        繪製淨值曲線圖，參考用戶提供的樣式，並添加 backtest_id 標記
        :param output_dir: 輸出目錄，默認為 data/picture/backtest
        """
        if not self.equity_curve_data:
            print("警告: 沒有淨值曲線數據可繪製")
            return None

        # 確保輸出目錄存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"✅ 創建輸出目錄: {output_dir}")

        # 準備數據
        df = pd.DataFrame(self.equity_curve_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 計算報酬率
        df['returns'] = (df['total_balance'] - self.initial_capital) / self.initial_capital * 100

        # 創建圖表，使用與用戶提供樣式一致的設計
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # 上圖：淨值曲線 - 參考用戶樣式
        ax1.plot(df['date'], df['total_balance'], linewidth=2, color='#1f77b4', label='總餘額')
        ax1.axhline(y=self.initial_capital, color='red', linestyle='--', alpha=0.8,
                    label=f'初始資金 ${self.initial_capital:,}')
        ax1.set_title(f'淨值曲線 - {self.strategy_name}', fontsize=14, fontweight='bold', pad=20)
        ax1.set_ylabel('總餘額 ($)', fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.legend()

        # 添加 backtest_id 標記到右上角
        ax1.text(0.02, 0.98, f'Backtest ID: {self.backtest_id}', 
                transform=ax1.transAxes, 
                fontsize=10, 
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # 格式化Y軸 - 使用美元格式
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        # 下圖：累計報酬率 - 參考用戶樣式
        ax2.plot(df['date'], df['returns'], linewidth=2, color='#d62728', label='累計報酬率')
        ax2.axhline(y=0, color='red', linestyle='--', alpha=0.8, label='損益平衡線')
        ax2.set_title(f'累計報酬率 - {self.strategy_name}', fontsize=14, fontweight='bold', pad=20)
        ax2.set_xlabel('日期', fontsize=12)
        ax2.set_ylabel('報酬率 (%)', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.legend()

        # 添加 backtest_id 標記到右上角
        ax2.text(0.02, 0.98, f'Backtest ID: {self.backtest_id}', 
                transform=ax2.transAxes, 
                fontsize=10, 
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # 格式化日期軸 - 使用月份間隔
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        # 調整布局
        plt.tight_layout()

        # 生成檔案名稱 - 使用更簡潔的命名格式
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        start_date_str = self.start_date.strftime('%Y-%m-%d') if hasattr(self.start_date, 'strftime') else str(self.start_date).split()[0]
        end_date_str = self.end_date.strftime('%Y-%m-%d') if hasattr(self.end_date, 'strftime') else str(self.end_date).split()[0]
        filename = f"equity_curve_{self.strategy_name}_{start_date_str}_{end_date_str}_{timestamp}.png"
        chart_path = os.path.join(output_dir, filename)

        # 保存圖表
        plt.savefig(chart_path, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()

        print(f"✅ 淨值曲線圖已保存: {chart_path}")
        return chart_path

    def load_strategy_ranking_data(self, strategy_name, start_date, end_date):
        """
        從數據庫載入指定期間的策略排行榜數據，並合併收益數據
        :param strategy_name: 策略名稱
        :param start_date: 開始日期 'YYYY-MM-DD'
        :param end_date: 結束日期 'YYYY-MM-DD'
        """
        self.ranking_data = {}
        
        print(f"🗄️ 正在從數據庫載入策略 {strategy_name} 的排行榜數據...")
        
        try:
            # 使用數據庫管理器
            db = DatabaseManager()
            
            # 生成日期範圍 - 策略檔案日期範圍應該是 start_date 到 (end_date-1)
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            strategy_end_dt = end_dt - timedelta(days=1)
            
            print(f"📅 載入策略數據日期範圍: {start_date} 到 {strategy_end_dt.strftime('%Y-%m-%d')}")
            
            current_dt = start_dt
            loaded_count = 0
            
            while current_dt <= strategy_end_dt:
                date_str = current_dt.strftime('%Y-%m-%d')
                
                # 使用JOIN查詢合併strategy_ranking和return_metrics數據
                query = """
                SELECT 
                    sr.strategy_name,
                    sr.trading_pair,
                    sr.date,
                    sr.final_ranking_score,
                    sr.rank_position,
                    sr.long_term_score,
                    sr.short_term_score,
                    sr.combined_roi_z_score,
                    rm.return_1d,
                    rm.roi_1d,
                    rm.return_2d,
                    rm.roi_2d,
                    rm.return_7d,
                    rm.roi_7d,
                    rm.return_14d,
                    rm.roi_14d,
                    rm.return_30d,
                    rm.roi_30d,
                    rm.return_all,
                    rm.roi_all
                FROM strategy_ranking sr
                LEFT JOIN return_metrics rm ON sr.trading_pair = rm.trading_pair AND sr.date = rm.date
                WHERE sr.strategy_name = ? AND sr.date = ?
                ORDER BY sr.rank_position
                """
                
                df = pd.read_sql_query(query, db.get_connection(), params=[strategy_name, date_str])
                
                if not df.empty:
                    # 重命名欄位以保持向後兼容
                    df = df.rename(columns={
                        'rank_position': 'Rank',
                        'return_1d': '1d_return',  # 重要：將return_1d重命名為1d_return
                        'roi_1d': '1d_ROI',
                        'return_2d': '2d_return',
                        'roi_2d': '2d_ROI',
                        'return_7d': '7d_return',
                        'roi_7d': '7d_ROI',
                        'return_14d': '14d_return',
                        'roi_14d': '14d_ROI',
                        'return_30d': '30d_return',
                        'roi_30d': '30d_ROI',
                        'return_all': 'all_return',
                        'roi_all': 'all_ROI'
                    })
                    
                    # 按排名排序
                    df = df.sort_values('Rank').reset_index(drop=True)
                    
                    self.ranking_data[date_str] = df
                    loaded_count += 1
                    print(f"✅ 數據庫載入: {date_str} ({len(df)} 個交易對)")
                else:
                    print(f"❌ 數據庫中沒有找到: {strategy_name} 在 {date_str} 的數據")
                
                current_dt += timedelta(days=1)
            
            print(f"📊 成功從數據庫載入 {loaded_count} 天的排行榜數據")
            
        except Exception as e:
            print(f"❌ 從數據庫載入策略數據時出錯: {e}")
            import traceback
            traceback.print_exc()

    def run_backtest(self, strategy_name, start_date, end_date):
        """
        執行回測
        :param strategy_name: 策略名稱
        :param start_date: 開始日期 'YYYY-MM-DD'
        :param end_date: 結束日期 'YYYY-MM-DD'
        """
        # 設置策略名稱和回測ID
        self.strategy_name = strategy_name
        self.backtest_id = f"{strategy_name}_{start_date}_{end_date}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"🚀 開始執行回測")
        print(f"📊 策略名稱: {strategy_name}")
        print(f"📅 回測期間: {start_date} 至 {end_date}")
        print(f"🆔 回測ID: {self.backtest_id}")
        print("="*60)

        # 載入數據
        self.load_strategy_ranking_data(strategy_name, start_date, end_date)
        
        if not self.ranking_data:
            print("❌ 沒有載入任何數據，無法執行回測")
            return

        # 計算回測期間
        self.calculate_backtest_period(start_date, end_date)

        # 生成日期範圍
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        current_dt = start_dt
        day_counter = 1
        
        print(f"💰 初始資金: ${self.initial_capital:,.2f}")
        print(f"📈 開始逐日回測...")
        print("-"*60)

        while current_dt < end_dt:  # 注意：交易日期到end_date前一天
            current_date_str = current_dt.strftime('%Y-%m-%d')
            current_time = current_date_str + " 08:00:00"
            
            print(f"\n📅 第{day_counter}天: {current_date_str}")
            
            # 1. 檢查離場條件
            exit_pairs = self.get_exit_candidates(current_date_str)
            for pair in exit_pairs:
                self.exit_position(pair, current_time)
            
            # 2. 檢查進場條件
            entry_candidates = self.get_entry_candidates(current_date_str)
            for pair in entry_candidates:
                if pair not in self.positions and len(self.positions) < self.max_positions:
                    self.enter_position(pair, current_time)
            
            # 3. 計算當日資金費率收益
            # 使用當天的數據來計算資金費率收益
            self.calculate_funding_rate_pnl_with_date(current_date_str, current_time, current_date_str)
            
            # 4. 記錄當日持倉狀況
            self.add_position_log(current_time)
            
            # 5. 記錄淨值曲線
            self.add_daily_equity_record(current_date_str, self.total_balance)
            
            # 顯示當日狀況
            print(f"💰 總餘額: ${self.total_balance:.2f} | 現金: ${self.cash_balance:.2f} | 持倉: ${self.position_balance:.2f}")
            print(f"📊 持倉數: {len(self.positions)}/{self.max_positions}")
            if self.positions:
                print(f"🎯 持有標的: {list(self.positions.keys())}")
            
            current_dt += timedelta(days=1)
            day_counter += 1

        print("\n" + "="*60)
        print("✅ 回測執行完成！")
        
        # 生成報告
        self.generate_reports()

    def generate_reports(self):
        """
        生成回測報告並保存到數據庫
        """
        print("📊 正在生成回測報告並保存到數據庫...")
        
        try:
            db = DatabaseManager()
            
            # 計算基本統計
            final_capital = self.total_balance
            if pd.isna(final_capital) or not np.isfinite(final_capital):
                final_capital = self.initial_capital
            
            total_return = final_capital - self.initial_capital
            total_roi = total_return / self.initial_capital
            
            # 計算年化報酬率 (ROI)
            if self.backtest_days > 0:
                roi = total_roi * 365 / self.backtest_days
            else:
                roi = 0
            
            win_rate = self.calculate_win_rate()
            avg_holding_days = self.calculate_average_holding_days()
            sharpe_ratio = self.calculate_sharpe_ratio()  # 計算夏普比率
            
            # 確保有backtest_id
            if not hasattr(self, 'backtest_id') or not self.backtest_id:
                self.backtest_id = f"{self.strategy_name}_{self.start_date}_{self.end_date}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 分離配置參數和結果數據
            config = {
                'initial_capital': float(self.initial_capital),
                'position_size': float(self.position_size),
                'fee_rate': float(self.fee_rate),
                'exit_size': float(self.exit_size),
                'max_positions': int(self.max_positions),
                'entry_top_n': int(self.entry_top_n),
                'exit_threshold': int(self.exit_threshold)
            }
            
            results = {
                'final_balance': float(final_capital),
                'total_return': float(total_roi),
                'roi': float(roi),
                'sharpe_ratio': float(sharpe_ratio),  # 重新排序：將夏普比率放在roi後面
                'total_days': int(self.backtest_days),
                'max_drawdown': float(self.max_drawdown),
                'win_rate': float(win_rate),
                'total_trades': len(self.holding_periods),
                'profit_days': int(self.profit_days),
                'loss_days': int(self.loss_days),
                'avg_holding_days': float(avg_holding_days),
                'notes': f"回測期間: {self.backtest_days} 天, Backtest ID: {self.backtest_id}"
            }
            
            db.insert_backtest_result(
                strategy_name=self.strategy_name,
                start_date=self.start_date,
                end_date=self.end_date,
                config=config,
                results=results,
                backtest_id=self.backtest_id
            )
            print(f"✅ 回測結果摘要已保存到數據庫: {self.backtest_id}")
            
            # 保存交易記錄到數據庫
            if self.event_log:
                trades_data = []
                for event in self.event_log:
                    try:
                        # 提取日期和時間
                        time_str = event.get('時間', '')
                        if ' ' in time_str:
                            date_part = time_str.split(' ')[0]
                        else:
                            date_part = time_str
                        
                        # 安全轉換數值，處理 '-' 和空值
                        def safe_float(value, default=0.0):
                            if value == '-' or value == '' or value is None:
                                return default
                            try:
                                return float(value)
                            except (ValueError, TypeError):
                                return default
                        
                        # 轉換中文動作為英文動作
                        original_action = event.get('事件', event.get('類型', ''))
                        if '進場' in original_action or '買入' in original_action or 'enter' in original_action.lower():
                            action = 'enter'
                        elif '離場' in original_action or '賣出' in original_action or 'exit' in original_action.lower():
                            action = 'exit'
                        elif '資金' in original_action or 'funding' in original_action.lower():
                            action = 'funding'
                        else:
                            action = 'funding'  # 默認為 funding
                        
                        trade_data = {
                            'trade_date': date_part,
                            'trading_pair': event.get('交易對', ''),
                            'action': action,
                            'amount': safe_float(event.get('金額', 0)),
                            'funding_rate_diff': safe_float(event.get('資費差', 0)),
                            'position_balance': safe_float(event.get('持倉後', event.get('after倉位餘額', 0))),
                            'cash_balance': safe_float(event.get('現金後', event.get('after現金餘額', 0))),
                            'total_balance': safe_float(event.get('總餘額', 0)),
                            'rank_position': None,  # 排名位置在事件記錄中可能沒有
                            'position_detail': event.get('持倉詳情', ''),  # 新增持倉詳情
                            'notes': f"原始事件: {original_action}, Backtest ID: {self.backtest_id}"
                        }
                        
                        trades_data.append(trade_data)
                        
                    except Exception as e:
                        print(f"⚠️ 處理交易記錄時出錯: {e}")
                        continue
                
                # 批量插入交易記錄
                if trades_data:
                    trades_saved = db.insert_backtest_trades(self.backtest_id, trades_data)
                    print(f"✅ {trades_saved} 條交易記錄已保存到數據庫")
                else:
                    print("✅ 0 條交易記錄已保存到數據庫")
            
            # 保存每日淨值記錄
            if self.equity_curve_data:
                equity_data = []
                for equity_point in self.equity_curve_data:
                    try:
                        equity_trade = {
                            'trade_date': equity_point['date'],
                            'trading_pair': 'PORTFOLIO',
                            'action': 'funding',  # 使用有效的 action 值
                            'amount': float(equity_point['total_balance']),
                            'funding_rate_diff': 0.0,
                            'position_balance': float(equity_point['total_balance']),
                            'cash_balance': 0.0,
                            'total_balance': float(equity_point['total_balance']),
                            'rank_position': None,
                            'position_detail': 'PORTFOLIO',  # 淨值記錄的持倉詳情
                            'notes': f"每日淨值記錄: {equity_point['date']}, Backtest ID: {self.backtest_id}"
                        }
                        equity_data.append(equity_trade)
                        
                    except Exception as e:
                        print(f"⚠️ 處理淨值記錄時出錯: {e}")
                        continue
                
                # 批量插入淨值記錄
                if equity_data:
                    equity_saved = db.insert_backtest_trades(self.backtest_id, equity_data)
                    print(f"✅ {equity_saved} 條淨值記錄已保存到數據庫")
                else:
                    print("✅ 0 條淨值記錄已保存到數據庫")
            
        except Exception as e:
            print(f"❌ 保存回測報告到數據庫時出錯: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # 生成文字摘要
        summary_text = f"""
🎯 回測結果摘要
================================
回測ID: {self.backtest_id}
策略名稱: {self.strategy_name}
回測期間: {self.start_date} 至 {self.end_date} ({self.backtest_days} 天)

💰 資金績效
----------------
初始資金: ${self.initial_capital:,.2f}
最終資金: ${final_capital:,.2f}
總報酬: ${total_return:,.2f}
總報酬率: {total_roi:.2%}
年化報酬率: {roi:.2%}
夏普比率: {sharpe_ratio:.3f}
最高資金: ${self.max_balance:,.2f}
最大回撤: {self.max_drawdown:.2%}

📊 交易統計
----------------
總交易次數: {len(self.holding_periods)}
平均持倉天數: {avg_holding_days:.1f} 天
勝率: {win_rate:.1%}
獲利天數: {self.profit_days}
虧損天數: {self.loss_days}
打平天數: {self.break_even_days}

⚙️ 策略參數
----------------
每次進場資金比例: {self.position_size:.1%}
手續費率: {self.fee_rate:.4%}
每次離場資金比例: {self.exit_size:.1%}
最大持倉數: {self.max_positions}
進場條件: 前{self.entry_top_n}名
離場條件: 跌出前{self.exit_threshold}名

💾 數據存儲
----------------
✅ 回測結果已保存到數據庫
✅ 交易記錄已保存到數據庫
✅ 淨值曲線已保存到數據庫
📊 數據庫ID: {self.backtest_id}
"""
        
        # 生成淨值曲線圖
        try:
            chart_path = self.plot_equity_curve()
            if chart_path:
                print(f"📈 淨值曲線圖已生成: {chart_path}")
        except Exception as e:
            print(f"⚠️ 生成淨值曲線圖時出錯: {e}")
        
        print("✅ 數據庫報告生成完成!")
        print(summary_text)

    def detect_available_strategies(self, start_date, end_date):
        """
        從數據庫偵測可用的策略
        :param start_date: 開始日期 'YYYY-MM-DD'
        :param end_date: 結束日期 'YYYY-MM-DD'
        :return: 可用的策略列表
        """
        print(f"🔍 正在從數據庫偵測可用的策略...")
        
        try:
            # 從數據庫獲取策略
            db = DatabaseManager()
            
            # 獲取所有可用策略名稱
            available_strategies = db.get_available_strategies()
            
            if not available_strategies:
                print("📊 數據庫中沒有策略數據")
                return []
            
            print(f"💾 數據庫中發現 {len(available_strategies)} 個策略: {available_strategies}")
            return available_strategies
            
        except Exception as e:
            print(f"❌ 從數據庫偵測策略時出錯: {e}")
            import traceback
            traceback.print_exc()
            return []

    def interactive_strategy_selection(self, start_date, end_date):
        """
        互動式策略選擇
        :param start_date: 開始日期 'YYYY-MM-DD'
        :param end_date: 結束日期 'YYYY-MM-DD'
        :return: 選擇的策略列表
        """
        available_strategies = self.detect_available_strategies(start_date, end_date)
        
        if not available_strategies:
            print("❌ 沒有找到任何可用的策略")
            return []
        
        print("\n" + "="*60)
        print("🎯 策略選擇菜單")
        print("="*60)
        print("可用策略:")
        
        for i, strategy in enumerate(available_strategies, 1):
            print(f"  {i}. {strategy}")
        
        print(f"  {len(available_strategies) + 1}. 全部策略")
        print(f"  0. 退出")
        
        while True:
            try:
                choice = input(f"\n請選擇策略 (0-{len(available_strategies) + 1}): ").strip()
                
                if choice == "0":
                    print("👋 退出程式")
                    return []
                
                choice_num = int(choice)
                
                if choice_num == len(available_strategies) + 1:
                    print(f"✅ 選擇全部策略: {available_strategies}")
                    return available_strategies
                
                if 1 <= choice_num <= len(available_strategies):
                    selected_strategy = available_strategies[choice_num - 1]
                    print(f"✅ 選擇策略: {selected_strategy}")
                    return [selected_strategy]
                
                print(f"❌ 無效選擇，請輸入 0-{len(available_strategies) + 1}")
                
            except ValueError:
                print("❌ 請輸入有效數字")
            except KeyboardInterrupt:
                print("\n👋 用戶中斷，退出程式")
                return []

    def run_multiple_backtests(self, selected_strategies, start_date, end_date):
        """
        執行多個策略的回測
        :param selected_strategies: 選擇的策略列表
        :param start_date: 開始日期 'YYYY-MM-DD'
        :param end_date: 結束日期 'YYYY-MM-DD'
        """
        if not selected_strategies:
            return
        
        results_summary = []
        
        print(f"\n🚀 開始執行 {len(selected_strategies)} 個策略的回測")
        print("="*70)
        
        for i, strategy in enumerate(selected_strategies, 1):
            print(f"\n📊 [{i}/{len(selected_strategies)}] 執行策略: {strategy}")
            print("-"*50)
            
            # 重置回測器狀態
            self.__init__(
                initial_capital=self.initial_capital,
                position_size=self.position_size,
                fee_rate=self.fee_rate,
                exit_size=self.exit_size,
                max_positions=self.max_positions,
                entry_top_n=self.entry_top_n,
                exit_threshold=self.exit_threshold
            )
            
            # 執行回測（從數據庫）
            try:
                self.run_backtest(strategy, start_date, end_date)
                
                # 收集結果
                final_capital = self.total_balance
                total_return = final_capital - self.initial_capital
                total_roi = total_return / self.initial_capital
                roi = total_roi * 365 / self.backtest_days if self.backtest_days > 0 else 0
                win_rate = self.calculate_win_rate()
                avg_holding_days = self.calculate_average_holding_days()
                sharpe_ratio = self.calculate_sharpe_ratio()
                
                results_summary.append({
                    'strategy': strategy,
                    'backtest_id': self.backtest_id,
                    'final_capital': final_capital,
                    'total_return': total_return,
                    'total_roi': total_roi,
                    'roi': roi,
                    'sharpe_ratio': sharpe_ratio,
                    'max_drawdown': self.max_drawdown,
                    'win_rate': win_rate,
                    'total_trades': len(self.holding_periods),
                    'avg_holding_days': avg_holding_days,
                    'backtest_days': self.backtest_days
                })
                
            except Exception as e:
                print(f"❌ 執行策略 {strategy} 時出錯: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 顯示比較結果
        if results_summary:
            self.display_strategy_comparison(results_summary)

    def display_strategy_comparison(self, results_summary):
        """
        顯示策略比較結果
        :param results_summary: 結果摘要列表
        """
        print("\n" + "="*100)
        print("📊 策略比較結果")
        print("="*100)
        
        # 排序：依年化報酬率降序
        results_summary.sort(key=lambda x: x['roi'], reverse=True)
        
        # 表頭
        header = f"{'排名':<4} {'策略名稱':<20} {'最終資金':<12} {'總報酬率':<10} {'年化報酬率':<12} {'夏普比率':<10} {'最大回撤':<10} {'勝率':<8} {'交易數':<8} {'平均持倉天數':<12} {'Backtest ID':<30}"
        print(header)
        print("-" * len(header))
        
        # 資料行
        for rank, result in enumerate(results_summary, 1):
            row = f"{rank:<4} {result['strategy']:<20} ${result['final_capital']:<11,.0f} {result['total_roi']:<9.1%} {result['roi']:<11.1%} {result['sharpe_ratio']:<9.3f} {result['max_drawdown']:<9.1%} {result['win_rate']:<7.1%} {result['total_trades']:<8} {result['avg_holding_days']:<11.1f} {result['backtest_id']:<30}"
            print(row)
        
        print("\n" + "="*100)
        print("🏆 最佳策略統計:")
        
        # 最佳策略
        best_roi = max(results_summary, key=lambda x: x['roi'])
        best_sharpe = max(results_summary, key=lambda x: x['sharpe_ratio'])
        best_winrate = max(results_summary, key=lambda x: x['win_rate'])
        lowest_drawdown = min(results_summary, key=lambda x: x['max_drawdown'])
        
        print(f"📈 最高年化報酬率: {best_roi['strategy']} ({best_roi['roi']:.1%})")
        print(f"⚡ 最高夏普比率: {best_sharpe['strategy']} ({best_sharpe['sharpe_ratio']:.3f})")
        print(f"🎯 最高勝率: {best_winrate['strategy']} ({best_winrate['win_rate']:.1%})")
        print(f"🛡️ 最低回撤: {lowest_drawdown['strategy']} ({lowest_drawdown['max_drawdown']:.1%})")
        
        print(f"\n✅ 完成 {len(results_summary)} 個策略的回測比較")


def main():
    """
    主程式入口
    """
    print("🚀 資金費率套利回測系統 v4 (數據庫版)")
    print("="*60)
    
    # 使用全局參數初始化回測器
    backtest = FundingRateBacktest(
        initial_capital=INITIAL_CAPITAL,
        position_size=POSITION_SIZE,
        fee_rate=FEE_RATE,
        exit_size=EXIT_SIZE,
        max_positions=MAX_POSITIONS,
        entry_top_n=ENTRY_TOP_N,
        exit_threshold=EXIT_THRESHOLD
    )
    
    # 互動式策略選擇
    selected_strategies = backtest.interactive_strategy_selection(START_DATE, END_DATE)
    
    if not selected_strategies:
        print("👋 沒有選擇任何策略，程式結束")
        return
    
    # 執行多策略回測
    backtest.run_multiple_backtests(selected_strategies, START_DATE, END_DATE)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 用戶中斷程式，正常退出")
    except Exception as e:
        print(f"❌ 程式執行時發生錯誤: {e}")
        import traceback
        traceback.print_exc() 