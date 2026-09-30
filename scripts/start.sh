#!/usr/bin/env bash
# 一键启动（Linux/macOS/Git Bash）：安装依赖 → 生成数据（如无）→ 启动服务
set -e
cd "$(dirname "$0")/.."
echo "============================================"
echo " 全国连锁零售经营决策 Agent 系统 - 一键启动"
echo "============================================"
pip install -q -r backend/requirements.txt
if [ ! -f backend/data_local/retail.db ]; then
  echo "首次运行，生成数据中（约 1 分钟）…"
  python scripts/generate.py
fi
echo "启动服务: http://127.0.0.1:8300"
cd backend && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8300
