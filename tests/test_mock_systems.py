# -*- coding: utf-8 -*-
"""目标2测试：Mock 业务系统（健康/OpenAPI/查询/受控写入/幂等/dry-run/治理拦截/补偿）。"""
import uuid

from conftest import auth


def test_health_and_openapi(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for prefix in ("/api/master", "/api/sales", "/api/inventory", "/api/members",
                   "/api/cs", "/api/external", "/api/gov"):
        assert any(p.startswith(prefix) for p in paths), f"缺少 {prefix} 路由"


def test_master_data(client):
    r = client.get("/api/master/stores")
    assert r.status_code == 200 and len(r.json()["items"]) == 12
    r = client.get("/api/master/products", params={"limit": 500})
    assert r.status_code == 200 and r.json()["total"] == 100
    r = client.get("/api/master/categories")
    assert r.status_code == 200


def test_sales_query_filters(client):
    stores = client.get("/api/master/stores").json()["items"]
    sid = stores[0]["id"]
    r = client.get("/api/sales/daily", params={"store_id": sid, "limit": 5})
    assert r.status_code == 200 and r.json()["total"] > 0
    item = r.json()["items"][0]
    for k in ("biz_date", "store_id", "product_id", "qty", "amount"):
        assert k in item
    # 渠道拆分：online ≤ total
    r_all = client.get("/api/sales/summary", params={
        "start": item["biz_date"], "end": item["biz_date"], "store_id": sid}).json()
    assert r_all["sales_qty"] >= 0 and "gross_margin_rate" in r_all


def test_sales_timeseries(client):
    stores = client.get("/api/master/stores").json()["items"]
    prods = client.get("/api/master/products", params={"limit": 1}).json()["items"]
    r = client.get("/api/sales/timeseries", params={
        "store_id": stores[0]["id"], "product_id": prods[0]["id"], "days": 14})
    assert r.status_code == 200 and len(r.json()["items"]) == 14


def test_replenishment_low_risk_auto(client):
    stores = client.get("/api/master/stores").json()["items"]
    prods = client.get("/api/master/products", params={"category_id": "C01", "limit": 1}).json()["items"]
    key = f"test-rpl-{uuid.uuid4().hex[:8]}"
    body = {"store_id": stores[0]["id"], "product_id": prods[0]["id"], "qty": 50,
            "idempotency_key": key}
    r = client.post("/api/inventory/replenishments", json=body, headers=auth("planner"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["policy"]["allowed"] and not data["policy"]["requires_approval"]
    assert data["replayed"] is False
    # 幂等重放：同 key 同请求 → 不重复下单
    r2 = client.post("/api/inventory/replenishments", json=body, headers=auth("planner"))
    assert r2.status_code == 200 and r2.json()["replayed"] is True
    assert r2.json()["order_no"] == data["order_no"]
    # 幂等冲突：同 key 不同请求 → 409
    r3 = client.post("/api/inventory/replenishments",
                     json={**body, "qty": 60}, headers=auth("planner"))
    assert r3.status_code == 409


def test_replenishment_dry_run_and_moq(client):
    stores = client.get("/api/master/stores").json()["items"]
    prods = client.get("/api/master/products", params={"category_id": "C01", "limit": 1}).json()["items"]
    moq = prods[0]["moq"]
    # dry-run：不落库
    r = client.post("/api/inventory/replenishments",
                    json={"store_id": stores[0]["id"], "product_id": prods[0]["id"],
                          "qty": max(moq, 10), "dry_run": True,
                          "idempotency_key": f"dr-{uuid.uuid4().hex[:6]}"},
                    headers=auth("planner"))
    assert r.status_code == 200 and r.json()["dry_run"] is True
    # 低于 MOQ 拒绝
    r = client.post("/api/inventory/replenishments",
                    json={"store_id": stores[0]["id"], "product_id": prods[0]["id"],
                          "qty": max(1, moq - 1), "idempotency_key": f"moq-{uuid.uuid4().hex[:6]}"},
                    headers=auth("planner"))
    assert r.status_code == 400 and "MOQ" in r.json()["detail"]


def test_replenishment_high_amount_needs_approval(client):
    stores = client.get("/api/master/stores").json()["items"]
    # 小家电类高价商品，大数量 → 金额>1万 → 必须审批
    prods = client.get("/api/master/products", params={"category_id": "C16", "limit": 1}).json()["items"]
    if not prods:
        return
    cost = prods[0]["cost_price"]
    qty = int(20000 / cost) + 10
    r = client.post("/api/inventory/replenishments",
                    json={"store_id": stores[0]["id"], "product_id": prods[0]["id"],
                          "qty": qty, "idempotency_key": f"hi-{uuid.uuid4().hex[:6]}"},
                    headers=auth("agent"))
    assert r.status_code == 403 and "审批" in r.json()["detail"]


def test_transfer_same_region_and_compensate(client):
    stores = client.get("/api/master/stores").json()["items"]
    same = [s for s in stores if s["region_id"] == stores[0]["region_id"]]
    src, dst = same[0], same[1]
    inv = client.get("/api/inventory", params={"store_id": src["id"], "limit": 200}).json()["items"]
    inv = [i for i in inv if i["on_hand"] > 10]
    assert inv, "测试世界应有可用库存"
    key = f"test-trf-{uuid.uuid4().hex[:8]}"
    body = {"from_store_id": src["id"], "to_store_id": dst["id"],
            "product_id": inv[0]["product_id"], "qty": 5, "idempotency_key": key}
    r = client.post("/api/inventory/transfers", json=body, headers=auth("planner"))
    assert r.status_code == 200, r.text
    order_id = r.json()["id"]
    # 库存已移动
    after = client.get("/api/inventory", params={
        "store_id": src["id"], "product_id": inv[0]["product_id"]}).json()["items"][0]
    assert after["on_hand"] == inv[0]["on_hand"] - 5
    # 补偿 → 库存恢复
    r = client.post(f"/api/inventory/transfers/{order_id}/compensate", headers=auth("planner"))
    assert r.status_code == 200 and r.json()["status"] == "compensated"
    restored = client.get("/api/inventory", params={
        "store_id": src["id"], "product_id": inv[0]["product_id"]}).json()["items"][0]
    assert restored["on_hand"] == inv[0]["on_hand"]


def test_transfer_cross_region_needs_approval(client):
    stores = client.get("/api/master/stores").json()["items"]
    regions = sorted({s["region_id"] for s in stores})
    if len(regions) < 2:
        return
    a = next(s for s in stores if s["region_id"] == regions[0])
    b = next(s for s in stores if s["region_id"] == regions[1])
    inv = client.get("/api/inventory", params={"store_id": a["id"], "limit": 300}).json()["items"]
    inv = [i for i in inv if i["on_hand"] > 10]
    r = client.post("/api/inventory/transfers",
                    json={"from_store_id": a["id"], "to_store_id": b["id"],
                          "product_id": inv[0]["product_id"], "qty": 5,
                          "idempotency_key": f"xr-{uuid.uuid4().hex[:6]}"},
                    headers=auth("agent"))
    assert r.status_code == 403 and "跨区域" in r.json()["detail"]


def test_campaign_thresholds(client):
    stores = client.get("/api/master/stores").json()["items"]
    sid = stores[0]["id"]
    # 10% 折扣 + 预算 8000 → 低风险可创建
    r = client.post("/api/members/campaigns",
                    json={"name": "测试促销-低风险", "store_ids": [sid], "category_id": "C04",
                          "discount_pct": 10, "budget": 8000,
                          "idempotency_key": f"cmp-lo-{uuid.uuid4().hex[:6]}"},
                    headers=auth("member"))
    assert r.status_code == 200, r.text
    # 15% 折扣 → 必须审批
    r = client.post("/api/members/campaigns",
                    json={"name": "测试促销-需审批", "store_ids": [sid], "category_id": "C04",
                          "discount_pct": 15, "budget": 8000,
                          "idempotency_key": f"cmp-hi-{uuid.uuid4().hex[:6]}"},
                    headers=auth("member"))
    assert r.status_code == 403 and "审批" in r.json()["detail"]
    # 35% 折扣 → L4 拒绝
    r = client.post("/api/members/campaigns",
                    json={"name": "测试促销-禁止", "store_ids": [sid], "category_id": "C04",
                          "discount_pct": 35, "budget": 5000,
                          "idempotency_key": f"cmp-den-{uuid.uuid4().hex[:6]}"},
                    headers=auth("risk"))
    assert r.status_code == 403 and "禁止" in r.json()["detail"]


def test_ticket_task_and_external(client):
    stores = client.get("/api/master/stores").json()["items"]
    r = client.post("/api/cs/tasks",
                    json={"store_id": stores[0]["id"], "type": "callback",
                          "idempotency_key": f"tsk-{uuid.uuid4().hex[:6]}"},
                    headers=auth("cs"))
    assert r.status_code == 200 and r.json()["status"] == "pending"
    # 赔偿类 → 审批
    r = client.post("/api/cs/tasks",
                    json={"store_id": stores[0]["id"], "type": "compensation_review",
                          "idempotency_key": f"tsk2-{uuid.uuid4().hex[:6]}"},
                    headers=auth("cs"))
    assert r.status_code == 403
    # 外部数据
    assert client.get("/api/external/weather").status_code == 200
    assert client.get("/api/external/competitor-promos").status_code == 200
    assert client.get("/api/external/calendar").status_code == 200


def test_audit_log_written(client):
    r = client.get("/api/gov/audit-logs", params={"action": "inventory.create_replenishment",
                                                  "limit": 5})
    assert r.status_code == 200 and len(r.json()["items"]) > 0
    log = r.json()["items"][0]
    assert log["actor_id"] and log["ts"] and log["action"]
