#!/bin/bash
# ============================================================
# 加密货币情绪监控系统 - 最小化 venv 部署脚本
# CentOS 7.9 + 宝塔面板 兼容版本
# ============================================================
#
# ⚠️ 重要说明：
# - 此脚本安装 Python 3.8 到 /usr/local/bin/python3.8
# - 不会影响系统自带的 Python 2.7（/usr/bin/python）
# - 不会影响宝塔面板的正常运行
#
# 使用方法:
#   chmod +x setup_venv.sh
#   ./setup_venv.sh
#
# ============================================================

set -e

echo ""
echo "=========================================="
echo "加密货币情绪监控系统 - venv 部署"
echo "=========================================="
echo ""

# ============================================================
# 步骤 1: 检查/安装 Python 3.8
# ============================================================

install_python38() {
    echo "📦 开始安装 Python 3.8（不影响系统 Python 2.7）..."
    echo ""
    
    # 安装编译依赖
    echo "[1/4] 安装编译依赖..."
    sudo yum groupinstall -y "Development Tools" > /dev/null 2>&1
    sudo yum install -y openssl-devel bzip2-devel libffi-devel zlib-devel sqlite-devel readline-devel > /dev/null 2>&1
    
    # 下载 Python 3.8
    echo "[2/4] 下载 Python 3.8.18..."
    cd /tmp
    if [ ! -f "Python-3.8.18.tgz" ]; then
        wget -q https://www.python.org/ftp/python/3.8.18/Python-3.8.18.tgz
    fi
    tar -xzf Python-3.8.18.tgz
    cd Python-3.8.18
    
    # 编译安装（使用 altinstall 避免覆盖系统 Python）
    echo "[3/4] 编译安装（约5-10分钟）..."
    ./configure --enable-optimizations --prefix=/usr/local > /dev/null 2>&1
    make -j$(nproc) > /dev/null 2>&1
    
    # ⚠️ 关键：使用 altinstall 而不是 install
    # altinstall 不会创建 python 和 pip 软链接，不会影响系统 Python 2.7
    sudo make altinstall > /dev/null 2>&1
    
    echo "[4/4] 清理临时文件..."
    rm -rf /tmp/Python-3.8.18*
    
    echo ""
    echo "✅ Python 3.8 安装完成！"
    echo "   安装位置: /usr/local/bin/python3.8"
    echo "   系统 Python 2.7: /usr/bin/python（未受影响）"
    echo ""
}

# 检查 Python 3.8 是否已安装
PYTHON_CMD=""
if command -v python3.8 &> /dev/null; then
    PYTHON_CMD="python3.8"
    echo "✅ 检测到 Python 3.8 已安装"
elif command -v /usr/local/bin/python3.8 &> /dev/null; then
    PYTHON_CMD="/usr/local/bin/python3.8"
    echo "✅ 检测到 Python 3.8 已安装"
else
    echo "⚠️  未检测到 Python 3.8"
    echo ""
    read -p "是否现在安装 Python 3.8？（不会影响 Python 2.7 和宝塔）[y/N]: " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_python38
        PYTHON_CMD="/usr/local/bin/python3.8"
    else
        echo "❌ 请先安装 Python 3.8 后再运行此脚本"
        exit 1
    fi
fi

VERSION=$($PYTHON_CMD --version 2>&1)
echo "使用 Python: $VERSION"
echo ""

# ============================================================
# 步骤 2: 创建虚拟环境并安装依赖
# ============================================================

echo "[1/3] 创建虚拟环境..."
$PYTHON_CMD -m venv venv

echo "[2/3] 安装依赖..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "[3/3] 验证安装..."
python -c "import main; print('✅ 模块加载成功')"

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo ""
echo "启动命令:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "后台运行（推荐）:"
echo "  nohup venv/bin/python main.py > output.log 2>&1 &"
echo ""
echo "查看统计:"
echo "  venv/bin/python main.py --stats"
echo "=========================================="
