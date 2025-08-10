#!/bin/bash
# 測試多用戶設定腳本

echo "========================================="
echo "多用戶套利收益分析測試"
echo "========================================="
echo ""

# 測試 User 1
echo "📊 測試 User 1..."
echo "-----------------------------------------"
python3 get_return_multi_user.py --auto --user user1
echo ""

# 測試 User 2 (如果 .env.user2 已設定)
if [ -f ".env.user2" ]; then
    echo "📊 測試 User 2..."
    echo "-----------------------------------------"
    python3 get_return_multi_user.py --auto --user user2
    echo ""
fi

# 顯示結果
echo "========================================="
echo "📁 生成的檔案："
echo "-----------------------------------------"

if [ -d "csv/Return_user1" ]; then
    echo "User 1 檔案："
    ls -la csv/Return_user1/*.csv 2>/dev/null | tail -5
    echo ""
fi

if [ -d "csv/Return_user2" ]; then
    echo "User 2 檔案："
    ls -la csv/Return_user2/*.csv 2>/dev/null | tail -5
    echo ""
fi

echo "========================================="
echo "✅ 測試完成"
echo "========================================="