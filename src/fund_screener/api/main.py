"""
FastAPI 应用入口

启动方式:
    uv run uvicorn fund_screener.api.main:app --reload --port 8000

或:
    uv run fund-screener api
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fund_screener.api.routes import funds, screening, chart, stats, health

logger = logging.getLogger("fund_screener.api")

app = FastAPI(
    title="Fund Screener API",
    description="全市场基金/ETF 趋势筛选器 REST API",
    version="1.0.0",
)

# CORS — 开发阶段允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(health.router, tags=["Health"])
app.include_router(funds.router, prefix="/api", tags=["Funds"])
app.include_router(screening.router, prefix="/api", tags=["Screening"])
app.include_router(chart.router, prefix="/api", tags=["Chart"])
app.include_router(stats.router, prefix="/api", tags=["Stats"])
