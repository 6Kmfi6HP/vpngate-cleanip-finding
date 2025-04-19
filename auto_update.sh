#!/bin/bash

# 设置脚本错误时立即退出
set -e

# 记录开始时间
echo "开始执行自动更新脚本: $(date)"

# 如果存在虚拟环境则激活
if [ -d ".venv" ]; then
    echo "激活虚拟环境..."
    source .venv/bin/activate
fi

# 运行Python脚本
echo "运行 check_vpn_risk.py..."
python3 check_vpn_risk.py

# Git 操作
echo "执行 Git 操作..."
git add .
git commit -m "Auto update VPN risk data: $(date '+%Y-%m-%d %H:%M:%S')"
git push

# 如果使用了虚拟环境，则退出虚拟环境
if [ -d ".venv" ]; then
    deactivate
fi

echo "脚本执行完成: $(date)" 