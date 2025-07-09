#!/bin/bash
# crontab 管理腳本 (UTC+0 時間模式)
# 使用方法：./manage_cron.sh [選項]

PROJECT_PATH="/Users/waynechen/Downloads/Arbitrage01-3"
PYTHON_PATH="$PROJECT_PATH/venv/bin/python3"
SCRIPT_PATH="$PROJECT_PATH/get_return_v2.py"
LOG_PATH="$PROJECT_PATH/logs/cron_get_return.log"

# 完整的 cron 任務命令
CRON_COMMAND="cd $PROJECT_PATH && $PYTHON_PATH $SCRIPT_PATH --auto >> $LOG_PATH 2>&1"

# 獲取系統時區偏移量（相對於UTC的小時數）
get_timezone_offset() {
    local offset=$(date +%z)
    local hours=${offset:1:2}
    local sign=${offset:0:1}
    
    # 移除前導零，避免被當作八進制
    hours=$((10#$hours))
    
    if [ "$sign" = "+" ]; then
        echo $hours
    else
        echo "-$hours"
    fi
}

# 將 UTC+0 時間轉換為本地時間
convert_utc_to_local() {
    local utc_hour=$1
    local utc_minute=$2
    local offset=$(get_timezone_offset)
    
    local local_hour=$((utc_hour + offset))
    
    # 處理小時跨日問題
    if [ $local_hour -ge 24 ]; then
        local_hour=$((local_hour - 24))
    elif [ $local_hour -lt 0 ]; then
        local_hour=$((local_hour + 24))
    fi
    
    echo "$utc_minute $local_hour"
}

# 將本地時間轉換回 UTC+0 顯示
convert_local_to_utc() {
    local local_hour=$1
    local local_minute=$2
    local offset=$(get_timezone_offset)
    
    local utc_hour=$((local_hour - offset))
    
    # 處理小時跨日問題
    if [ $utc_hour -ge 24 ]; then
        utc_hour=$((utc_hour - 24))
    elif [ $utc_hour -lt 0 ]; then
        utc_hour=$((utc_hour + 24))
    fi
    
    printf "%02d:%02d UTC+0" $utc_hour $local_minute
}

function show_help() {
    echo "crontab 管理腳本 (UTC+0 時間模式)"
    echo "使用方法：./manage_cron.sh [選項]"
    echo ""
    echo "系統時區：$(date +%Z) (UTC$(date +%z | sed 's/\([+-]\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1\2/'))"
    echo ""
    echo "選項："
    echo "  -s, --show      顯示當前 crontab 設定"
    echo "  -d, --delete    刪除所有 crontab 任務"
    echo "  -0, --midnight  設定每天 00:00 (UTC+0) 執行"
    echo "  -8, --morning   設定每天 08:00 (UTC+0) 執行"
    echo "  -h, --help      顯示此說明"
    echo ""
    echo "自訂時間："
    echo "  --custom \"分 時 日 月 週\"  自訂 cron 時間 (UTC+0)"
    echo "  例如：--custom \"30 14 * * *\"  (每天 14:30 UTC+0)"
    echo ""
    echo "交互模式："
    echo "  不加參數直接執行即可進入交互模式"
}

function show_current() {
    echo "當前 crontab 設定："
    local cron_output=$(crontab -l 2>/dev/null)
    
    if [ -z "$cron_output" ]; then
        echo "沒有 crontab 任務"
    else
        echo "$cron_output"
        echo ""
        # 解析並顯示 UTC+0 時間
        local cron_time=$(echo "$cron_output" | grep -o '^[0-9]* [0-9]*' | head -1)
        if [ -n "$cron_time" ]; then
            local minute=$(echo "$cron_time" | cut -d' ' -f1)
            local hour=$(echo "$cron_time" | cut -d' ' -f2)
            local utc_time=$(convert_local_to_utc $hour $minute)
            echo "對應時間：$utc_time"
        fi
    fi
}

function delete_all() {
    echo "刪除所有 crontab 任務..."
    crontab -r 2>/dev/null || echo "沒有 crontab 任務需要刪除"
    echo "完成"
}

function set_midnight() {
    echo "設定每天 00:00 (UTC+0) 執行..."
    local converted_time=$(convert_utc_to_local 0 0)
    echo "$converted_time * * * $CRON_COMMAND" | crontab -
    echo "完成"
    show_current
}

function set_morning() {
    echo "設定每天 08:00 (UTC+0) 執行..."
    local converted_time=$(convert_utc_to_local 8 0)
    echo "$converted_time * * * $CRON_COMMAND" | crontab -
    echo "完成"
    show_current
}

function set_custom() {
    local time_spec="$1"
    echo "設定自訂時間：$time_spec (UTC+0)"
    
    # 解析時間規格
    local minute=$(echo "$time_spec" | cut -d' ' -f1)
    local hour=$(echo "$time_spec" | cut -d' ' -f2)
    local day=$(echo "$time_spec" | cut -d' ' -f3)
    local month=$(echo "$time_spec" | cut -d' ' -f4)
    local dow=$(echo "$time_spec" | cut -d' ' -f5)
    
    # 只轉換小時和分鐘（如果都是數字）
    if [[ "$hour" =~ ^[0-9]+$ ]] && [[ "$minute" =~ ^[0-9]+$ ]]; then
        local converted_time=$(convert_utc_to_local $hour $minute)
        local converted_minute=$(echo "$converted_time" | cut -d' ' -f1)
        local converted_hour=$(echo "$converted_time" | cut -d' ' -f2)
        echo "$converted_minute $converted_hour $day $month $dow $CRON_COMMAND" | crontab -
    else
        echo "警告：複雜時間格式可能需要手動調整時區"
        echo "$time_spec $CRON_COMMAND" | crontab -
    fi
    
    echo "完成"
    show_current
}

# 交互模式主函數
interactive_mode() {
    while true; do
        echo ""
        echo "crontab 管理腳本 (UTC+0 時間模式)"
        echo "項目路徑：$PROJECT_PATH"
        echo "系統時區：$(date +%Z) (UTC$(date +%z | sed 's/\([+-]\)\([0-9]\{2\}\)\([0-9]\{2\}\)/\1\2/'))"
        echo ""
        
        # 顯示當前設定
        show_current
        echo ""
        
        # 顯示選單
        echo "請選擇操作："
        echo "  1. 查看當前設定"
        echo "  2. 設定每日執行時間 (UTC+0)"
        echo "  3. 刪除所有任務"
        echo "  4. 退出"
        echo ""
        
        # 讀取用戶輸入
        read -p "請輸入選項 (1-4): " choice
        
        case "$choice" in
            1)
                echo ""
                show_current
                read -p "按 Enter 繼續..."
                ;;
            2)
                interactive_set_daily
                ;;
            3)
                interactive_delete_all
                ;;
            4)
                echo "退出"
                exit 0
                ;;
            *)
                echo "無效選項，請輸入 1-4"
                read -p "按 Enter 繼續..."
                ;;
        esac
    done
}

