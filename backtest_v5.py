import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import glob
import re

# 添加數據庫支持
from database_operations import DatabaseManager

# ===== 策略參數設定（在這裡修改你的參數）=====
INITIAL_CAPITAL = 10000  # 初始資金
POSITION_SIZE = 0.25  # 每次進場資金比例 (25%)
FEE_RATE = 0.001  # 手續費率 (0.1%)
EXIT_SIZE = 1.0  # 每次離場資金比例 (100%)
MAX_POSITIONS = 4  # 最大持倉數 <<<--- 在這裡修改
ENTRY_TOP_N = 4  # 進場條件: 綜合評分前N名 <<<--- 在這裡修改
EXIT_THRESHOLD = 10  # 離場條件: 排名跌出前N名
POSITION_MODE = 'percentage_based'  # v5新增：進場模式 ('fixed_amount' 或 'percentage_based')

# ===== 回測期間設定 =====
START_DATE = "2024-01-01"  # 開始日期 (修改為有數據的日期)
END_DATE = "2025-06-20"  # 結束日期 - 延長至3天以看到完整回測效果
# 移除CSV依賴，全部使用數據庫


class FundingRateBacktest:
    def __init__(self, initial_capital=10000, position_size=0.1, fee_rate=0.0007,
                 exit_size=1.0, max_positions=3, entry_top_n=3, exit_threshold=20,
                 position_mode='percentage_based'):
        """
        初始化回測參數
        :param initial_capital: 初始資金
        :param position_size: 每次進場資金比例 (10% = 0.1)
        :param fee_rate: 手續費率 (0.07% = 0.0007)
        :param exit_size: 每次離場資金比例 (100% = 1.0)
        :param max_positions: 最大持倉數
        :param entry_top_n: 進場條件: 綜合評分前N名
        :param exit_threshold: 離場條件: 排名跌出前N名
        :param position_mode: 進場金額計算模式 ('fixed_amount' 或 'percentage_based')
        """
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.fee_rate = fee_rate
        self.exit_size = exit_size
        self.max_positions = max_positions
        self.entry_top_n = entry_top_n
        self.exit_threshold = exit_threshold
        self.position_mode = position_mode  # 新增：進場模式開關

        # 打印實際接收到的參數值
        print(f"[DEBUG] 初始化參數:")
        print(f"  - max_positions: {self.max_positions}")
        print(f"  - entry_top_n: {self.entry_top_n}")
        print(f"  - exit_threshold: {self.exit_threshold}")
        print(f"  - position_mode: {self.position_mode}")

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

    def detect_files(self, summary_folder_path):
        """
        偵測資料夾中的檔案結構 - 已廢棄，改用strategy_ranking
        """
        pass

    def load_summary_data(self, summary_folder_path, start_date, end_date):
        """
        載入指定期間的summary數據 - 已廢棄，改用load_strategy_ranking_data
        """
        pass

    def get_entry_candidates(self, date_str):
        """
        獲取進場候選交易對
        :param date_str: 日期字串
        """
        if date_str not in self.summary_data:
            return []

        df = self.summary_data[date_str]
        # 使用統一的 Combined_Score 欄位
        top_pairs = df.head(self.entry_top_n)['trading_pair'].tolist()
        return top_pairs

    def get_exit_candidates(self, date_str):
        """
        獲取需要離場的交易對（不在前N名的持倉）
        :param date_str: 日期字串
        """
        if date_str not in self.summary_data:
            return list(self.positions.keys())

        df = self.summary_data[date_str]
        # 使用統一的 Combined_Score 欄位
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

                self.cash_balance += pnl
                print(
                    f"計算 {pair} 資金費率收益: {pnl:.2f} (倉位: {position_amount:.2f}, 1d_return: {daily_return:.8f})")

                # 檢查餘額是否有效
                if pd.isna(self.cash_balance) or not np.isfinite(self.cash_balance):
                    print(f"錯誤: 現金餘額變成無效值: {self.cash_balance}")
                    print(f"PnL: {pnl}, 交易對: {pair}, 日期: {ranking_date_str}")
                    # 回復到安全值
                    self.cash_balance = self.cash_balance - pnl if np.isfinite(self.cash_balance - pnl) else 0
                    continue

                self.total_balance = self.cash_balance + self.position_balance

                # 檢查總餘額是否有效
                if pd.isna(self.total_balance) or not np.isfinite(self.total_balance):
                    print(f"錯誤: 總餘額變成無效值: {self.total_balance}")
                    self.total_balance = self.cash_balance + self.position_balance

        # 記錄當日損益並更新勝率統計
        self.record_daily_pnl(trading_date_str, daily_pnl_total)

    def enter_position(self, pair, current_time):
        """
        進場操作 (v5版本：支持position_mode，合併手續費記錄)
        :param pair: 交易對
        :param current_time: 當前時間
        """
        if len(self.positions) >= self.max_positions:  # 使用動態最大持倉數
            print(f"已達最大持倉數 {self.max_positions}，無法進場 {pair}")
            return False

        if pair in self.positions:  # 已經持有該倉位
            print(f"已持有 {pair}，無法重複進場")
            return False

        # 根據 position_mode 計算進場金額
        if self.position_mode == 'fixed_amount':
            # 固定金額模式：每次進場固定金額
            entry_amount = self.initial_capital * self.position_size
        else:  # 'percentage_based'
            # 比例模式：根據當前現金餘額的比例進場
            entry_amount = self.cash_balance * self.position_size

        # 計算手續費
        fee = entry_amount * self.fee_rate
        total_cost = entry_amount + fee

        # 檢查現金是否充足
        if total_cost > self.cash_balance:
            print(f"現金不足，無法進場 {pair} (需要: ${total_cost:.2f}, 可用: ${self.cash_balance:.2f})")
            return False

        # 記錄進場前狀態
        before_position_balance = self.position_balance
        before_cash_balance = self.cash_balance

        # 執行進場操作
        self.positions[pair] = entry_amount
        self.position_balance += entry_amount
        self.cash_balance -= total_cost  # 扣除進場金額 + 手續費

        # 記錄進場日期
        entry_date = current_time.split(' ')[0]  # 提取日期部分 (YYYY-MM-DD)
        self.positions_entry_date[pair] = entry_date

        # 記錄進場事件（包含手續費，只記錄一筆）
        self.add_event_log(
            current_time, '進場', pair, entry_amount, '-',
            before_position_balance, self.position_balance,
            before_cash_balance, self.cash_balance
        )

        # 更新總餘額
        self.total_balance = self.cash_balance + self.position_balance

        print(f"✅ 進場 {pair}: ${entry_amount:.2f} (手續費: ${fee:.2f}, 模式: {self.position_mode})")
        return True

    def exit_position(self, pair, current_time):
        """
        離場操作 (v5版本：合併手續費記錄)
        :param pair: 交易對
        :param current_time: 當前時間
        """
        if pair not in self.positions:
            print(f"沒有持倉 {pair}，無法離場")
            return False

        position_amount = self.positions[pair]
        
        # 計算離場金額和手續費
        exit_amount = position_amount * self.exit_size
        fee = exit_amount * self.fee_rate
        net_proceeds = exit_amount - fee  # 扣除手續費後的實際收回金額

        # 記錄離場前狀態
        before_position_balance = self.position_balance
        before_cash_balance = self.cash_balance

        # 計算持倉天數
        if pair in self.positions_entry_date:
            entry_date_str = self.positions_entry_date[pair]
            exit_date_str = current_time.split(' ')[0]  # 提取日期部分 (YYYY-MM-DD)

            try:
                entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d')
                exit_date = datetime.strptime(exit_date_str, '%Y-%m-%d')
                holding_days = (exit_date - entry_date).days

                # 記錄持倉期間
                self.position_counter += 1
                holding_record = {
                    'position_id': self.position_counter,
                    'trading_pair': pair,
                    'entry_date': entry_date_str,
                    'exit_date': exit_date_str,
                    'holding_days': holding_days,
                    'position_amount': position_amount
                }
                self.holding_periods.append(holding_record)

                print(f"記錄持倉: {pair} 持倉 {holding_days} 天 ({entry_date_str} → {exit_date_str})")
            except ValueError as e:
                print(f"日期解析錯誤: {e}")

        # 執行離場操作
        self.position_balance -= position_amount
        self.cash_balance += net_proceeds  # 收回扣除手續費後的金額
        del self.positions[pair]

        # 清除進場日期記錄
        if pair in self.positions_entry_date:
            del self.positions_entry_date[pair]

        # 記錄離場事件（包含手續費，只記錄一筆）
        self.add_event_log(
            current_time, '離場', pair, exit_amount, '-',
            before_position_balance, self.position_balance,
            before_cash_balance, self.cash_balance
        )

        # 更新總餘額
        self.total_balance = self.cash_balance + self.position_balance

        print(f"✅ 離場 {pair}: ${exit_amount:.2f} (手續費: ${fee:.2f}, 實收: ${net_proceeds:.2f})")
        return True

    def format_position_detail(self):
        """
        格式化當前持倉詳情為字串，格式: "BT_TEST1(2000), BT_TEST2(1000)"
        """
        if not self.positions:
            return "無持倉"
        
        position_items = []
        for pair, amount in self.positions.items():
            position_items.append(f"{pair}({int(amount)})")
        
        return ", ".join(position_items)

    def add_event_log(self, time_str, event_type, pair, amount, funding_rate_diff,
                      before_position, after_position, before_cash, after_cash):
        """
        添加事件記錄
        """
        total_balance = after_position + after_cash

        self.event_log.append({
            '標號': self.event_counter,
            '時間': time_str,
            '類型': event_type,
            '交易對': pair,
            '金額': round(amount, 2),
            '資費差': funding_rate_diff if event_type == '資金費率' else '-',
            'before倉位餘額': round(before_position, 2),
            'after倉位餘額': round(after_position, 2),
            'before現金餘額': round(before_cash, 2),
            'after現金餘額': round(after_cash, 2),
            '總餘額': round(total_balance, 2),
            '持倉詳情': self.format_position_detail()  # 新增持倉詳情
        })

        if event_type not in ['進場手續費', '離場手續費']:
            self.event_counter += 1

    def add_position_log(self, time_str):
        """
        添加倉位記錄
        """
        position_count = len(self.positions)

        if position_count == 0:
            position_str = '-'
        else:
            position_list = [f"{pair}({round(amount, 2)})" for pair, amount in self.positions.items()]
            position_str = ', '.join(position_list)

        self.position_log.append({
            '時間': time_str,
            '倉位數目': position_count,
            '交易對&金額': position_str
        })

    def update_max_drawdown(self):
        """
        更新最大回撤
        """
        if self.total_balance > self.max_balance:
            self.max_balance = self.total_balance

        current_drawdown = (self.max_balance - self.total_balance) / self.max_balance
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown

    def record_daily_pnl(self, date_str, daily_pnl):
        """
        記錄當日損益並更新勝率統計 (v5版本：新增收益率追蹤)
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

        # 計算當日收益率（夏普比率計算需要）
        if len(self.equity_curve_data) > 1:
            # 使用前一天的總餘額計算收益率
            previous_balance = self.equity_curve_data[-1]['total_balance']
            if previous_balance > 0:
                daily_return_rate = daily_pnl / previous_balance
                self.daily_returns.append(daily_return_rate)
            else:
                self.daily_returns.append(0.0)
        else:
            # 第一天，收益率為 0
            self.daily_returns.append(0.0)

        self.daily_pnl_records.append({
            'date': date_str,
            'daily_pnl': daily_pnl,
            'result': result
        })

    def add_daily_equity_record(self, date_str, total_balance):
        """
        記錄每日淨值
        :param date_str: 日期字串
        :param total_balance: 總餘額
        """
        self.equity_curve_data.append({
            'date': date_str,
            'total_balance': total_balance
        })

    def calculate_win_rate(self):
        """
        計算勝率
        :return: 勝率 (獲利天數 / 總天數)
        """
        total_trading_days = self.profit_days + self.loss_days + self.break_even_days
        if total_trading_days == 0:
            return 0.0
        return self.profit_days / total_trading_days

    def calculate_average_holding_days(self):
        """
        計算平均持倉天數
        :return: 平均持倉天數
        """
        if not self.holding_periods:
            return 0.0

        total_holding_days = sum([record['holding_days'] for record in self.holding_periods])
        return total_holding_days / len(self.holding_periods)

    def calculate_sharpe_ratio(self):
        """
        計算夏普比率 (v5版本：從v4移植)
        :return: 年化夏普比率
        """
        if len(self.daily_returns) < 2:
            return 0.0
        
        # 計算每日收益率的平均值和標準差
        mean_daily_return = np.mean(self.daily_returns)
        std_daily_return = np.std(self.daily_returns, ddof=1)  # 使用樣本標準差
        
        if std_daily_return == 0:
            return 0.0
        
        # 假設無風險利率為0（簡化計算）
        daily_sharpe = mean_daily_return / std_daily_return
        
        # 年化夏普比率（假設一年有252個交易日）
        annual_sharpe = daily_sharpe * np.sqrt(252)
        
        return annual_sharpe

    def calculate_backtest_period(self, start_date, end_date):
        """
        計算回測期間天數
        :param start_date: 開始日期 'YYYY-MM-DD'
        :param end_date: 結束日期 'YYYY-MM-DD'
        """
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d')
        self.backtest_days = (self.end_date - self.start_date).days + 1

    def plot_equity_curve(self, output_dir="data/picture/backtest"):
        """
        繪製淨值曲線圖，參考用戶提供的樣式
        :param output_dir: 輸出目錄，默認為 data/picture/backtest
        """
        if not self.equity_curve_data:
            print("警告: 沒有淨值曲線數據可繪製")
            return None

        # 設置matplotlib使用非GUI後端，避免線程問題
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

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

        # 格式化日期軸 - 使用月份間隔
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        # 調整布局
        plt.tight_layout()

        # 生成檔案名稱 - v5版：包含backtest_id
        if hasattr(self, 'backtest_id') and self.backtest_id:
            filename = f"equity_curve_{self.backtest_id}.png"
        else:
            # 回傳格式：以防沒有backtest_id
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
                
                # 添加調試信息
                print(f"🔍 查詢策略: {strategy_name}, 日期: {date_str}")
                
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
                    # 改進錯誤信息，檢查是否存在策略數據
                    check_query = "SELECT COUNT(*) as count FROM strategy_ranking WHERE strategy_name = ? AND date = ?"
                    check_df = pd.read_sql_query(check_query, db.get_connection(), params=[strategy_name, date_str])
                    count = check_df['count'].iloc[0] if not check_df.empty else 0
                    
                    if count > 0:
                        print(f"⚠️  數據存在但JOIN失敗: {strategy_name} 在 {date_str} ({count} 條記錄)")
                        # 嘗試只查詢strategy_ranking表
                        simple_query = """
                        SELECT 
                            strategy_name,
                            trading_pair,
                            date,
                            final_ranking_score,
                            rank_position
                        FROM strategy_ranking 
                        WHERE strategy_name = ? AND date = ?
                        ORDER BY rank_position
                        """
                        df = pd.read_sql_query(simple_query, db.get_connection(), params=[strategy_name, date_str])
                        if not df.empty:
                            df = df.rename(columns={'rank_position': 'Rank'})
                            self.ranking_data[date_str] = df
                            loaded_count += 1
                            print(f"✅ 簡化查詢成功: {date_str} ({len(df)} 個交易對)")
                        else:
                            print(f"❌ 簡化查詢也失敗: {strategy_name} 在 {date_str}")
                    else:
                        print(f"❌ 數據庫中沒有找到: {strategy_name} 在 {date_str} 的數據")
                
                current_dt += timedelta(days=1)
            
            print(f"📊 成功從數據庫載入 {loaded_count} 天的排行榜數據")
            
        except Exception as e:
            print(f"❌ 從數據庫載入策略數據時出錯: {e}")
            import traceback
            traceback.print_exc()

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

    def run_backtest(self, strategy_name, start_date, end_date):
        """
        執行回測
        :param strategy_name: 策略名稱
        :param start_date: 開始日期 'YYYY-MM-DD'
        :param end_date: 結束日期 'YYYY-MM-DD'
        """
        print(f"🚀 開始策略回測: {strategy_name}")
        print(f"📅 回測期間: {start_date} 至 {end_date}")

        # 保存策略名稱用於檔案命名
        self.strategy_name = strategy_name
        
        # 生成唯一的回測ID，確保backtest_results和backtest_trades使用相同ID
        from datetime import datetime
        self.backtest_id = f"{strategy_name}_{start_date}_{end_date}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"🔍 回測ID: {self.backtest_id}")

        # 計算回測期間
        self.calculate_backtest_period(start_date, end_date)

        # 載入策略排行榜數據（從數據庫）
        self.load_strategy_ranking_data(strategy_name, start_date, end_date)

        if not self.ranking_data:
            print("沒有找到有效的策略排行榜數據，無法執行回測")
            return

        # 生成完整的回測日期範圍 (從start_date到end_date)
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        backtest_dates = []
        current_dt = start_dt
        while current_dt <= end_dt:
            backtest_dates.append(current_dt.strftime('%Y-%m-%d'))
            current_dt += timedelta(days=1)
        
        print(f"回測日期範圍: {backtest_dates}")
        print(f"可用策略檔案: {sorted(self.ranking_data.keys())}")
        print(f"開始處理 {len(backtest_dates)} 個回測日...")

        # 從第二天開始處理交易 (第一天只是載入策略，不交易)
        for i, date_str in enumerate(backtest_dates):
            current_time = f"{date_str} 08:00:00"
            
            print(f"處理第 {i+1}/{len(backtest_dates)} 個回測日: {date_str}")

            # 第一天：只記錄淨值，不做任何交易
            if i == 0:
                print("第一個回測日，只記錄初始狀態，不進行交易")
                # 記錄每日淨值
                self.add_daily_equity_record(date_str, self.total_balance)
                continue

            # 第二天開始：使用前一天的策略檔案進行交易
            prev_date_str = backtest_dates[i-1]  # 前一天的日期
            
            # 檢查前一天的策略檔案是否存在
            if prev_date_str not in self.ranking_data:
                print(f"前一天({prev_date_str})策略檔案不存在，跳過交易")
                # 記錄每日淨值
                self.add_daily_equity_record(date_str, self.total_balance)
                continue
            
            print(f"使用 {prev_date_str} 的策略檔案進行 {date_str} 的交易")

            # 1. 先計算資金費率收益（使用前一天的數據，對所有現有持倉）
            if len(self.positions) > 0:
                self.calculate_funding_rate_pnl_with_date(prev_date_str, current_time, date_str)

            # 2. 處理離場（使用前一天的策略檔案判斷）
            exit_candidates = self.get_exit_candidates(prev_date_str)
            for pair in exit_candidates:
                self.exit_position(pair, current_time)

            # 3. 處理進場（使用前一天的策略檔案判斷）
            entry_candidates = self.get_entry_candidates(prev_date_str)
            for pair in entry_candidates:
                if len(self.positions) < self.max_positions:
                    self.enter_position(pair, current_time)

            # 4. 記錄當前倉位狀態
            self.add_position_log(current_time)

            # 5. 更新最大回撤
            self.update_max_drawdown()

            # 6. 記錄每日淨值
            self.add_daily_equity_record(date_str, self.total_balance)

            print(f"  總餘額: {self.total_balance:.2f}, 持倉數: {len(self.positions)}")

        print("回測完成!")
        self.generate_reports()

    def get_unique_filename(self, base_path, base_name, extension, strategy_name=None):
        """
        生成唯一的檔案名稱，避免覆蓋
        :param base_path: 基礎路徑
        :param base_name: 基礎檔案名
        :param extension: 副檔名
        :param strategy_name: 策略名稱（可選）
        :return: 唯一的檔案路徑
        """
        # 獲取當日日期
        today = datetime.now().strftime('%Y%m%d')

        counter = 1
        while True:
            # 生成檔案名稱格式: base_name_YYYYMMDD(counter)_strategy.extension
            if strategy_name:
                filename = f"{base_name}_{today}({counter})_{strategy_name}.{extension}"
            else:
                filename = f"{base_name}_{today}({counter}).{extension}"
            full_path = os.path.join(base_path, filename)

            # 如果檔案不存在，就使用這個名稱
            if not os.path.exists(full_path):
                return full_path, filename

            counter += 1

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
            
            # 計算回測總天數
            total_days = self.backtest_days
            
            win_rate = self.calculate_win_rate()
            avg_holding_days = self.calculate_average_holding_days()
            
            # 計算夏普比率 (v5版本新增)
            sharpe_ratio = self.calculate_sharpe_ratio()
            
            # 確保有backtest_id
            if not hasattr(self, 'backtest_id') or not self.backtest_id:
                self.backtest_id = f"{self.strategy_name}_{self.start_date}_{self.end_date}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 準備回測結果摘要
            backtest_summary = {
                'backtest_id': self.backtest_id,
                'strategy_name': self.strategy_name,
                'start_date': self.start_date,
                'end_date': self.end_date,
                'initial_capital': float(self.initial_capital),
                'final_capital': float(final_capital),
                'total_return': float(total_return),
                'total_roi': float(total_roi),
                'roi': float(roi),
                'total_days': int(total_days),
                'max_drawdown': float(self.max_drawdown),
                'max_balance': float(self.max_balance),
                'position_size': float(self.position_size),
                'fee_rate': float(self.fee_rate),
                'exit_size': float(self.exit_size),
                'max_positions': int(self.max_positions),
                'entry_top_n': int(self.entry_top_n),
                'exit_threshold': int(self.exit_threshold),
                'backtest_days': int(self.backtest_days),
                'win_rate': float(win_rate),
                'avg_holding_days': float(avg_holding_days),
                'profit_days': int(self.profit_days),
                'loss_days': int(self.loss_days),
                'break_even_days': int(self.break_even_days),
                'total_trades': len(self.holding_periods)
            }
            
            # 插入回測結果摘要
            # 分離配置參數和結果數據
            config = {
                'initial_capital': backtest_summary['initial_capital'],
                'position_size': backtest_summary['position_size'],
                'fee_rate': backtest_summary['fee_rate'],
                'exit_size': backtest_summary['exit_size'],
                'max_positions': backtest_summary['max_positions'],
                'entry_top_n': backtest_summary['entry_top_n'],
                'exit_threshold': backtest_summary['exit_threshold']
            }
            
            results = {
                'final_balance': backtest_summary['final_capital'],
                'total_return': backtest_summary['total_roi'],
                'roi': backtest_summary['roi'],
                'total_days': backtest_summary['total_days'],
                'max_drawdown': backtest_summary['max_drawdown'],
                'win_rate': backtest_summary['win_rate'],
                'total_trades': backtest_summary['total_trades'],
                'profit_days': backtest_summary['profit_days'],
                'loss_days': backtest_summary['loss_days'],
                'avg_holding_days': backtest_summary['avg_holding_days'],
                'sharpe_ratio': float(sharpe_ratio),  # v5版本：加入夏普比率
                'notes': f"回測期間: {backtest_summary['total_days']} 天, 進場模式: {self.position_mode}"
            }
            
            db.insert_backtest_result(
                strategy_name=backtest_summary['strategy_name'],
                start_date=backtest_summary['start_date'],
                end_date=backtest_summary['end_date'],
                config=config,
                results=results,
                backtest_id=backtest_summary['backtest_id']
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
                        
                        # 轉換中文動作為英文動作（v5版本：排除手續費事件）
                        original_action = event.get('事件', event.get('類型', ''))
                        
                        # 排除手續費事件，避免被誤記為進場/離場
                        if '手續費' in original_action:
                            print(f"⚠️ 跳過手續費事件: {original_action}")
                            continue
                        
                        if original_action == '進場' or 'enter' in original_action.lower():
                            action = 'enter'
                        elif original_action == '離場' or 'exit' in original_action.lower():
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
                            'notes': f"原始事件: {original_action}"
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
                            'notes': f"每日淨值記錄: {equity_point['date']}"
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
        
        # 生成文字摘要 (v5版本：新增夏普比率和進場模式)
        summary_text = f"""
