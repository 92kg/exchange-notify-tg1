#!/bin/bash
# 加密货币情绪监控 - 重启脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  加密货币情绪监控 - 重启服务"
echo "=========================================="

# 停止旧进程
echo "[1/3] 停止旧进程..."
OLD_PID=$(pgrep -f "python main.py" 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "  发现进程 PID: $OLD_PID，正在终止..."
    kill $OLD_PID 2>/dev/null
    sleep 2
    # 检查是否还在运行
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "  进程未响应，强制终止..."
        kill -9 $OLD_PID 2>/dev/null
        sleep 1
    fi
    echo "  旧进程已停止"
else
    echo "  未发现运行中的进程"
fi

# 启动新进程
echo "[2/3] 启动新进程..."
nohup venv/bin/python main.py > output.log 2>&1 &
NEW_PID=$!
sleep 2

# 检查是否启动成功
echo "[3/3] 验证启动状态..."
if ps -p $NEW_PID > /dev/null 2>&1; then
    echo "  ✅ 启动成功！新进程 PID: $NEW_PID"
    echo ""
    echo "查看日志: tail -f output.log"
    echo "停止服务: kill $NEW_PID"
else
    echo "  ❌ 启动失败，请检查错误日志:"
    tail -20 output.log
    exit 1
fi

echo "=========================================="
