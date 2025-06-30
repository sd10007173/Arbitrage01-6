# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Database and Core Architecture

This is a cryptocurrency funding rate arbitrage analysis and backtesting system centered around **`data/funding_rate.db`** SQLite database.

**Core Data Flow:**
```
Market Cap Filtering → Exchange Support Verification → Funding Rate Collection → 
Difference Calculation → Return Metrics → Strategy Ranking → Backtesting → Visualization
```

**Main Database Tables:**
- `trading_pair`: Market cap ranked crypto pairs with exchange support flags
- `funding_rate_history`: Hourly funding rate data from multiple exchanges
- `funding_rate_diff`: Cross-exchange funding rate differences
- `return_metrics`: Multi-timeframe return calculations (1d, 2d, 7d, 14d, 30d, all)
- `strategy_ranking`: Strategy-based ranking results
- `backtest_results` & `backtest_trades`: Backtesting results and trade details

## Core System Workflow Commands

### 1. Market Cap and Exchange Setup
```bash
# Get top N market cap coins (user input required)
python market_cap_trading_pair.py

# Verify exchange support and get listing dates
python exchange_trading_pair_v10.py  # Latest version with Bybit perpetual contract fix

# NOTE: v10 fixes Bybit symbol format issue (XCN/USDT:USDT vs XCN/USDT)
```

### 2. Funding Rate Data Collection
```bash
# Batch collect funding rate history (interactive input)
python fetch_FR_history_group_v2.py

# Calculate cross-exchange funding rate differences
python calculate_FR_diff_v3.py

# Calculate return metrics across multiple timeframes
python calculate_FR_return_list_v2.py
```

### 3. Strategy Analysis
```bash
# Generate strategy rankings (interactive mode)
python strategy_ranking_v2.py

# Factor-based strategies (alternative approach)
python factor_strategies/run_factor_strategies.py

# Backtest strategy performance
python backtest_v3.py
```

### 4. Visualization
```bash
# Generate return charts for all trading pairs
python draw_return_metrics.py
```

## Key Configuration Files

**Strategy Configurations:**
- `ranking_config.py`: Main strategy definitions (original, momentum_focused, stability_focused)
- `factor_strategies/factor_strategy_config.py`: Factor-based strategy configurations
- `ranking_engine.py`: Core ranking calculation engine

## Database Operations

**Core Database Module:** `database_operations.py`
- Provides unified database interface
- Handles batch operations and transactions
- Use this for any database interactions

**Schema Definition:** `database_schema.py`
- Defines table structures and indexes
- Run to initialize or update database schema

## Testing and Verification

**Core Testing:**
```bash
# Comprehensive system test with sample data
python prepare_test_data.py  # Seeds test data

# Factor strategy testing
python factor_strategies/test_factor_strategies.py

# Database integrity checks
python view_database_simple.py
```

**Performance Testing:** See strategy_ranking_performance_report.md for detailed performance analysis and optimization guidelines.

## Critical Exchange Trading Pair Versioning

**IMPORTANT:** Always use `exchange_trading_pair_v10.py` (or latest version) due to critical symbol format issues:
- v9 and earlier: Incorrect Bybit perpetual contract format (XCN/USDT instead of XCN/USDT:USDT)
- v10: Fixed Bybit perpetual contract format, ensuring accurate exchange support detection

## Factor Strategy System

**Location:** `factor_strategies/` directory
- Alternative strategy framework using mathematical factors
- Integrates with existing `strategy_ranking` table
- Interactive execution via `run_factor_strategies.py`
- Supports cerebrum_core, cerebrum_momentum, cerebrum_stability strategies

## Data Requirements and Dependencies

**Minimum Data for Strategy Execution:**
- Market cap data from CoinGecko API
- Exchange support verification (Binance, Bybit, OKX, Gate)
- Minimum 30-90 days of funding rate history (strategy dependent)
- Cross-exchange funding rate pairs (Binance-Bybit focus)

**API Dependencies:**
- CoinGecko API (market cap data)
- CCXT library (exchange data)
- No API keys required for basic functionality

## File Naming Conventions

**Version Control:** Core files use versioned naming (v1, v2, etc.)
- Always check for latest version before modifications
- Legacy versions kept for reference and rollback capability
- Test files often reference specific versions

**Log Files:** Located in `logs/` directory
- `calculate_FR_diff_log.txt`: Funding rate difference calculation logs
- `scheduler_log.txt`: Automated execution logs

## Common Development Tasks

**Adding New Exchanges:**
1. Update `exchange_trading_pair_v10.py` with new exchange integration
2. Modify `fetch_FR_history_group_v2.py` for funding rate collection
3. Update database schema for new exchange support columns

**Adding New Strategies:**
1. Add configuration to `ranking_config.py` or `factor_strategies/factor_strategy_config.py`
2. Test via interactive interfaces before production use

**Performance Optimization:**
- Use batch processing for large datasets
- Implement chunked database operations for memory efficiency
- Reference performance reports in documentation for optimization guidance

## Security and Data Integrity

- No sensitive API keys stored in code
- SQLite database provides ACID compliance
- Backup mechanisms via `tests/smart_backup.py`
- Input validation for all user-provided data

## Development Environment

**Dependencies:** Install via `pip install -r requirements.txt`
- Key packages: pandas, numpy, scipy, matplotlib, ccxt, pycoingecko

**Python Version:** 3.7+ required for modern pandas/numpy compatibility
**Database:** SQLite 3 (no external database server required)