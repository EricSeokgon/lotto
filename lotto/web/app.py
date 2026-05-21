"""FastAPI 앱 — 로또 통계 웹 대시보드."""

from __future__ import annotations

import asyncio
import datetime
import threading
from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lotto.web.routes import api, pages

# 경로 상수
_WEB_DIR = Path(__file__).parent
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"
_DRAWS_PATH = Path("data/draws.csv")
_STATS_PATH = Path("data/stats.json")


def _next_monday_midnight() -> float:
    """다음 월요일 자정까지 남은 초를 반환합니다."""
    now = datetime.datetime.now()
    days_until_monday = (7 - now.weekday()) % 7 or 7
    next_monday = (now + datetime.timedelta(days=days_until_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_monday - now).total_seconds()


async def _weekly_collect_task() -> None:
    """매주 월요일 자정에 증분 수집 + 통계 분석을 실행합니다."""
    while True:
        wait_sec = _next_monday_midnight()
        await asyncio.sleep(wait_sec)
        threading.Thread(
            target=api._collect_worker,
            args=(False, 1, api._estimate_latest_drw_no()),
            daemon=True,
        ).start()
        # 다음 루프까지 1시간 대기 (월요일 중복 실행 방지)
        await asyncio.sleep(3600)


@asynccontextmanager
async def _lifespan(app_: FastAPI) -> AsyncIterator[None]:
    # SPEC-LOTTO-012 REQ-HLT-004: 서버 시작 시각을 lifespan 진입 시점으로 재설정
    api._startup_time = datetime.datetime.now()
    task = asyncio.create_task(_weekly_collect_task())
    yield
    task.cancel()


# FastAPI 앱 초기화
app = FastAPI(
    title="로또 번호 추천 시스템",
    description="통계 기반 로또 번호 수집·분석·추천·시뮬레이션 API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=_lifespan,
)

# 정적 파일 마운트 (디렉토리 존재 시)
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Jinja2 템플릿 설정
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# 라우터 등록
app.include_router(pages.router)
app.include_router(api.router)


@app.get("/health")
async def health() -> dict:
    """서버 및 데이터 파일 상태를 반환합니다."""
    csv_exists = _DRAWS_PATH.exists()
    stats_exists = _STATS_PATH.exists()
    status = "ok" if (csv_exists and stats_exists) else "degraded"
    return {
        "status": status,
        "data_csv_exists": csv_exists,
        "stats_json_exists": stats_exists,
    }
