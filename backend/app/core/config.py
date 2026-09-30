# -*- coding: utf-8 -*-
"""全局配置：路径、随机种子、LLM（OpenAI 兼容，可选）。"""
import os
import pathlib

_CORE = pathlib.Path(__file__).resolve().parent      # backend/app/core
APP_DIR = _CORE.parent                               # backend/app
BACKEND_DIR = APP_DIR.parent                         # backend
ROOT_DIR = BACKEND_DIR.parent                        # 仓库根目录

DATA_LOCAL = BACKEND_DIR / "data_local"
DB_PATH = pathlib.Path(os.getenv("RETAIL_DB", str(DATA_LOCAL / "retail.db")))
KB_DIR = pathlib.Path(os.getenv("RETAIL_KB_DIR", str(ROOT_DIR / "data" / "kb")))
WEB_DIR = pathlib.Path(os.getenv("RETAIL_WEB_DIR", str(ROOT_DIR / "web")))

SEED = int(os.getenv("RETAIL_SEED", "42"))

# LLM 可选：配置后用于"叙述生成"（不参与数值计算）；未配置则使用模板叙述器
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

API_PREFIX = "/api"