🎯 回測結果摘要 (backtest_v5)
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

⚙️ 策略參數 (v5新增進場模式)
----------------
進場模式: {self.position_mode}
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
            
            # 重置回測器狀態 (v5版本：保持 position_mode)
            self.__init__(
                initial_capital=self.initial_capital,
                position_size=self.position_size,
                fee_rate=self.fee_rate,
                exit_size=self.exit_size,
                max_positions=self.max_positions,
                entry_top_n=self.entry_top_n,
                exit_threshold=self.exit_threshold,
                position_mode=self.position_mode
            )
            
            # 執行回測（從數據庫）
            try:
                self.run_backtest(strategy, start_date, end_date)
                
                # 收集結果摘要
                final_capital = self.total_balance
                if pd.isna(final_capital) or not np.isfinite(final_capital):
                    final_capital = self.initial_capital
                
                total_roi = (final_capital - self.initial_capital) / self.initial_capital
                win_rate = self.calculate_win_rate()
                
                results_summary.append({
                    'strategy': strategy,
                    'initial_capital': self.initial_capital,
                    'final_capital': final_capital,
                    'total_return': final_capital - self.initial_capital,
                    'total_roi': total_roi,
                    'win_rate': win_rate,
                    'max_drawdown': self.max_drawdown
                })
                
                print(f"✅ 策略 {strategy} 回測完成")
                
            except Exception as e:
                print(f"❌ 策略 {strategy} 回測失敗: {e}")
                results_summary.append({
                    'strategy': strategy,
                    'initial_capital': self.initial_capital,
                    'final_capital': self.initial_capital,
                    'total_return': 0,
                    'total_roi': 0,
                    'win_rate': 0,
                    'max_drawdown': 0,
                    'error': str(e)
                })
        
        # 顯示所有策略的比較結果
        self.display_strategy_comparison(results_summary)

    def display_strategy_comparison(self, results_summary):
        """
        顯示策略比較結果
        :param results_summary: 結果摘要列表
        """
        print("\n" + "="*80)
        print("📈 策略回測結果比較")
        print("="*80)
        
        # 表頭
        print(f"{'策略名稱':<20} {'總報酬率':<12} {'勝率':<8} {'最大回撤':<10} {'最終資金':<12} {'狀態':<8}")
        print("-"*80)
        
        # 排序：按總報酬率降序
        sorted_results = sorted(results_summary, key=lambda x: x['total_roi'], reverse=True)
        
        for result in sorted_results:
            strategy = result['strategy']
            roi = result['total_roi']
            win_rate = result['win_rate']
            max_dd = result['max_drawdown']
            final_capital = result['final_capital']
            
            status = "❌ 失敗" if 'error' in result else "✅ 成功"
            
            print(f"{strategy:<20} {roi:>10.2%} {win_rate:>6.1%} {max_dd:>8.2%} ${final_capital:>10,.0f} {status:<8}")
        
        # 最佳策略
        if sorted_results and 'error' not in sorted_results[0]:
            best_strategy = sorted_results[0]
            print(f"\n🏆 最佳策略: {best_strategy['strategy']} (報酬率: {best_strategy['total_roi']:.2%})")


