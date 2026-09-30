# -*- coding: utf-8 -*-
"""Playwright 端到端测试（核心闭环：R1-R5）。

覆盖：R2 自动发现异常 → R3 根因分析 → R4 补货/促销建议 → R5 审批执行 → 审计追溯。
自包含：启动临时 uvicorn（独立 DB）→ 生成小世界 → UI 与 API 混合驱动。
（按 2026-09-30 产品审计裁决，世界推演/复盘页已从 UI 移除，对应断言收缩为核心闭环。）
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "backend"
PORT = 8399
BASE = f"http://127.0.0.1:{PORT}"


def _wait_health(proc, timeout=60):
    import urllib.request
    dl = time.time() + timeout
    while time.time() < dl:
        if proc.poll() is not None:
            raise RuntimeError(f"服务进程提前退出: {proc.returncode}")
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError("服务健康检查超时")


@pytest.fixture(scope="module", autouse=True)
def server():
    tmp = tempfile.mkdtemp(prefix="retail_e2e_")
    env = os.environ.copy()
    env["RETAIL_DB"] = os.path.join(tmp, "e2e.db")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT),
         "--host", "127.0.0.1", "--log-level", "warning"],
        cwd=str(BACKEND), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        _wait_health(proc)
        yield BASE
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


def _api(method, path, body=None, token="tok_risk_01"):
    import urllib.request
    req = urllib.request.Request(
        BASE + path, method=method,
        headers={"Content-Type": "application/json", "X-Auth-Token": token},
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


@pytest.fixture(scope="module", autouse=True)
def demo_state(server):
    """生成小世界 + 跑半程流水线（保留待审批项给 UI 操作）。"""
    _api("POST", "/api/world/generate",
         {"days": 45, "stores": 12, "skus": 100, "seed": 42, "inject": True})
    result = _api("POST", "/api/agent/pipeline")
    return result


def test_e2e_core_loop_ui(server, demo_state):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 1) 经营总览加载
        page.goto(BASE + "/#/overview")
        page.wait_for_timeout(2500)
        assert "零售经营决策" in page.title()
        body = page.locator("#main").inner_text()
        assert "销售额" in body and "待处理异常" in body

        # 2) 异常中心：自动发现的异常可见
        page.goto(BASE + "/#/anomalies")
        page.wait_for_timeout(1500)
        rows = page.locator("table tr.clickable")
        assert rows.count() >= 3, "自动发现的异常应可见"
        # 3) 进入详情：根因分析 + 证据
        rows.first.click()
        page.wait_for_timeout(1500)
        detail = page.locator("#main").inner_text()
        assert "根因" in detail or "原因分析" in detail
        assert "证据" in detail
        assert "建议" in detail or "补货" in detail

        # 4) 建议（补货/促销）页面：R4 只出这两类
        page.goto(BASE + "/#/decisions")
        page.wait_for_timeout(1500)
        cards = page.locator("#main").inner_text()
        assert "需审批" in cards or "自动执行" in cards
        assert "补货下单" in cards or "促销活动" in cards
        # 不应出现冻结的动作类型
        assert "会员触达" not in cards and "客服跟进" not in cards and "库存调拨" not in cards

        # 5) 审批中心：以风控身份通过一条审批（R5 Human-in-the-loop）
        page.goto(BASE + "/#/approvals")
        page.wait_for_timeout(1500)
        approve_btns = page.locator("button:has-text('通过')")
        if approve_btns.count() > 0:
            approve_btns.first.click()
            page.wait_for_timeout(2000)
            _api("POST", "/api/agent/execute", token="tok_agent")
            page.reload()
            page.wait_for_timeout(1500)

        # 6) 执行记录
        page.goto(BASE + "/#/executions")
        page.wait_for_timeout(1500)
        execs = page.locator("#main").inner_text()
        assert "success" in execs or "executed" in execs or "replenish" in execs or "promo" in execs

        # 7) 审计日志：完整链路留痕
        page.goto(BASE + "/#/audit")
        page.wait_for_timeout(1500)
        audit_text = page.locator("#audit-card").inner_text()
        assert "perception.scan" in audit_text or "execution." in audit_text or "decision." in audit_text

        # 8) UI 无 JS 错误
        assert not errors, f"页面 JS 错误: {errors}"
        browser.close()


def test_e2e_decisions_only_replenish_promo(server, demo_state):
    """R4 最小集：生成的建议只包含补货与促销。"""
    decisions = _api("GET", "/api/agent/decisions?limit=100")
    types = {d["action_type"] for d in decisions["items"]}
    assert types and types <= {"replenish", "promo"}, f"超范围动作: {types}"


def test_e2e_acceptance_metrics(server):
    """治理合规复查：高风险执行 100% 持审批单。"""
    m = _api("GET", "/api/kpi/overview")["agent_metrics"]
    assert m["high_risk_approval_compliance_pct"] in (100, None)
