# -*- coding: utf-8 -*-
"""构建 GitHub Pages 静态快照：web 前端 + 预抓取的 API JSON（只读预览）。

流程：独立临时库重建演示世界（小规模，种子固定）→ 跑 Agent 流水线 →
风控审批通过全部高风险 → TestClient 抓取全部页面数据 → public/ 目录。
CI（.github/workflows/deploy-pages.yml）push main 后自动执行并发布。
"""
import json
import os
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# 独立临时库，不污染本地演示数据
os.environ["RETAIL_DB"] = os.path.join(tempfile.mkdtemp(prefix="retail_snap_"), "snap.db")

from app.bootstrap import bootstrap  # noqa: E402
from app.agents import orchestrator  # noqa: E402

# 页面消费的全部 GET 端点（与 web/assets/app.js 的 fetchJSON 参数一致；
# 文件名规则 = snapPath()：/api/a/b?x=1 → snapshot/a-b-x1.json）
ENDPOINTS = [
    "/api/kpi/overview",
    "/api/kpi/trend?days=30",
    "/api/kpi/stores?limit=10",
    "/api/agent/anomalies?limit=100",
    "/api/agent/anomalies?limit=8",
    "/api/agent/decisions?limit=100",
    "/api/agent/executions?limit=100",
    "/api/gov/approvals?status=pending",
    "/api/gov/approvals?limit=50",
    "/api/gov/audit-logs?limit=200",
]


def snap_name(path: str) -> str:
    p, _, q = path.partition("?")
    qs = "-" + "".join(ch for ch in q if ch.isalnum()) if q else ""
    return p.replace("/api/", "").replace("/", "-") + qs + ".json"


def main() -> None:
    print("[1/3] 重建演示世界（45 天 × 12 店 × 100 SKU，种子 42）…")
    bootstrap(days=45, stores=12, skus=100, seed=42)

    print("[2/3] 运行 Agent 流水线 + 风控审批…")
    from app.core.db import session_scope
    from app.agents import execution as execution_agent
    from app.governance.approvals import decide_approval
    from app.governance.auth import Actor
    from app.models import Approval
    from sqlmodel import select
    with session_scope() as s:
        orchestrator.run_pipeline(s)
        risk = Actor(id="usr_risk_01", username="risk_approver_01", name="吴风控",
                     role="risk_approver")
        for ap in s.exec(select(Approval).where(Approval.status == "pending")).all():
            decide_approval(s, ap.id, "approve", risk, note="快照演示：审批通过")
        execution_agent.execute_approved(s)

    print("[3/3] 抓取 API 快照 → public/ …")
    from fastapi.testclient import TestClient
    from app.main import app
    public = ROOT / "public"
    if public.exists():
        shutil.rmtree(public)
    (public / "snapshot").mkdir(parents=True)
    shutil.copy2(ROOT / "web" / "index.html", public / "index.html")
    shutil.copytree(ROOT / "web" / "assets", public / "assets", dirs_exist_ok=True)

    with TestClient(app) as client:
        for ep in ENDPOINTS:
            r = client.get(ep)
            r.raise_for_status()
            (public / "snapshot" / snap_name(ep)).write_text(
                json.dumps(r.json(), ensure_ascii=False), encoding="utf-8")
            print("   ✓", ep)
        # 异常详情（前 10 个，含故事线异常优先）
        anomalies = client.get("/api/agent/anomalies?limit=100").json()["items"]
        ranked = sorted(anomalies, key=lambda a: (a.get("severity") == "critical",),
                        reverse=True)
        for a in ranked[:10]:
            r = client.get(f"/api/agent/anomalies/{a['id']}")
            r.raise_for_status()
            (public / "snapshot" / snap_name(f"/api/agent/anomalies/{a['id']}")).write_text(
                json.dumps(r.json(), ensure_ascii=False), encoding="utf-8")

    n = len(list((public / "snapshot").glob("*.json")))
    print(f"完成：public/ 共 {n} 个快照 JSON + 静态前端（只读预览）")


if __name__ == "__main__":
    main()
