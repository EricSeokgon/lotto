"""페이지 라우터 — HTML 탭 5개.

# @MX:ANCHOR: [AUTO] 웹 대시보드 HTML 페이지 라우트 진입점
# @MX:REASON: app.py, 5개 HTML 템플릿에서 참조되는 핵심 라우터
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from starlette.responses import TemplateResponse

from lotto.web.data import (
    compute_frequency_percentiles,
    get_data_status,
    get_draws,
    get_recommendations,
    get_simulation,
    get_stats,
    interpolate_color,
)

router = APIRouter()

# 템플릿 경로 설정
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _render(request: Request, template: str, ctx: dict) -> TemplateResponse:
    """Starlette v0.40+ 호환 TemplateResponse 헬퍼."""
    return templates.TemplateResponse(request, template, ctx)


@router.get("/")
async def index(request: Request) -> TemplateResponse:
    """대시보드 인덱스 페이지."""
    data_status = get_data_status()
    return _render(request, "index.html", {
        "active_tab": "dashboard",
        "data_status": data_status,
    })


@router.get("/collect")
async def collect_page(request: Request) -> TemplateResponse:
    """수집 현황 페이지."""
    data_status = get_data_status()
    draws = get_draws()
    return _render(request, "collect.html", {
        "active_tab": "collect",
        "data_status": data_status,
        "draws": draws,
    })


@router.get("/analyze")
async def analyze_page(request: Request) -> TemplateResponse:
    """빈도 분석 페이지 — 시그니처 배지 색상 포함."""
    data_status = get_data_status()
    stats = get_stats()

    badge_colors: dict[int, str] = {}
    badge_percentiles: dict[int, float] = {}
    freq_chart_data: dict = {"labels": [], "values": []}

    if stats is not None:
        freq_abs = stats.frequency.absolute
        # 문자열 키를 정수 키로 변환
        freq_dict = {int(k): v for k, v in freq_abs.items()} if freq_abs else {}

        if freq_dict:
            percentiles = compute_frequency_percentiles(freq_dict)
            badge_percentiles = percentiles
            badge_colors = {num: interpolate_color(pct) for num, pct in percentiles.items()}

            # 상위 20개 차트 데이터 (Python에서 미리 계산)
            sorted_freq = sorted(freq_dict.items(), key=lambda x: x[1], reverse=True)[:20]
            freq_chart_data = {
                "labels": [str(k) for k, _ in sorted_freq],
                "values": [v for _, v in sorted_freq],
            }

    return _render(request, "analyze.html", {
        "active_tab": "analyze",
        "data_status": data_status,
        "stats": stats,
        "badge_colors": badge_colors,
        "badge_percentiles": badge_percentiles,
        "numbers": list(range(1, 46)),
        "freq_chart_data": freq_chart_data,
    })


@router.get("/recommend")
async def recommend_page(
    request: Request,
    count: int = 5,
) -> TemplateResponse:
    """추천 번호 페이지.

    Args:
        count: 추천 세트 수 (1~20)
    """
    count = max(1, min(20, count))
    data_status = get_data_status()
    recommendations = get_recommendations(count=count)

    return _render(request, "recommend.html", {
        "active_tab": "recommend",
        "data_status": data_status,
        "recommendations": recommendations,
        "count": count,
    })


@router.get("/simulate")
async def simulate_page(
    request: Request,
    rounds: int = 1000,
) -> TemplateResponse:
    """시뮬레이션 페이지.

    Args:
        rounds: 시뮬레이션 회차 수 (1~100000)
    """
    rounds = max(1, min(100000, rounds))
    data_status = get_data_status()
    result = get_simulation(rounds=rounds)

    # 도넛 차트 데이터 구성
    prize_chart_data: dict = {"labels": [], "values": []}
    if result is not None:
        prize_chart_data = {
            "labels": list(result.prize_counts.keys()),
            "values": list(result.prize_counts.values()),
        }

    return _render(request, "simulate.html", {
        "active_tab": "simulate",
        "data_status": data_status,
        "result": result,
        "rounds": rounds,
        "prize_chart_data": prize_chart_data,
    })
