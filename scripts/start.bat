@echo off
chcp 65001 >nul
REM 一键启动：安装依赖 → 生成数据（如无）→ 启动服务
cd /d "%~dp0.."
echo ============================================
echo  全国连锁零售经营决策 Agent 系统 - 一键启动
echo ============================================
pip install -q -r backend\requirements.txt 2>nul
python -c "import sqlite3,os; db=r'backend\data_local\retail.db'; ok=os.path.exists(db); print('DB存在' if ok else '首次运行，生成数据中(约1分钟)…'); exit(0 if ok else 1)" 2>nul
if errorlevel 1 (
    python scripts\generate.py
)
echo 启动服务: http://127.0.0.1:8300
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8300
