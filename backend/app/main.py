# -*- coding: utf-8 -*-
"""FastAPI 应用入口：/health + 业务路由 + 治理路由 + Agent 路由 + 静态前端 + 定时调度。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core import config
from .api.business import ALL_BUSINESS_ROUTERS
from .api.gov import gov_router

app = FastAPI(
    title="全国连锁零售经营决策 Agent 系统",
    description="Mock 原系统 + 经营决策 Agent（目标—感知—诊断—决策—执行—治理—评估）",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "retail-agent-platform"}


@app.on_event("startup")
def _startup():
    from .core.db import init_db, session_scope
    from .governance.auth import seed_users
    init_db()
    with session_scope() as s:
        seed_users(s)
    _start_scheduler()


def _start_scheduler():
    """定时任务：每小时感知扫描（RETAIL_SCHEDULER=1 时启用，默认关闭避免演示干扰）。"""
    import os
    if os.getenv("RETAIL_SCHEDULER", "0") != "1":
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from .core.db import session_scope
        from .agents import perception

        def scan_job():
            with session_scope() as s:
                perception.scan(s)

        sched = BackgroundScheduler(timezone="Asia/Shanghai")
        sched.add_job(scan_job, "interval", hours=1, id="perception_scan",
                      next_run_time=None)
        sched.start()
        app.state.scheduler = sched
    except Exception as exc:  # noqa: BLE001
        print(f"[scheduler] 启动失败（不影响服务）: {exc}")


for r in ALL_BUSINESS_ROUTERS:
    app.include_router(r, prefix=config.API_PREFIX)
app.include_router(gov_router, prefix=config.API_PREFIX)

from .api.agent import register as _register_agent  # noqa: E402
from .api.world import register as _register_world  # noqa: E402
_register_agent(app)
_register_world(app)

# 静态前端（无构建步骤，直接挂载 web/ 目录）
if config.WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(config.WEB_DIR / "index.html")
