# 安全配置指南

## 🔒 敏感資訊保護

此專案包含 API 金鑰和其他敏感資訊，已透過 `.gitignore` 進行保護。

### 📋 已保護的檔案類型

- `.env*` - 所有環境設定檔案（除了 `.env.example` 和 `.env.template`）
- `api_config.py` - API 配置檔案
- `logs/` - 日誌目錄（可能包含敏感資訊）
- `crontab_backup_*.txt` - Crontab 備份檔案

### 🚀 首次設定步驟

1. **複製範例環境檔案：**
   ```bash
   cp .env.example .env.your_username
   ```

2. **編輯您的環境檔案：**
   ```bash
   nano .env.your_username
   ```

3. **填入真實的 API 金鑰：**
   - `BINANCE_API_KEY` - 您的 Binance API 金鑰
   - `BINANCE_SECRET_KEY` - 您的 Binance 密鑰
   - `BYBIT_API_KEY` - 您的 Bybit API 金鑰
   - `BYBIT_SECRET_KEY` - 您的 Bybit 密鑰
   - `TELEGRAM_BOT_TOKEN` - Telegram 機器人令牌
   - `TELEGRAM_CHAT_ID` - Telegram 聊天 ID

4. **測試配置：**
   ```bash
   python3 get_return_multi_user.py --auto --user your_username
   ```

### ⚠️ 重要安全注意事項

- **絕不要** 將包含真實 API 金鑰的檔案提交到 Git
- **絕不要** 在公開場合分享您的 API 金鑰
- **定期輪換** 您的 API 金鑰
- **使用最小權限** 設定 API 金鑰（只給予必要的交易和查詢權限）

### 📊 多用戶設定

每個用戶都應該有自己的環境檔案：
- `.env.alice` - Alice 的配置
- `.env.bob` - Bob 的配置
- `.env.charlie` - Charlie 的配置

### 🔄 批次執行

系統會自動偵測所有 `.env.{username}` 檔案並執行對應用戶的分析。

### 🛡️ 如果意外提交了敏感資訊

如果您意外提交了包含 API 金鑰的檔案：

1. **立即更換 API 金鑰**
2. **從 Git 歷史中移除敏感資訊：**
   ```bash
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch path/to/sensitive/file' \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **強制推送到遠端：**
   ```bash
   git push origin --force --all
   ```

### 📞 需要協助？

如有任何安全問題，請聯繫系統管理員。