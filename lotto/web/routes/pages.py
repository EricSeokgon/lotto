"""페이지 라우터 — HTML 탭 5개.

# @MX:ANCHOR: [AUTO] 웹 대시보드 HTML 페이지 라우트 진입점
# @MX:REASON: app.py, 5개 HTML 템플릿에서 참조되는 핵심 라우터
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:  # pragma: no cover
    from starlette.templating import _TemplateResponse as TemplateResponse

    from lotto.models import DrawResult

from lotto.web.data import (
    compute_frequency_percentiles,
    compute_ticket_results,
    get_data_status,
    get_draws,
    get_last_sync_date,
    get_recommendations,
    get_simulation,
    get_stats,
    get_strategy_comparison,
    interpolate_color,
)

router = APIRouter()

# 템플릿 경로 설정
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _ball_color(n: int) -> str:
    """로또 볼 번호에 따른 배경색 반환 (공식 색상 기준)."""
    if n <= 10:  # noqa: PLR2004
        return "#FBC400"
    if n <= 20:  # noqa: PLR2004
        return "#69C8F2"
    if n <= 30:  # noqa: PLR2004
        return "#FF7272"
    if n <= 40:  # noqa: PLR2004
        return "#AAAAAA"
    return "#B0D840"


def _prize_class(prize: str) -> str:
    """등수 배지 Tailwind CSS 클래스 반환."""
    mapping = {
        "1등": "bg-yellow-400 text-yellow-900",
        "2등": "bg-yellow-200 text-yellow-800",
        "3등": "bg-orange-200 text-orange-800",
        "4등": "bg-green-200 text-green-800",
        "5등": "bg-blue-200 text-blue-800",
        "낙첨": "bg-gray-200 text-gray-600",
        "미추첨": "bg-gray-100 text-gray-400",
    }
    return mapping.get(prize, "bg-gray-100 text-gray-400")


# Jinja2 환경에 커스텀 필터 등록
templates.env.filters["ball_color"] = _ball_color
templates.env.filters["prize_class"] = _prize_class


def _render(request: Request, template: str, ctx: dict[str, Any]) -> TemplateResponse:
    """Starlette v0.40+ 호환 TemplateResponse 헬퍼."""
    return templates.TemplateResponse(request, template, ctx)


@router.get("/")
async def index(request: Request) -> TemplateResponse:
    """대시보드 인덱스 페이지.

    SPEC-LOTTO-009 REQ-LAST-001: 헤더에 표시할 last_date 컨텍스트를 전달한다.
    """
    data_status = get_data_status()
    last_date = get_last_sync_date()
    return _render(request, "index.html", {
        "active_tab": "dashboard",
        "data_status": data_status,
        "last_date": last_date,
    })


@router.get("/collect")
async def collect_page(request: Request) -> TemplateResponse:
    """수집 현황 페이지."""
    data_status = get_data_status()
    draws = get_draws()
    # 서버사이드 초기 렌더링: 최신 회차부터 표시 (브라우저 캐시 무관)
    initial_draws = list(reversed(draws))[:20]
    return _render(request, "collect.html", {
        "active_tab": "collect",
        "data_status": data_status,
        "draws": draws,
        "initial_draws": initial_draws,
    })


@router.get("/analyze")
async def analyze_page(request: Request) -> TemplateResponse:
    """빈도 분석 페이지 — 시그니처 배지 색상 포함."""
    data_status = get_data_status()
    stats = get_stats()

    badge_colors: dict[int, str] = {}
    badge_percentiles: dict[int, float] = {}
    freq_chart_data: dict[str, Any] = {"labels": [], "values": []}

    gap_rounds: dict[int, int] = {}

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
                "numbers": [k for k, _ in sorted_freq],
                "labels": [f"{k}번" for k, _ in sorted_freq],
                "values": [v for _, v in sorted_freq],
            }

        # 갭 분석: consecutive_pattern.current_streak 음수값 = 미출현 회차 수
        if stats.consecutive_pattern and stats.consecutive_pattern.current_streak:
            streaks = stats.consecutive_pattern.current_streak
            for num in range(1, 46):
                try:
                    streak = int(streaks.get(num, 0))
                    gap_rounds[num] = max(0, -streak)
                except (TypeError, ValueError):
                    gap_rounds[num] = 0

    return _render(request, "analyze.html", {
        "active_tab": "analyze",
        "data_status": data_status,
        "stats": stats,
        "badge_colors": badge_colors,
        "badge_percentiles": badge_percentiles,
        "numbers": list(range(1, 46)),
        "freq_chart_data": freq_chart_data,
        "gap_rounds": gap_rounds,
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


_PRIZE_VALUES: dict[str, int] = {
    "1등": 2_000_000_000,
    "2등": 60_000_000,
    "3등": 1_500_000,
    "4등": 50_000,
    "5등": 5_000,
    "낙첨": 0,
}


@router.get("/simulate")
async def simulate_page(
    request: Request,
    rounds: int = 1000,
    budget: int = 1000,
) -> TemplateResponse:
    """시뮬레이션 페이지.

    Args:
        rounds: 시뮬레이션 회차 수 (1~100000)
        budget: 회차당 구매 금액 (원)
    """
    rounds = max(1, min(100000, rounds))
    budget = max(1000, min(100000, budget))
    data_status = get_data_status()
    result = get_simulation(rounds=rounds)
    strategy_comparison = get_strategy_comparison(min(rounds, 200)) if result is not None else None

    prize_chart_data: dict[str, Any] = {"labels": [], "values": []}
    budget_info: dict[str, Any] = {"total_cost": 0, "total_return": 0, "roi": 0.0}
    per_round_data: dict[str, Any] = {"labels": [], "values": []}

    if result is not None:
        prize_chart_data = {
            "labels": list(result.prize_counts.keys()),
            "values": list(result.prize_counts.values()),
        }

        total_cost = result.total_rounds * budget
        total_return = sum(
            result.prize_counts.get(prize, 0) * _PRIZE_VALUES.get(prize, 0)
            for prize in _PRIZE_VALUES
        )
        roi = (total_return - total_cost) / total_cost * 100 if total_cost > 0 else 0.0
        budget_info = {
            "total_cost": total_cost,
            "total_return": total_return,
            "roi": roi,
        }

        # 누적 적중 추세 (최대 300포인트로 샘플링)
        per_round = result.per_round_hits
        if len(per_round) > 300:
            step = max(1, len(per_round) // 300)
            sampled = per_round[::step]
        else:
            sampled = per_round
        per_round_data = {
            "labels": list(range(1, len(sampled) + 1)),
            "values": sampled,
        }

    return _render(request, "simulate.html", {
        "active_tab": "simulate",
        "data_status": data_status,
        "result": result,
        "rounds": rounds,
        "budget": budget,
        "prize_chart_data": prize_chart_data,
        "budget_info": budget_info,
        "per_round_data": per_round_data,
        "strategy_comparison": strategy_comparison,
    })


@router.get("/purchases")
async def purchases_page(request: Request) -> TemplateResponse:
    """구매 이력 페이지.

    SPEC-LOTTO-015 REQ-PRIZE-003: ROI 요약 카드 4종을 컨텍스트로 전달.
    """
    import lotto.purchase as _pm

    data_status = get_data_status()
    records = _pm.load_purchases(_pm._PURCHASES_PATH)
    draws = get_draws()
    draws_by_drw_no: dict[int, DrawResult] = {d.drwNo: d for d in draws} if draws else {}
    purchases = _pm.build_responses(records, draws_by_drw_no)
    # SPEC-LOTTO-015 REQ-PRIZE-003: ROI 요약 계산 (pending 제외)
    roi_summary = _pm.calc_roi(purchases)
    return _render(request, "purchases.html", {
        "active_tab": "purchases",
        "data_status": data_status,
        "purchases": purchases,
        "roi_summary": roi_summary,
    })


@router.get("/history")
async def history_page(request: Request) -> TemplateResponse:
    """구매 히스토리 페이지.

    SPEC-LOTTO-015 REQ-PRIZE-003: ROI 요약 카드 4종을 컨텍스트로 전달.
    """
    import lotto.purchase as _pm

    data_status = get_data_status()
    results = compute_ticket_results()

    # 등수 통계 사전 계산 (Jinja2에서 dict.update 미지원 우회)
    prize_counts: dict[str, int] = {}
    for r in results:
        prize = r["prize"]
        prize_counts[prize] = prize_counts.get(prize, 0) + 1

    # SPEC-LOTTO-015 REQ-PRIZE-003: ROI 요약 계산
    # compute_ticket_results는 dict 리스트를 반환하며 prize_rank/prize_amount 키 포함
    roi_summary = _pm.calc_roi(results)

    return _render(request, "history.html", {
        "active_tab": "history",
        "data_status": data_status,
        "results": results,
        "prize_counts": prize_counts,
        "roi_summary": roi_summary,
    })