# 使用範例
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 智能策略回測系統")
    print("="*70)
    
    # 初始化回測器（使用全域變數，v5版本加入 position_mode）
    backtest = FundingRateBacktest(
        initial_capital=INITIAL_CAPITAL,
        position_size=POSITION_SIZE,
        fee_rate=FEE_RATE,
        exit_size=EXIT_SIZE,
        max_positions=MAX_POSITIONS,
        entry_top_n=ENTRY_TOP_N,
        exit_threshold=EXIT_THRESHOLD,
        position_mode=POSITION_MODE
    )

    # 互動式策略選擇（從數據庫）
    selected_strategies = backtest.interactive_strategy_selection(START_DATE, END_DATE)
    
    if not selected_strategies:
        print("❌ 沒有選擇任何策略，程式結束")
        exit(0)

    # 顯示當前參數設定
    print("\n" + "="*70)
    print("📋 回測參數設定")
    print("="*70)
    print("策略參數 (backtest_v5):")
    print(f"- 初始資金: ${INITIAL_CAPITAL:,}")
    print(f"- 進場模式: {POSITION_MODE}")
    print(f"- 每次進場資金比例: {POSITION_SIZE:.1%}")
    print(f"- 手續費率: {FEE_RATE:.4%}")
    print(f"- 每次離場資金比例: {EXIT_SIZE:.1%}")
    print(f"- 最大持倉數: {MAX_POSITIONS}")
    print(f"- 進場條件: 綜合評分前{ENTRY_TOP_N}名")
    print(f"- 離場條件: 排名跌出前{EXIT_THRESHOLD}名")
    print(f"- 回測期間: {START_DATE} 至 {END_DATE}")
    print(f"- 選擇的策略: {selected_strategies}")
    print("- 💾 數據源: 數據庫 (策略排行榜表)")
    print("=" * 70)

    # 執行回測（從數據庫）
    if len(selected_strategies) == 1:
        # 單一策略回測
        strategy = selected_strategies[0]
        print(f"\n🎯 執行單一策略回測: {strategy}")
        backtest.run_backtest(strategy, START_DATE, END_DATE)
    else:
        # 多策略回測
        print(f"\n🎯 執行多策略回測: {len(selected_strategies)} 個策略")
        backtest.run_multiple_backtests(selected_strategies, START_DATE, END_DATE)