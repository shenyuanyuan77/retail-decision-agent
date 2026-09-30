# -*- coding: utf-8 -*-
"""测试夹具：独立小规模 Mock 世界（固定种子，可重复）。"""
import os
import pathlib
import sys
import tempfile

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

_TMP = tempfile.mkdtemp(prefix="retail_test_")
os.environ["RETAIL_DB"] = os.path.join(_TMP, "test_retail.db")
os.environ.setdefault("RETAIL_SEED", "42")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.bootstrap import bootstrap  # noqa: E402
from app.core.db import session_scope  # noqa: E402
from app.main import app  # noqa: E402

# 演示 token（governance.auth.seed_users 预置）
TOKENS = {
    "region": "tok_region_01",
    "store": "tok_store_01",
    "planner": "tok_planner_01",
    "member": "tok_member_01",
    "cs": "tok_cs_01",
    "hq": "tok_hq_01",
    "risk": "tok_risk_01",
    "agent": "tok_agent",
}


@pytest.fixture(scope="session", autouse=True)
def world():
    """整个测试会话共用一个小规模世界（生成一次，秒级）。"""
    return bootstrap(days=45, stores=12, skus=100, seed=42)


@pytest.fixture(scope="session")
def client(world):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session():
    with session_scope() as s:
        yield s


def auth(role: str) -> dict:
    return {"X-Auth-Token": TOKENS[role]}