# 交互模式：設定每日執行時間
interactive_set_daily() {
    echo ""
    echo "設定每日執行時間 (UTC+0)"
    echo ""
    
    # 輸入小時
    while true; do
        read -p "請輸入小時 (0-23): " hour
        if [[ "$hour" =~ ^[0-9]+$ ]] && [ "$hour" -ge 0 ] && [ "$hour" -le 23 ]; then
            break
        else
            echo "請輸入有效的小時數 (0-23)"
        fi
    done
    
    # 輸入分鐘
    while true; do
        read -p "請輸入分鐘 (0-59): " minute
        if [[ "$minute" =~ ^[0-9]+$ ]] && [ "$minute" -ge 0 ] && [ "$minute" -le 59 ]; then
            break
        else
            echo "請輸入有效的分鐘數 (0-59)"
        fi
    done
    
    # 顯示確認資訊
    echo ""
    echo "確認設定："
    printf "UTC+0 時間：%02d:%02d\n" $hour $minute
    
    local converted_time=$(convert_utc_to_local $hour $minute)
    local local_minute=$(echo "$converted_time" | cut -d' ' -f1)
    local local_hour=$(echo "$converted_time" | cut -d' ' -f2)
    printf "本地時間：%02d:%02d %s\n" $local_hour $local_minute "$(date +%Z)"
    echo "cron 設定：$local_minute $local_hour * * *"
    echo ""
    
    # 確認執行
    read -p "確認執行嗎？(y/n): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo "$converted_time * * * $CRON_COMMAND" | crontab -
        echo "設定完成！"
    else
        echo "已取消"
    fi
    
    read -p "按 Enter 繼續..."
}

# 交互模式：刪除所有任務
interactive_delete_all() {
    echo ""
    echo "確認刪除所有 crontab 任務？"
    echo "警告：這將移除所有定時任務！"
    echo ""
    
    read -p "確認刪除嗎？(y/n): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        delete_all
        echo "所有任務已刪除！"
    else
        echo "已取消"
    fi
    
    read -p "按 Enter 繼續..."
}

# 主要邏輯
case "${1:-}" in
    -s|--show)
        show_current
        ;;
    -d|--delete)
        delete_all
        ;;
    -0|--midnight)
        set_midnight
        ;;
    -8|--morning)
        set_morning
        ;;
    --custom)
        if [[ -n "${2:-}" ]]; then
            set_custom "$2"
        else
            echo "錯誤：請提供時間規格"
            echo "例如：--custom \"30 14 * * *\""
        fi
        ;;
    -h|--help)
        show_help
        ;;
    "")
        interactive_mode
        ;;
    *)
        echo "未知選項：$1"
        show_help
        exit 1
        ;;
esac 