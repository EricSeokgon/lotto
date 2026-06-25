"""페이지 라우터 — HTML 탭 5개.

# @MX:ANCHOR: [AUTO] 웹 대시보드 HTML 페이지 라우트 진입점
# @MX:REASON: app.py, 5개 HTML 템플릿에서 참조되는 핵심 라우터
"""

from __future__ import annotations

from pathlib import Path
from typing import (  # noqa: UP035 — FastAPI는 Python 3.9에서 List 런타임 평가 필요
    TYPE_CHECKING,
    Any,
    List,
    Optional,  # noqa: UP045 — FastAPI는 Python 3.9에서 런타임 평가를 위해 Optional 필요
)

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi import Path as FastAPIPath  # noqa: N814 — pathlib.Path와 충돌 방지 별칭
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:  # pragma: no cover
    from starlette.templating import _TemplateResponse as TemplateResponse

    from lotto.models import DrawResult

from lotto.web import data as wd  # SPEC-LOTTO-054: 모듈 레벨 patch 호환용 별칭
from lotto.web.data import (
    compute_frequency_percentiles,
    compute_ticket_results,
    get_data_status,
    get_draws,
    get_last_sync_date,
    get_simulation,
    get_stats,
    get_strategy_comparison,
    interpolate_color,
    list_simulation_results,
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
    SPEC-LOTTO-023 REQ-SCHED-004: 다음 자동 수집 예정 시각을 컨텍스트로 노출한다.
    SPEC-LOTTO-025 REQ-NOTIF-005: 알림 설정 상태 카드를 컨텍스트로 노출한다.
    """
    from lotto.web import notifier as _notifier
    from lotto.web import scheduler as _sched

    data_status = get_data_status()
    last_date = get_last_sync_date()
    sched_status = _sched.get_status()
    notify_status = _notifier.get_settings_status()
    return _render(request, "index.html", {
        "active_tab": "dashboard",
        "data_status": data_status,
        "last_date": last_date,
        # REQ-SCHED-004: 스케줄러 비활성 시 next_run 은 None → 템플릿에서 숨김
        "scheduler_enabled": sched_status["enabled"],
        "scheduler_next_run": sched_status["next_run"],
        # REQ-NOTIF-005: 알림 설정 상태 (마스킹 처리됨 — URL/이메일 미노출)
        "notify_status": notify_status,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-029 REQ-DETAIL-002 — 회차별 상세 보기 페이지
# @MX:SPEC: SPEC-LOTTO-029 REQ-DETAIL-002
@router.get("/draw/{drw_no}")
async def draw_detail_page(request: Request, drw_no: int) -> TemplateResponse:
    """회차 상세 페이지 — 번호 시각화, 당첨금, 이전/다음 링크, 즐겨찾기 대조 (REQ-DETAIL-002).

    - 번호 + 보너스 색상 볼 시각화
    - 1등 당첨금/당첨자 수 표시 (없으면 '정보 없음')
    - 이전/다음 회차 링크 (존재할 때만 활성)
    - 즐겨찾기 번호 대조 (favorites가 있을 때만, 일치 번호 하이라이트)
    - 없는 회차 또는 drw_no <= 0 → 404 HTML
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    # drw_no <= 0 은 미존재와 동일하게 404 처리
    if drw_no <= 0:
        raise HTTPException(status_code=404, detail=f"{drw_no}회차를 찾을 수 없습니다.")

    draws = wd.get_draws() or []
    draw = next((d for d in draws if d.drwNo == drw_no), None)
    if draw is None:
        raise HTTPException(status_code=404, detail=f"{drw_no}회차를 찾을 수 없습니다.")

    # 이전/다음 회차 존재 여부 — 활성 링크 판정용
    existing_nos = {d.drwNo for d in draws}
    has_prev = (drw_no - 1) in existing_nos
    has_next = (drw_no + 1) in existing_nos

    # 즐겨찾기 대조 — 즐겨찾기에 포함된 모든 번호 집합과 당첨 번호의 교집합 하이라이트
    favorites = wd.get_favorites()
    favorite_numbers: set[int] = set()
    for fav in favorites:
        nums = fav.get("numbers", [])
        if isinstance(nums, list):
            favorite_numbers.update(int(n) for n in nums if isinstance(n, int))
    draw_numbers = draw.numbers()
    matched_favorites = sorted(favorite_numbers & set(draw_numbers))

    return _render(request, "draw_detail.html", {
        "active_tab": "collect",
        "draw": draw,
        "numbers": draw_numbers,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_no": drw_no - 1,
        "next_no": drw_no + 1,
        "favorites": favorites,
        "matched_favorites": matched_favorites,
    })


@router.get("/collect")
async def collect_page(request: Request) -> TemplateResponse:
    """수집 현황 페이지.

    SPEC-LOTTO-031: 상단에 수집 현황 요약 카드 + 누락 회차 목록을 전달한다.
    """
    from lotto.web.data import collect_summary

    data_status = get_data_status()
    # 기존 테스트가 pages.get_draws 를 패치하므로 모듈 임포트 심볼을 그대로 사용
    draws = get_draws() or []
    # 서버사이드 초기 렌더링: 최신 회차부터 표시 (브라우저 캐시 무관)
    initial_draws = list(reversed(draws))[:20]
    # SPEC-LOTTO-031: 수집 요약 (누락 회차 감지 포함)
    summary = collect_summary(draws)
    return _render(request, "collect.html", {
        "active_tab": "collect",
        "data_status": data_status,
        "draws": draws,
        "initial_draws": initial_draws,
        "summary": summary,
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
    # SPEC-LOTTO-051: get_recommendations/get_cross_strategy_consensus를 patch하는
    # 테스트와 호환되도록 lotto.web.data 모듈 네임스페이스로 동적 호출한다.
    from lotto.web import data as wd

    recommendations = wd.get_recommendations(count=count)

    # SPEC-LOTTO-051 REQ-CONS-004/007/011: 추천이 있을 때만 합의 1회 스캔.
    # 모든 추천 세트의 번호 합집합을 target으로 11개 전략을 요청당 1회만 스캔한다.
    consensus: dict[int, int] = {}
    if recommendations:
        stats = wd.get_stats()
        if stats is not None:
            from lotto.recommender import LottoRecommender

            target_numbers = sorted(
                {n for rec in recommendations for n in rec.numbers}
            )
            consensus = wd.get_cross_strategy_consensus(
                LottoRecommender(stats), target_numbers
            )

    return _render(request, "recommend.html", {
        "active_tab": "recommend",
        "data_status": data_status,
        "recommendations": recommendations,
        "count": count,
        # SPEC-LOTTO-051 REQ-CONS-003/006: 번호별 합의 카운트(N/11)와 주의 임계값
        "consensus": consensus,
        "consensus_caution_threshold": 4,
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


# @MX:NOTE: [AUTO] SPEC-LOTTO-048 — 저장된 시뮬레이션 결과 목록/비교 페이지
# @MX:SPEC: SPEC-LOTTO-048
@router.get("/simulation-history")
async def simulation_history_page(request: Request) -> TemplateResponse:
    """저장된 시뮬레이션 결과 목록 + 비교 페이지 (SPEC-LOTTO-048).

    저장된 결과를 최신순 카드로 표시하고, 삭제(JS fetch DELETE)와
    2건 이상 선택 시 나란히 비교(클라이언트 측)를 지원한다. 저장된
    결과가 없으면 빈 상태 안내를 노출한다.
    """
    results = list_simulation_results()
    return _render(request, "sim_history.html", {
        "active_tab": "sim_history",
        "results": results,
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


# @MX:NOTE: [AUTO] SPEC-LOTTO-024 REQ-CHECK-002 — 번호 즉시 검증 페이지
# @MX:SPEC: SPEC-LOTTO-024 REQ-CHECK-002
@router.get("/check")
async def check_page(request: Request) -> TemplateResponse:
    """번호 즉시 검증 페이지 — 회차/번호 입력 후 등수 확인 (REQ-CHECK-002).

    최신 회차 번호를 기본값으로 채워준다 (인수 조건).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    data_status = get_data_status()
    draws = wd.get_draws()
    # 인수 조건: 최신 회차를 기본값으로 (draws가 없으면 1)
    latest_drw_no = max((d.drwNo for d in draws), default=1) if draws else 1
    return _render(request, "check.html", {
        "active_tab": "check",
        "data_status": data_status,
        "latest_drw_no": latest_drw_no,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-030 — 번호 통계 목록 페이지
# @MX:SPEC: SPEC-LOTTO-030
@router.get("/numbers")
async def numbers_page(request: Request) -> TemplateResponse:
    """번호 통계 목록 페이지 — 1~45 전체의 출현 횟수/출현율/미출현 간격 (SPEC-LOTTO-030).

    각 번호 행 클릭 시 /numbers/{number} 상세 페이지로 이동한다.
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    data_status = get_data_status()
    draws = wd.get_draws()
    # 번호별 요약 — 목록은 가벼운 핵심 지표만 사용 (number_stats 재사용)
    rows = [wd.number_stats(n, draws) for n in range(1, 46)]
    return _render(request, "numbers.html", {
        "active_tab": "numbers",
        "data_status": data_status,
        "rows": rows,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-042 — 번호 추이 트래커 페이지
# @MX:SPEC: SPEC-LOTTO-042 REQ-TREND-T-040
# 주의: /numbers/{number} 동적 라우트보다 먼저 등록해야 "trend"가 number로 캡처되지 않는다.
@router.get("/numbers/trend")
async def numbers_trend_page(
    request: Request,
    n: Optional[List[int]] = Query(default=None),  # noqa: UP045, UP006, B008 — Python 3.9 호환 / FastAPI 반복 Query
    recent_n: int = Query(default=100, ge=10, le=500),
) -> TemplateResponse:
    """번호 추이 트래커 페이지 — 1~3개 번호의 최근 N회 출현 타임라인/간격 (SPEC-LOTTO-042).

    - 파라미터 없음(n 없음): 입력 폼만 표시 (REQ-TREND-T-040)
    - 유효 파라미터(n 1~3개): 폼 + 추이 결과 표시
    - 잘못된 개수/범위/중복은 폼 + 오류 메시지 (number_trend는 호출하지 않음)
    - 데이터 부재 시에도 200 (빈 구조를 자연스럽게 렌더링)
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    trend: dict[str, Any] | None = None
    error_message: str | None = None
    selected = n or []

    if selected:
        if not (1 <= len(selected) <= 3):  # noqa: PLR2004
            error_message = "번호는 1~3개여야 합니다."
        elif any(not (1 <= num <= 45) for num in selected):  # noqa: PLR2004
            error_message = "번호는 1~45 범위여야 합니다."
        elif len(set(selected)) != len(selected):
            error_message = "번호에 중복이 있습니다."
        else:
            trend = wd.number_trend(selected, recent_n=recent_n, draws=wd.get_draws())

    return _render(request, "numbers_trend.html", {
        "active_tab": "numbers_trend",
        "selected": selected,
        "recent_n": recent_n,
        "trend": trend,
        "error_message": error_message,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-044 — 번호 궁합 추천기 페이지
# @MX:SPEC: SPEC-LOTTO-044 REQ-AFFINITY-020
# 주의: /numbers/{number} 동적 라우트보다 먼저 등록해야 "affinity"가 number로 캡처되지 않는다.
@router.get("/numbers/affinity")
async def numbers_affinity_page(
    request: Request,
    target: Optional[int] = Query(default=None, ge=1, le=45),  # noqa: UP045
) -> TemplateResponse:
    """번호 궁합 추천기 페이지 — 대상 번호의 동반 파트너/추천 조합 (SPEC-LOTTO-044).

    - 파라미터 없음(target 없음): 입력 폼만 표시 (REQ-AFFINITY-020)
    - 유효 target(1~45): 폼 + 궁합 결과 표시 (REQ-AFFINITY-021)
    - 데이터 부재 시에도 200 (빈 구조를 자연스럽게 렌더링)
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    affinity: dict[str, Any] | None = None
    if target is not None:
        affinity = wd.number_affinity(target, wd.get_draws())

    return _render(request, "numbers_affinity.html", {
        "active_tab": "numbers_affinity",
        "target": target,
        "affinity": affinity,
        "error_message": None,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-047 — 번호별 당첨 주기 분석 페이지
# @MX:SPEC: SPEC-LOTTO-047
# 주의: /numbers/{number} 동적 라우트보다 먼저 등록해야 "cycle"이 number로 캡처되지 않는다.
@router.get("/numbers/cycle")
async def numbers_cycle_page(request: Request) -> TemplateResponse:
    """번호별 당첨 주기 분석 페이지 — 1~45 평균 주기/현재 간격/상태 + most_overdue (SPEC-LOTTO-047).

    - 요약 카운트 카드 4종 (overdue/frequent/normal/never)
    - 가장 지연된 번호 하이라이트 섹션 (상위 5)
    - 번호별 주기 상세 테이블 (색상 코딩 상태 배지)
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 메시지)
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    analysis = wd.cycle_analysis(wd.get_draws())
    return _render(request, "cycle_analysis.html", {
        "active_tab": "cycle",
        "analysis": analysis,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-053 — 번호 동시 출현 분석 페이지
# @MX:SPEC: SPEC-LOTTO-053 REQ-CO-007, REQ-CO-008, REQ-CO-012
# 주의: /numbers/{number} 동적 라우트보다 먼저 등록해야 "cooccurrence"가 number로 캡처되지 않는다.
@router.get("/numbers/cooccurrence")
async def numbers_cooccurrence_page(
    request: Request,
    number: Optional[int] = Query(default=None, ge=1, le=45),  # noqa: UP045
) -> TemplateResponse:
    """번호 동시 출현 분석 페이지 — 상위 동시 출현 쌍 또는 특정 번호의 파트너 (SPEC-LOTTO-053).

    - number 없음: 상위 20개 동시 출현 쌍 표 (REQ-CO-007).
    - number 지정(1~45): 해당 번호의 상위 10개 동반 파트너 표 (REQ-CO-008/012).
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    draws = wd.get_draws()
    partners: list[dict[str, Any]] | None = None
    pairs: list[dict[str, Any]] | None = None
    if number is not None:
        partners = wd.get_number_partners(draws, number, top_k=10)
    else:
        pairs = wd.get_top_cooccurrences(draws, n=20)

    return _render(request, "cooccurrence.html", {
        "active_tab": "cooccurrence",
        "number": number,
        "partners": partners,
        "pairs": pairs,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-030 — 번호 상세 통계 페이지
# @MX:SPEC: SPEC-LOTTO-030
@router.get("/numbers/{number}")
async def number_detail_page(
    request: Request,
    number: int = FastAPIPath(..., ge=1, le=45, description="조회할 번호 (1~45)"),
) -> TemplateResponse:
    """번호 상세 페이지 — stats 데이터, 동반 번호 top5, 위치별 빈도 바 차트 (SPEC-LOTTO-030).

    number는 1~45. 범위 초과 시 FastAPI Path 검증으로 422.
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    data_status = get_data_status()
    stats = wd.number_stats(number, wd.get_draws())
    # 위치 바 차트용 최댓값 (0 나눗셈 방지)
    by_position = stats["by_position"]
    position_max = max(by_position.values()) if by_position else 0
    return _render(request, "number_detail.html", {
        "active_tab": "numbers",
        "data_status": data_status,
        "stats": stats,
        "position_max": position_max,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-038 — 통계 대규모 대시보드 페이지
# @MX:SPEC: SPEC-LOTTO-038
@router.get("/stats")
async def stats_page(request: Request) -> TemplateResponse:
    """통계 대규모 대시보드 페이지 — 전체 이력 7개 통계 요소 시각화 (SPEC-LOTTO-038).

    - 요약 카드: 총 회차 수, 1등 당첨금 합계
    - 최고/최저 1등 당첨금 회차 카드
    - 번호 빈도 막대 차트 (1~45)
    - 홀짝 분포 / 범위 분포
    - 연도별 평균 당첨금 라인 차트
    - 데이터 부재 시 빈 상태 메시지
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    overview = wd.dashboard_overview(wd.get_draws())
    return _render(request, "stats.html", {
        "active_tab": "stats",
        "overview": overview,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-041 — 회차 구간 통계 페이지
# @MX:SPEC: SPEC-LOTTO-041 REQ-RANGE-007,008
@router.get("/stats/range")
async def stats_range_page(
    request: Request,
    start_drw: Optional[int] = Query(default=None, ge=1),  # noqa: UP045
    end_drw: Optional[int] = Query(default=None, ge=1),  # noqa: UP045
) -> TemplateResponse:
    """회차 구간 통계 페이지 — 폼 입력 후 지정 구간의 통계 시각화 (SPEC-LOTTO-041).

    - 파라미터 없음: 입력 폼만 표시 (REQ-RANGE-007)
    - 유효 구간(start_drw <= end_drw): 폼 + 통계 결과 표시 (REQ-RANGE-008)
    - start_drw > end_drw: 폼 + 오류 메시지 (range_stats는 호출하지 않음)
    - 데이터 부재 시에도 200 (빈 구조를 자연스럽게 렌더링)
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats: dict[str, Any] | None = None
    error_message: str | None = None

    # 두 파라미터가 모두 주어졌을 때만 통계 계산
    if start_drw is not None and end_drw is not None:
        if start_drw > end_drw:
            error_message = "시작 회차는 끝 회차보다 클 수 없습니다."
        else:
            stats = wd.range_stats(start_drw, end_drw, wd.get_draws())

    return _render(request, "stats_range.html", {
        "active_tab": "stats_range",
        "start_drw": start_drw,
        "end_drw": end_drw,
        "stats": stats,
        "error_message": error_message,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-054 — 롤링 윈도우 빈도 분석 페이지
# @MX:SPEC: SPEC-LOTTO-054 REQ-RW-008/009/014
@router.get("/stats/rolling")
async def stats_rolling_page(
    request: Request,
    w: Optional[int] = Query(default=None, ge=1),  # noqa: UP045
) -> TemplateResponse:
    """롤링 윈도우 빈도 분석 페이지 — 최근 N회차별 빈도/델타/추세 비교 (SPEC-LOTTO-054).

    - w 없음: 기본 윈도우(10/20/50/100)를 나란히 비교 (REQ-RW-008).
    - w=W 지정: 해당 단일 윈도우만 포커스 표시 (REQ-RW-009/014).
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    draws = wd.get_draws()
    # w가 주어지면 단일 윈도우, 아니면 기본 4개 윈도우 (REQ-RW-014)
    windows: tuple[int, ...] = (w,) if w is not None else (10, 20, 50, 100)
    results = wd.get_rolling_frequency(draws, windows=windows)

    return _render(request, "rolling.html", {
        "active_tab": "rolling",
        "single_window": w,
        "results": results,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-055 — 끝자리(1의 자리) 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-055 REQ-LD-010/011/013
@router.get("/stats/last-digit")
async def stats_last_digit_page(request: Request) -> TemplateResponse:
    """끝자리 분포 분석 페이지 — 끝자리 0~9별 출현 횟수/비율/편차 표 (SPEC-LOTTO-055).

    - 10개 끝자리 행을 표로 제시하고, 편차 부호(양/음)에 따라 강조 표시한다.
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    stats = wd.get_last_digit_stats(wd.get_draws())
    # 끝자리 오름차순 행 리스트 (템플릿 순회용)
    rows = [stats[d] for d in range(10)]
    total_draws = sum(row["count"] for row in rows)

    return _render(request, "last_digit.html", {
        "active_tab": "last_digit",
        "rows": rows,
        "total_draws": total_draws,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-056 — 번호 간격 패턴 분석 페이지
# @MX:SPEC: SPEC-LOTTO-056
@router.get("/stats/gap")
async def stats_gap_page(request: Request) -> TemplateResponse:
    """번호 간격 패턴 분석 페이지 — 인접 간격의 분류/위치별 평균/최빈 간격 (SPEC-LOTTO-056).

    - 소/중/대 분류 요약, 위치별 평균 간격 표, 최빈 간격 상위 10개 표를 제시한다.
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    stats = wd.get_gap_stats(wd.get_draws())

    return _render(request, "gap.html", {
        "active_tab": "gap",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-057 — AC값(산술 복잡도) 분석 페이지
# @MX:SPEC: SPEC-LOTTO-057
@router.get("/stats/ac")
async def stats_ac_page(request: Request) -> TemplateResponse:
    """AC값(산술 복잡도) 분석 페이지 — AC 0~10 분포/고저복잡도 비율 (SPEC-LOTTO-057).

    - AC 0~10 분포 표(고복잡도 7~10 강조, 저복잡도 0~3 강조)와 요약을 제시한다.
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    stats = wd.get_ac_stats(wd.get_draws())

    return _render(request, "ac.html", {
        "active_tab": "ac",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-058 — 소수/합성수 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-058
@router.get("/stats/prime")
async def stats_prime_page(request: Request) -> TemplateResponse:
    """소수/합성수 분포 분석 페이지 — 소수/합성수 개수(0~6) 분포 (SPEC-LOTTO-058).

    - 평균 소수/합성수 개수, 숫자 1 출현 회차 요약과 분포 표 2종을 제시한다.
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    stats = wd.get_prime_stats(wd.get_draws())

    return _render(request, "prime.html", {
        "active_tab": "prime",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-059 — 십의 자리 구간 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-059
@router.get("/stats/decade")
async def stats_decade_page(request: Request) -> TemplateResponse:
    """십의 자리 구간 분포 분석 페이지 — 5개 구간 평균/기대/편차 (SPEC-LOTTO-059).

    - 구간별 평균 출현 개수와 기대 평균, 편차, 최빈/최소 구간을 제시한다.
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    stats = wd.get_decade_stats(wd.get_draws())

    return _render(request, "decade.html", {
        "active_tab": "decade",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-060 — 홀짝 비율 분석 페이지
# @MX:SPEC: SPEC-LOTTO-060
@router.get("/stats/odd-even")
async def stats_odd_even_page(request: Request) -> TemplateResponse:
    """홀짝 비율 분석 페이지 — 홀수 개수(0~6)별 분포/비율 + 균형 회차 (SPEC-LOTTO-060).

    - 요약 카드: 분석 회차 / 평균 홀수·짝수 / 균형(3:3) 회차 수·비율
    - 홀수 개수별 분포 테이블 (홀수 개수 / 회차 수 / 비율 / 짝수 개수 / 회차 수 / 비율)
    - 균형(홀 3) 행 하이라이트
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    stats = wd.get_odd_even_stats(wd.get_draws())

    return _render(request, "odd_even.html", {
        "active_tab": "odd_even",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-061 — 고저 비율 분석 페이지
# @MX:SPEC: SPEC-LOTTO-061
@router.get("/stats/high-low")
async def stats_high_low_page(request: Request) -> TemplateResponse:
    """고저 비율 분석 페이지 — 저 개수(0~6)별 분포/비율 + 균형 회차 (SPEC-LOTTO-061).

    - 요약 카드: 분석 회차 / 평균 저·고 / 균형(3:3) 회차 수·비율
    - 저 개수별 분포 테이블 (저 개수 / 회차 수 / 비율 / 고 개수 / 회차 수 / 비율)
    - 균형(저 3) 행 하이라이트
    - 저(low): 1~22, 고(high): 23~45 (경계 22는 저, 23은 고)
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    stats = wd.get_high_low_stats(wd.get_draws())

    return _render(request, "high_low.html", {
        "active_tab": "high_low",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-062 — 연속 번호 패턴 분석 페이지
# @MX:SPEC: SPEC-LOTTO-062
@router.get("/stats/consecutive-pattern")
async def stats_consecutive_pattern_page(request: Request) -> TemplateResponse:
    """연속 번호 패턴 분석 페이지 — 연속 쌍 개수(0~5)별 분포/비율 (SPEC-LOTTO-062).

    - 요약 카드: 분석 회차 / 평균 연속 쌍 / 연속 없음 회차 수·비율 /
      트리플(3연속) 회차 수·비율 / 최대 연속 쌍
    - 연속 쌍 개수별 분포 테이블 (쌍 개수 / 회차 수 / 비율)
    - SPEC-043의 consecutive_pattern과 독립적인 별도 집계.
    - 데이터 부재 시에도 200 (빈 상태 안내 메시지).
    """
    stats = wd.get_consecutive_pattern_stats(wd.get_draws())

    return _render(request, "consecutive_pattern.html", {
        "active_tab": "consecutive_pattern",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-063 — 끝자리 합계 분석 페이지
# @MX:SPEC: SPEC-LOTTO-063
@router.get("/stats/last-digit-sum")
async def stats_last_digit_sum_page(request: Request) -> TemplateResponse:
    """끝자리 합계 분석 페이지 — 끝자리 합 분포/카테고리 분류 (SPEC-LOTTO-063).

    - 요약 카드: 분석 회차 / 평균 합 / 최소 합 / 최대 합
    - 카테고리 테이블: low(<15)/mid(15~29)/high(>=30) 회차 수·비율
    - 분포 테이블: 최빈 상위 20개 끝자리 합 (회차 수 내림차순, 동률 합계 오름차순)
    - SPEC-055의 끝자리 분포(/stats/last-digit)와 독립적인 별도 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_last_digit_sum_stats(wd.get_draws())
    return _render(request, "last_digit_sum.html", {
        "active_tab": "last_digit_sum",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-064 — 최솟값·최댓값 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-064
@router.get("/stats/min-max")
async def stats_min_max_page(request: Request) -> TemplateResponse:
    """최솟값·최댓값 분포 분석 페이지 (SPEC-LOTTO-064).

    - 요약 카드: 분석 회차 / 평균 최솟값 / 평균 최댓값 / 평균 범위
    - 카테고리 테이블: small(범위<30)/large(범위>=30) 회차 수·비율
    - 분포 테이블: 최빈 상위 15개 최솟값·최댓값 (회차 수 내림차순, 동률 값 오름차순)
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_min_max_stats(wd.get_draws())
    return _render(request, "min_max.html", {
        "active_tab": "min_max",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-065 — 번호 표준편차 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-065
@router.get("/stats/std")
async def stats_std_page(request: Request) -> TemplateResponse:
    """번호 표준편차 분포 분석 페이지 (SPEC-LOTTO-065).

    - 요약 카드: 분석 회차 / 평균·최소·최대 표준편차
    - 카테고리 테이블: low(<10)/mid([10,14))/high(>=14) 회차 수·비율
    - 분포 테이블: 6개 고정 bucket("0-4"~"20+") 회차 수·비율
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_std_stats(wd.get_draws())
    return _render(request, "std_analysis.html", {
        "active_tab": "std",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-066 — 소수합 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-066
@router.get("/stats/prime_sum")
async def stats_prime_sum_page(request: Request) -> TemplateResponse:
    """소수합 분포 분석 페이지 (SPEC-LOTTO-066).

    - 요약 카드: 분석 회차 / 평균·최소·최대 소수합
    - 카테고리 테이블: low(<40)/mid([40,80])/high(>80) 회차 수·비율
    - 분포 테이블: 6개 고정 bucket("0-30"~"150+") 회차 수·비율
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_prime_sum_stats(wd.get_draws())
    return _render(request, "prime_sum.html", {
        "active_tab": "prime_sum",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-067 — 번호 총합 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-067
@router.get("/stats/total_sum")
async def stats_total_sum_page(request: Request) -> TemplateResponse:
    """번호 총합 분포 분석 페이지 (SPEC-LOTTO-067).

    - 요약 카드: 분석 회차 / 평균·최소·최대 총합
    - 카테고리 테이블: low(<110)/mid([110,170])/high(>170) 회차 수·비율
    - 분포 테이블: 6개 고정 bucket("21-80"~"171-255") 회차 수·비율
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_total_sum_stats(wd.get_draws())
    return _render(request, "total_sum.html", {
        "active_tab": "total_sum",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-068 — 번호 구간별 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-068
@router.get("/stats/range_dist")
async def stats_range_dist_page(request: Request) -> TemplateResponse:
    """번호 구간별 분포 분석 페이지 (SPEC-LOTTO-068).

    - 요약 카드: 분석 회차 / 최다 커버 구간(most_covered_range)
    - 구간 분포 테이블: 5개 고정 구간("1-9"~"40-45")의
      total_count/draw_count/avg_per_draw/pct_of_numbers/draw_pct
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_range_dist_stats(wd.get_draws())
    return _render(request, "range_dist.html", {
        "active_tab": "range_dist",
        "stats": stats,
    })


@router.get("/stats/consecutive-pairs")
async def stats_consecutive_pairs_page(request: Request) -> TemplateResponse:
    """연속번호 패턴(연속 쌍) 분석 페이지 (SPEC-LOTTO-069).

    - 요약 카드: 분석 회차 / 평균 연속 쌍 / 최빈 버킷 / 연속 쌍 보유 비율
    - 버킷 분포 테이블: 4개 고정 버킷("0","1","2","3+")의 count/pct
    - SPEC-062(/stats/consecutive-pattern)와는 별개의 독립 페이지다.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_consecutive_pairs_stats(wd.get_draws())
    return _render(request, "consecutive_pairs.html", {
        "active_tab": "consecutive_pairs",
        "stats": stats,
    })


@router.get("/stats/ac-value")
async def stats_ac_value_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-121: AC값(산술 복잡도) 분석."""
    from lotto.web import data as wd

    data = wd.get_ac_analysis()
    return _render(request, "ac_value.html", {
        "active_tab": "ac_value",
        "data": data,
    })


@router.get("/stats/tail-digits")
async def tail_digits_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-122: 번호 끝자리(일의 자리) 분석."""
    from lotto.web import data as wd

    data = wd.get_tail_digit_analysis()
    return _render(request, "tail_digits.html", {
        "active_tab": "tail_digits",
        "data": data,
    })


@router.get("/stats/number-gaps")
async def number_gaps_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-123: 번호 간격(Gap) 분석."""
    from lotto.web import data as wd

    data = wd.get_number_gap_analysis()
    return _render(request, "number_gaps.html", {
        "active_tab": "number_gaps",
        "data": data,
    })


@router.get("/stats/number-range")
async def number_range_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-130: 번호 범위(최대-최소) 분포 분석."""
    data = wd.get_number_range_analysis()
    return _render(request, "number_range.html", {
        "active_tab": "number_range",
        "data": data,
    })


@router.get("/stats/median")
async def stats_median_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-129: 번호 중앙값 분포 분석."""
    data = wd.get_median_analysis()
    return _render(request, "median.html", {
        "active_tab": "median",
        "data": data,
    })


@router.get("/stats/last-digit-unique")
async def stats_last_digit_unique_page(request: Request) -> TemplateResponse:
    """끝자리 유니크 수 분포 분석 페이지 (SPEC-LOTTO-072).

    - 요약 카드: 분석 회차 / 평균 유니크 개수 / 최다 개수 / 모두 다른 비율(==6)
    - 분포 테이블: 6개 고정 개수("1".."6")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)의 서로 다른 끝자리 개수(1~6)를 집계한다.
    - SPEC-055(끝자리별 분포)·SPEC-063(끝자리 합계)과 독립적인 별도 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_last_digit_unique_stats(wd.get_draws())
    return _render(request, "last_digit_unique.html", {
        "active_tab": "last_digit_unique",
        "stats": stats,
    })


@router.get("/stats/mult3")
async def stats_mult3_page(request: Request) -> TemplateResponse:
    """3의 배수 포함 개수 분포 분석 페이지 (SPEC-LOTTO-073).

    - 요약 카드: 분석 회차 / 평균 개수 / 최빈 개수 / 3개 이상 비율(>=3)
    - 분포 테이블: 7개 고정 개수("0".."6")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)의 3배수 개수(0~6)를 집계한다.
    - SPEC-058(소수/합성수 분포)·SPEC-066(소수합)과 독립적인 별도 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_mult3_stats(wd.get_draws())
    return _render(request, "mult3.html", {
        "active_tab": "mult3",
        "stats": stats,
    })


@router.get("/stats/even-count")
async def stats_even_count_page(request: Request) -> TemplateResponse:
    """짝수 포함 개수 분포 분석 페이지 (SPEC-LOTTO-074).

    - 요약 카드: 분석 회차 / 평균 개수 / 최빈 개수 / 3개 이상 비율(>=3)
    - 분포 테이블: 7개 고정 개수("0".."6")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)의 짝수 개수(0~6)를 집계한다.
    - SPEC-061(홀짝 비율; get_odd_even_stats)과 독립적인 별도 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_even_count_stats(wd.get_draws())
    return _render(request, "even_count.html", {
        "active_tab": "even_count",
        "stats": stats,
    })


@router.get("/stats/mult5")
async def stats_mult5_page(request: Request) -> TemplateResponse:
    """5의 배수 포함 개수 분포 분석 페이지 (SPEC-LOTTO-075).

    - 요약 카드: 분석 회차 / 평균 개수 / 최빈 개수 / 3개 이상 비율(>=3)
    - 분포 테이블: 7개 고정 개수("0".."6")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)의 5배수 개수(0~6)를 집계한다.
    - SPEC-073(3의 배수)·SPEC-074(짝수 개수)와 독립적인 별도 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_mult5_stats(wd.get_draws())
    return _render(request, "mult5.html", {
        "active_tab": "mult5",
        "stats": stats,
    })


@router.get("/stats/mult4")
async def stats_mult4_page(request: Request) -> TemplateResponse:
    """4의 배수 포함 개수 분포 분석 페이지 (SPEC-LOTTO-076).

    - 요약 카드: 분석 회차 / 평균 개수 / 최빈 개수 / 3개 이상 비율(>=3)
    - 분포 테이블: 7개 고정 개수("0".."6")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)의 4배수 개수(0~6)를 집계한다.
    - SPEC-073(3의 배수)·SPEC-074(짝수)·SPEC-075(5의 배수)와 독립적인 별도 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_mult4_stats(wd.get_draws())
    return _render(request, "mult4.html", {
        "active_tab": "mult4",
        "stats": stats,
    })


@router.get("/stats/single-digit")
async def stats_single_digit_page(request: Request) -> TemplateResponse:
    """1자리 번호 포함 개수 분포 분석 페이지 (SPEC-LOTTO-077).

    - 요약 카드: 분석 회차 / 평균 개수 / 최빈 개수 / 3개 이상 비율(>=3)
    - 분포 테이블: 7개 고정 개수("0".."6")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)의 1자리(1~9) 개수(0~6)를 집계한다.
    - SPEC-073~076(3·짝수·5·4의 배수)와 독립적인 별도 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_single_digit_stats(wd.get_draws())
    return _render(request, "single_digit.html", {
        "active_tab": "single_digit",
        "stats": stats,
    })


@router.get("/stats/triple-run")
async def stats_triple_run_page(request: Request) -> TemplateResponse:
    """3연속 이상 번호 포함 분포 분석 페이지 (SPEC-LOTTO-078).

    - 요약 카드: 분석 회차 / 3연속 포함 비율(>=1) / 최빈 묶음 수 / 평균 최대 연속 길이
    - 분포 테이블: 3개 고정 묶음 수("0","1","2")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)에서 3개 이상 연속 묶음 수(0~2)를 집계한다.
    - SPEC-062(연속 패턴)·SPEC-069(연속 쌍)와 독립적인 별도 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_triple_run_stats(wd.get_draws())
    return _render(request, "triple_run.html", {
        "active_tab": "triple_run",
        "stats": stats,
    })


@router.get("/stats/digit-sum-dist")
async def stats_digit_sum_dist_page(request: Request) -> TemplateResponse:
    """끝자리 합계 분포 분석 페이지 (SPEC-LOTTO-079).

    - 요약 카드: 분석 회차 / 평균 끝자리합 / 최빈 구간 / 고합계 비율(합>=25)
    - 분포 테이블: 6개 고정 구간의 count/pct
    - 한 회차 본번호 6개(보너스 제외) 끝자리(n % 10) 합을 6개 구간으로 집계한다.
    - SPEC-063(끝자리 합 low/mid/high)과는 다른 별개 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_digit_sum_dist_stats(wd.get_draws())
    return _render(request, "digit_sum_dist.html", {
        "active_tab": "digit_sum_dist",
        "stats": stats,
    })


@router.get("/stats/max-gap-dist")
async def stats_max_gap_dist_page(request: Request) -> TemplateResponse:
    """번호 간격 최대값 분포 분석 페이지 (SPEC-LOTTO-080).

    - 요약 카드: 분석 회차 / 평균 최대간격 / 최빈 구간 / 고간격 비율(max_gap>=21)
    - 분포 테이블: 6개 고정 구간의 count/pct
    - 한 회차 정렬 본번호 6개(보너스 제외)의 인접 차이 최댓값을 6개 구간으로 집계한다.
    - SPEC-056(get_gap_stats, small/medium/large)과는 다른 별개 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_max_gap_dist_stats(wd.get_draws())
    return _render(request, "max_gap_dist.html", {
        "active_tab": "max_gap_dist",
        "stats": stats,
    })


@router.get("/stats/even-run")
async def stats_even_run_page(request: Request) -> TemplateResponse:
    """짝수 연속 포함 분포 분석 페이지 (SPEC-LOTTO-081).

    - 요약 카드: 분석 회차 / 짝수연속 포함 비율(>=1) / 최빈 그룹 수 / 평균 짝수연속 수
    - 분포 테이블: 4개 고정 묶음 수("0","1","2","3")의 count/pct
    - 한 회차 본번호 6개(보너스 제외) 중 간격 2 짝수 연속 묶음 수(0~3)를 집계한다.
    - SPEC-074(짝수 개수)·SPEC-069(연속 쌍)와는 다른 별개 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_even_run_stats(wd.get_draws())
    return _render(request, "even_run.html", {
        "active_tab": "even_run",
        "stats": stats,
    })


@router.get("/stats/decade-diversity")
async def stats_decade_diversity_page(request: Request) -> TemplateResponse:
    """10단위 다양성 분포 분석 페이지 (SPEC-LOTTO-082).

    - 요약 카드: 분석 회차 / 평균 10단위 수 / 최빈 10단위 수 / 전 구간 커버 비율(%)
    - 분포 테이블: 5개 고정 커버 수("1".."5")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)가 커버하는 서로 다른 10단위 그룹 수(1~5)를 집계한다.
    - SPEC-059(구간당 출현 개수 0~6)와는 다른 별개 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_decade_diversity_stats(wd.get_draws())
    return _render(request, "decade_diversity.html", {
        "active_tab": "decade_diversity",
        "stats": stats,
    })


@router.get("/stats/odd-run")
async def stats_odd_run_page(request: Request) -> TemplateResponse:
    """홀수 연속 포함 분포 분석 페이지 (SPEC-LOTTO-083).

    - 요약 카드: 분석 회차 / 홀수연속 포함 비율(>=1) / 최빈 그룹 수 / 평균 홀수연속 수
    - 분포 테이블: 4개 고정 묶음 수("0","1","2","3")의 count/pct
    - 한 회차 본번호 6개(보너스 제외) 중 간격 2 홀수 연속 묶음 수(0~3)를 집계한다.
    - SPEC-081(짝수 연속)의 홀수 대응이며, SPEC-060(홀짝 개수)와는 다른 별개 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_odd_run_stats(wd.get_draws())
    return _render(request, "odd_run.html", {
        "active_tab": "odd_run",
        "stats": stats,
    })


@router.get("/stats/parity-transition")
async def stats_parity_transition_page(request: Request) -> TemplateResponse:
    """홀짝 전환 횟수 분포 분석 페이지 (SPEC-LOTTO-084).

    - 요약 카드: 분석 회차 / 평균 전환 횟수 / 최빈 전환 횟수 / 고빈도 교차(>=4) 비율
    - 분포 테이블: 6개 고정 전환 횟수("0"~"5")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)를 정렬해 인접 쌍 홀짝 전환 횟수(0~5)를 집계한다.
    - SPEC-060(홀짝 개수 비율)과는 정의·출력 구조가 다른 별개 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_parity_transition_stats(wd.get_draws())
    return _render(request, "parity_transition.html", {
        "active_tab": "parity_transition",
        "stats": stats,
    })


@router.get("/stats/last-digit-pair")
async def stats_last_digit_pair_page(request: Request) -> TemplateResponse:
    """일의 자리 중복 분포 분석 페이지 (SPEC-LOTTO-085).

    - 요약 카드: 분석 회차 / 중복쌍 포함 비율 / 최빈 그룹 수 / 평균 그룹 수
    - 분포 테이블: 4개 고정 그룹 수("0"~"3")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)를 일의 자리별로 묶어 2개 이상 공유 그룹 수(0~3)를 집계한다.
    - SPEC-063/079(끝자리 합계 분포)와는 정의·출력 구조가 다른 별개 집계.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_last_digit_pair_stats(wd.get_draws())
    return _render(request, "last_digit_pair.html", {
        "active_tab": "last_digit_pair",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-086 — 합계 구간 세분화 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-086
@router.get("/stats/sum-range-detailed")
async def sum_range_detailed_page(request: Request) -> TemplateResponse:
    """번호 합계 구간 세분화 분포 분석 페이지 (SPEC-LOTTO-086).

    - 요약 카드: 총 회차 / 평균 합계 / 최빈 구간 / 중간 구간 비율(101-160%)
    - 분포 테이블: 6개 비균등 구간("21-60"~"201-255")의 count/pct
    - 한 회차 본번호 6개(보너스 제외) 합계를 10단위 세분화 구간으로 분류한다.
    - SPEC-049(/stats/sum-range, 폭 20 버킷)와는 정의·출력 구조가 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_sum_range_stats(wd.get_draws())
    return _render(request, "sum_range_detailed.html", {
        "active_tab": "sum_range_detailed",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-087 — 번호 중앙값 구간 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-087
@router.get("/stats/median-range")
async def median_range_page(request: Request) -> TemplateResponse:
    """번호 중앙값 구간 분포 분석 페이지 (SPEC-LOTTO-087).

    - 요약 카드: 총 회차 / 평균 중앙값 / 최빈 구간 / 중앙 구간(20-29) 비율(%)
    - 분포 테이블: 5개 구간("1-9"~"40-45")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)를 정렬한 3·4번째 평균(중앙값)이 속하는 10단위 구간.
    - SPEC-071(중앙값 9구간)과는 버킷 정의가 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_median_range_stats(wd.get_draws())
    return _render(request, "median_range.html", {
        "active_tab": "median_range",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-088 — 번호 간격 분산(균등도) 구간 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-088
@router.get("/stats/gap-variance")
async def gap_variance_page(request: Request) -> TemplateResponse:
    """번호 간격 분산 구간 분포 분석 페이지 (SPEC-LOTTO-088).

    - 요약 카드: 총 회차 / 평균 분산 / 최빈 구간 / 균등 간격(분산<10) 비율(%)
    - 분포 테이블: 5개 구간("0-10"~"100+")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)를 정렬한 인접 간격 5개의 모분산(균등도) 구간.
    - SPEC-056(간격 패턴)·SPEC-079(최대 간격 분포)와는 산출 대상이 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_gap_variance_stats(wd.get_draws())
    return _render(request, "gap_variance.html", {
        "active_tab": "gap_variance",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-089 — 저·고 번호 균형 조합 분포 페이지
# @MX:SPEC: SPEC-LOTTO-089
@router.get("/stats/low-high")
async def low_high_page(request: Request) -> TemplateResponse:
    """저·고 번호 균형 조합 분포 분석 페이지 (SPEC-LOTTO-089).

    - 요약 카드: 총 회차 / 평균 저번호 수 / 최빈 조합 / 균형(3저3고) 비율(%)
    - 분포 테이블: 7개 조합("0저6고"~"6저0고")의 count/pct
    - 한 회차 본번호 6개(보너스 제외)를 저(1~22)/고(23~45)로 나눈 개수 조합.
    - SPEC-061(고저 비율, 정수 키 분포)과는 출력 구조가 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_low_high_stats(wd.get_draws())
    return _render(request, "low_high.html", {
        "active_tab": "low_high_combo",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-131 — 번호 합계 끝자리 분석 페이지
# @MX:SPEC: SPEC-LOTTO-131
@router.get("/stats/sum-last-digit")
async def sum_last_digit_page(request: Request) -> TemplateResponse:
    """번호 합계 끝자리 분석 페이지 (SPEC-LOTTO-131)."""
    data = wd.get_sum_last_digit_analysis()
    return _render(request, "sum_last_digit.html", {
        "active_tab": "sum_last_digit",
        "data": data,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-132 — 연속 번호 패턴 분석 페이지
# @MX:SPEC: SPEC-LOTTO-132
@router.get("/stats/consecutive")
async def consecutive_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-132: 연속 번호 패턴 분석."""
    data = wd.get_consecutive_analysis()
    return _render(request, "consecutive.html", {
        "active_tab": "consecutive",
        "data": data,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-091 — 소수 이웃 포함 개수 분포 페이지
# @MX:SPEC: SPEC-LOTTO-091
@router.get("/stats/prime-neighbor")
async def prime_neighbor_page(request: Request) -> TemplateResponse:
    """소수 이웃 번호 포함 분포 분석 페이지 (SPEC-LOTTO-091).

    - 요약 카드: 총 회차 / 평균 이웃 수 / 최빈 개수 / 고밀도(5개 이상) 비율(%)
    - 분포 테이블: 7개 키("0"~"6")의 count/pct
    - 본번호 6개(보너스 제외) 중 소수 이웃(소수 또는 소수±1) 포함 개수로 분류.
    - SPEC-058(소수 개수만)과는 출력 구조가 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_prime_neighbor_stats(wd.get_draws())
    return _render(request, "prime_neighbor.html", {
        "active_tab": "prime_neighbor",
        "stats": stats,
    })


@router.get("/stats/cluster-count")
async def cluster_count_page(request: Request) -> TemplateResponse:
    """번호 군집 수 분포 분석 페이지 (SPEC-LOTTO-092).

    - 요약 카드: 총 회차 / 평균 군집 수 / 최빈 군집 수 / 군집 존재 비율(%)
    - 분포 테이블: 4개 키("0"~"3")의 count/pct
    - 정렬된 본번호 6개(보너스 제외)에서 간격 1인 연속 묶음(길이 2 이상) 개수로 분류.
    - SPEC-069/062/078(연속 관련 지표)와는 출력 구조가 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_cluster_stats(wd.get_draws())
    return _render(request, "cluster_count.html", {
        "active_tab": "cluster_count",
        "stats": stats,
    })


@router.get("/stats/first-last-zone")
async def first_last_zone_page(request: Request) -> TemplateResponse:
    """첫·마지막 번호 구간 조합 분포 분석 페이지 (SPEC-LOTTO-093).

    - 요약 카드: 총 회차 / 평균 범위(max-min) / 최빈 조합 / 광범위(AC) 비율(%)
    - 분포 테이블: 6개 조합 키("AA"~"CC")의 count/pct
    - 본번호 6개 최솟값·최댓값 소속 구간(A:1-15/B:16-30/C:31-45) 조합으로 분류.
    - SPEC-064(최솟값·최댓값 값/범위)와는 출력 구조가 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_first_last_zone_stats(wd.get_draws())
    return _render(request, "first_last_zone.html", {
        "active_tab": "first_last_zone",
        "stats": stats,
    })


@router.get("/stats/alternation")
async def alternation_page(request: Request) -> TemplateResponse:
    """홀짝 교차 패턴 분포 분석 페이지 (SPEC-LOTTO-094).

    - 요약 카드: 총 회차 / 평균 교차수 / 최빈 교차단계 / 완전교차(교차5) 비율(%)
    - 분포 테이블: 6개 단계 키("교차0"~"교차5")의 count/pct
    - 본번호 6개를 정렬한 뒤 인접 쌍의 홀짝 교차 횟수(0~5)로 분류.
    - SPEC-084(홀짝 전환 횟수 + 고빈도 비율)와는 출력 구조가 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_alternation_stats(wd.get_draws())
    return _render(request, "alternation.html", {
        "active_tab": "alternation",
        "stats": stats,
    })


@router.get("/stats/span")
async def span_page(request: Request) -> TemplateResponse:
    """번호 스팬(max-min) 분포 분석 페이지 (SPEC-LOTTO-095).

    - 요약 카드: 총 회차 / 평균 스팬 / 최빈 버킷 / 좁은(≤20)·넓은(≥36) 비율(%)
    - 분포 테이블: 7개 버킷 키("10 이하"~"41 이상")의 count/pct
    - 본번호 6개의 최댓값-최솟값을 7개 고정 버킷으로 분류.
    - SPEC-064(최솟값·최댓값 값/범위)와는 출력 구조가 다른 별개 페이지.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_span_stats(wd.get_draws())
    return _render(request, "span.html", {
        "active_tab": "span",
        "stats": stats,
    })


@router.get("/stats/min-gap-dist")
async def min_gap_dist_page(request: Request) -> TemplateResponse:
    """최소 간격 구간 분포 분석 페이지 (SPEC-LOTTO-096).

    - 요약 카드: 총 회차 / 평균 min_gap / 최빈 구간 / 연속번호(≥1) 비율 / 대형 간격(≥6) 비율(%)
    - 분포 테이블: 6개 버킷 키("1"~"11+")의 count/pct
    - 본번호 6개의 인접 차이 최솟값을 6개 고정 버킷으로 분류.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_min_gap_dist_stats(wd.get_draws())
    return _render(request, "min_gap_dist.html", {
        "active_tab": "min_gap_dist",
        "stats": stats,
    })


@router.get("/stats/gap-median-dist")
async def gap_median_dist_page(request: Request) -> TemplateResponse:
    """번호 간격 중앙값 구간 분포 분석 페이지 (SPEC-LOTTO-097).

    - 요약 카드: 총 회차 / 평균 gap_median / 최빈 구간 / 조밀(<=4) 비율 / 광간(>=9) 비율(%)
    - 분포 테이블: 6개 버킷 키("1-2"~"11+")의 count/pct
    - 본번호 6개의 인접 차이 정렬 후 중앙값을 6개 고정 버킷으로 분류.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_gap_median_dist_stats(wd.get_draws())
    return _render(request, "gap_median_dist.html", {
        "active_tab": "gap_median_dist",
        "stats": stats,
    })


@router.get("/stats/quartile-dist")
async def quartile_dist_page(request: Request) -> TemplateResponse:
    """번호 사분위 분포 분석 페이지 (SPEC-LOTTO-099).

    - 요약 카드: 총 회차 / Q1~Q4 평균 / 균형 비율 / 쏠림 비율 / 최빈 패턴
    - 분포 테이블: 관측된 패턴의 count/pct (상위 10개)
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    from lotto.web import data as wd

    stats = wd.get_quartile_dist_stats(wd.get_draws())
    return _render(request, "quartile_dist.html", {
        "active_tab": "quartile_dist",
        "stats": stats,
    })


@router.get("/stats/zone-coverage")
async def zone_coverage_page(request: Request) -> TemplateResponse:
    """구간별 번호 선택 분포 분석 페이지 (SPEC-LOTTO-098).

    - 요약 카드: 총 회차 / 평균 커버 구간 수 / 최빈 커버 구간
      / 완전분산(6구간) 비율 / 집중(3구간 이하) 비율
    - 분포 테이블: 6개 버킷 키("1"~"6")의 count/pct
    - 1-45 번호를 9개 구간(각 5개)으로 나누어 커버 구간 수를 분류.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 안내 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    stats = wd.get_zone_coverage_stats(wd.get_draws())
    return _render(request, "zone_coverage.html", {
        "active_tab": "zone_coverage",
        "stats": stats,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-046 — 당첨금 연도별 비교 페이지
# @MX:SPEC: SPEC-LOTTO-046
@router.get("/stats/yearly-prize")
async def yearly_prize_page(request: Request) -> TemplateResponse:
    """당첨금 연도별 비교 페이지 — 연도별 평균 막대 차트 + 통계 테이블 (SPEC-LOTTO-046).

    - 요약 카드: 전체 평균 / 최고·최저 평균 연도
    - 연도별 평균 1등 당첨금 막대 차트 (Chart.js)
    - 연도별 상세 테이블 (최고/최저 평균 연도 하이라이트)
    - 데이터 부재 시 빈 상태 메시지
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    report = wd.yearly_prize_comparison(wd.get_draws())
    return _render(request, "yearly_prize.html", {
        "active_tab": "yearly_prize",
        "report": report,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-049 — 합계 범위 분석 페이지
# @MX:SPEC: SPEC-LOTTO-049
@router.get("/stats/sum-range")
async def sum_range_page(request: Request) -> TemplateResponse:
    """합계 범위 분석 페이지 — 합계 분포 막대 차트 + 테이블 + 조합 체커 (SPEC-LOTTO-049).

    - 요약 카드: 평균/최소/최대 합계, 최빈 구간, 공통 영역
    - 합계 버킷 분포 막대 차트 (Chart.js, 최빈 구간 강조)
    - 분포 상세 테이블
    - 조합 합계 체커 폼 (번호 6개 → /api/stats/sum-range/evaluate 호출)
    - 데이터 부재(total_draws==0) 시 빈 상태 메시지
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    analysis = wd.sum_range_analysis(wd.get_draws())
    return _render(request, "sum_range.html", {
        "active_tab": "sum_range",
        "analysis": analysis,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-043 — 연속 번호 패턴 분석 페이지
# @MX:SPEC: SPEC-LOTTO-043 REQ-CONSEC-040
@router.get("/patterns/consecutive")
async def consecutive_pattern_page(
    request: Request,
    recent_n: Optional[int] = Query(default=None, ge=1, le=2000),  # noqa: UP045
) -> TemplateResponse:
    """연속 번호 패턴 분석 페이지 — 연속 비율/런 길이 분포/연속 쌍/최장 런 (SPEC-LOTTO-043).

    - recent_n 미지정: 전체 회차 분석. 지정 시 최신 N회차로 윈도 제한.
    - 데이터 부재(total_draws==0) 시에도 200 (빈 상태 메시지).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    pattern = wd.consecutive_pattern(wd.get_draws(), recent_n=recent_n)
    # 런 길이 분포 바 차트용 최댓값 (0 나눗셈 방지)
    run_dist = pattern["run_length_distribution"]
    run_max = max(run_dist.values()) if run_dist else 0
    return _render(request, "patterns_consecutive.html", {
        "active_tab": "patterns_consecutive",
        "recent_n": recent_n,
        "pattern": pattern,
        "run_max": run_max,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-039 — 당첨번호 예측 리포트 페이지
# @MX:SPEC: SPEC-LOTTO-039
@router.get("/prediction")
async def prediction_page(request: Request) -> TemplateResponse:
    """예측 리포트 페이지 — 최근 50회차 복합 스코어링 결과 시각화 (SPEC-LOTTO-039).

    - 요약: 분석 회차 수, 분석 기준(recent_n)
    - 상위 후보 테이블: 번호 / composite_score / 4차원 breakdown 막대
    - 추천 조합 카드 3종 (각 6개 번호 공)
    - 데이터 부재 시 빈 상태 메시지
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    report = wd.prediction_report(wd.get_draws(), recent_n=50)
    return _render(request, "prediction.html", {
        "active_tab": "prediction",
        "report": report,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-052 — 전략 백테스팅 분석 페이지
# @MX:SPEC: SPEC-LOTTO-052
@router.get("/backtest")
async def backtest_page(
    request: Request,
    n: int = 50,
) -> TemplateResponse:
    """전략 백테스팅 페이지 — 11개 전략의 과거 적중 성능을 표로 표시 (SPEC-LOTTO-052).

    - 각 전략의 평균 적중/적중 분포(0~6)/최고 회차/종합 점수를 표시한다.
    - 데이터 부족(20회 미만) 시 안내 메시지를 렌더한다 (REQ-BT-009).
    - ?n=N 으로 평가 윈도를 조정한다 (기본 50, REQ-BT-006/017).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    n = max(1, n)
    draws = wd.get_draws() or []
    result = wd.run_backtest(draws, n_past=n)

    error_message: str | None = None
    rows: list[dict[str, Any]] = []
    if "error" in result:
        error_message = str(result["error"])
    else:
        # REQ-BT-006: score 내림차순 정렬된 전략 행 목록
        for label, br in result.items():
            rows.append({
                "strategy_label": label,
                "avg_match": br["avg_match"],
                "match_counts": br["match_counts"],
                "best_draw": br["best_draw"],
                "score": br["score"],
            })
        rows.sort(key=lambda r: r["score"], reverse=True)

    return _render(request, "backtest.html", {
        "active_tab": "backtest",
        "n_past": n,
        "rows": rows,
        "error_message": error_message,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-040 — 번호 비교 분석기 페이지
# @MX:SPEC: SPEC-LOTTO-040
@router.get("/compare")
async def compare_page(request: Request) -> TemplateResponse:
    """번호 비교 분석기 페이지 — 6개 번호 입력 후 역대 회차와 비교 (SPEC-LOTTO-040).

    - 6개 번호 입력 폼
    - 결과 영역: 일치 수준별 회차 통계, 번호 빈도 바, 종합 등급 카드
    - 데이터 부재 시에도 200 (클라이언트가 빈 결과를 자연스럽게 렌더링)
    """
    data_status = get_data_status()
    return _render(request, "compare.html", {
        "active_tab": "compare",
        "data_status": data_status,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-027 REQ-SET-001 — 웹 설정 관리 페이지
# @MX:SPEC: SPEC-LOTTO-027 REQ-SET-001
@router.get("/settings")
async def settings_page(request: Request) -> TemplateResponse:
    """설정 현황 페이지 — 마스킹된 설정 상태 카드 + 테스트 발송 버튼 (REQ-SET-001).

    실제 URL/이메일 값은 노출하지 않고 마스킹된 값만 표시한다.
    """
    # 함수 내부 임포트: notifier 의 settings 를 patch 하는 테스트와 호환
    from lotto.web import notifier as _notifier

    data_status = get_data_status()
    settings_status = _notifier.get_full_settings_status()
    # 빈 상태 판정: 모든 채널/스케줄러가 비활성일 때 안내 문구 노출
    any_configured = (
        settings_status["webhook_enabled"]
        or settings_status["email_enabled"]
        or settings_status["scheduler_enabled"]
        or settings_status["notify_threshold"] > 0
    )
    return _render(request, "settings.html", {
        "active_tab": "settings",
        "data_status": data_status,
        "settings_status": settings_status,
        "any_configured": any_configured,
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


@router.get("/stats/fitness")
async def fitness_page(
    request: Request,
    numbers: Optional[str] = Query(None),  # noqa: UP045 — Python 3.9 FastAPI 호환
) -> TemplateResponse:
    """번호 조합 적합도 점수 분석 페이지.

    Query:
        numbers: 쉼표로 구분된 6개 번호 (선택, 예: "1,7,14,21,35,42")
    """
    from lotto.web import data as wd

    stats = None
    error_msg = None

    if numbers:
        try:
            nums = [int(x.strip()) for x in numbers.split(",") if x.strip()]
            stats = wd.get_fitness_score(nums, wd.get_draws())
        except (ValueError, TypeError) as exc:
            error_msg = str(exc)

    return _render(request, "fitness.html", {
        "active_tab": "fitness",
        "stats": stats,
        "numbers": numbers or "",
        "error_msg": error_msg,
    })


@router.get("/stats/fitness-recommend")
async def fitness_recommend_page(
    request: Request,
    count: int = Query(default=5, ge=1, le=20),
    min_score: float = Query(default=60.0, ge=0.0, le=100.0),
    pool_size: int = Query(default=1000, ge=1, le=5000),
) -> TemplateResponse:
    """적합도 기반 번호 추천 페이지.

    Query:
        count: 추천 개수 (1~20, 기본 5)
        min_score: 최소 적합도 점수 (0~100, 기본 60.0)
        pool_size: 평가할 무작위 조합 개수 (1~5000, 기본 1000)
    """
    from lotto.web import data as wd

    recommendations = None
    error_msg = None
    try:
        draws = wd.get_draws()
        recommendations = wd.get_fitness_recommendations(
            count=count, min_score=min_score, pool_size=pool_size, draws=draws
        )
    except (ValueError, TypeError) as exc:
        error_msg = str(exc)

    return _render(request, "fitness_recommend.html", {
        "active_tab": "fitness_recommend",
        "recommendations": recommendations,
        "count": count,
        "min_score": min_score,
        "pool_size": pool_size,
        "error_msg": error_msg,
    })


# SPEC-LOTTO-102: 번호 조합 시뮬레이션 페이지
@router.get("/stats/simulate")
async def simulate_combo_page(request: Request) -> TemplateResponse:
    """번호 조합 회차별 백테스트 페이지.

    6개 번호 입력 폼을 렌더링하며, 결과는 JavaScript fetch로
    POST /api/stats/simulate를 호출해 표시한다.
    """
    return _render(request, "simulate_combo.html", {
        "active_tab": "combo_simulate",
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-103 — 보너스 번호 분석 페이지
# @MX:SPEC: SPEC-LOTTO-103 REQ-BON-E03
@router.get("/stats/bonus")
async def bonus_page(
    request: Request,
    recent_n: int = Query(default=50, ge=1, le=500),
) -> TemplateResponse:
    """보너스 번호 분석 페이지 — 빈도·비율·동시출현·최근추세 시각화 (SPEC-LOTTO-103).

    - top10 강조, recent_n 선택기, 번호별 테이블(번호/총 횟수/비율/최근 횟수/상태)
    - recent_n 쿼리로 최근 윈도우를 조정한다 (REQ-BON-E04).
    - 데이터 부재 시에도 200 (빈 상태를 자연스럽게 렌더링).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    analysis = wd.get_bonus_analysis(wd.get_draws(), recent_n=recent_n)
    return _render(request, "bonus_analysis.html", {
        "active_tab": "bonus",
        "analysis": analysis,
        "recent_n": recent_n,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-104 — 번호 출현 주기 분석 페이지
# @MX:SPEC: SPEC-LOTTO-104 REQ-REC-E03
@router.get("/stats/recency")
async def recency_page(
    request: Request,
    top_n: int = Query(default=10, ge=1, le=45),
) -> TemplateResponse:
    """번호 주기 분석 페이지 — last_seen_ago·간격(평균/최대/최소)·연체·최근 (SPEC-LOTTO-104).

    - 45개 번호 테이블, overdue 강조, recent 배지, top_n 선택기
    - top_n 쿼리로 연체 목록 크기를 조정한다 (REQ-REC-E04).
    - 데이터 부재 시에도 200 (빈 상태를 자연스럽게 렌더링).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    analysis = wd.get_recency_analysis(wd.get_draws(), top_n=top_n)
    return _render(request, "recency_analysis.html", {
        "active_tab": "recency",
        "analysis": analysis,
        "top_n": top_n,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-105 — 번호 위치별 분포 분석 페이지
# @MX:SPEC: SPEC-LOTTO-105 REQ-POS-011
@router.get("/stats/position")
async def position_page(
    request: Request,
    top_n: int = Query(default=5, ge=1, le=45),
) -> TemplateResponse:
    """위치별 분포 분석 페이지 — 위치(1~6)별 avg/median/min/max/std/최빈 번호 (SPEC-LOTTO-105).

    - 6개 위치 테이블, top_n 선택기(3/5/10), disclaimer 노출 (서버 렌더링, JS 비의존).
    - top_n 쿼리로 위치별 최빈 번호 개수를 조정한다 (REQ-POS-012).
    - 데이터 부재 시에도 200 (빈 상태를 자연스럽게 렌더링).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    result = wd.get_position_distribution(wd.get_draws(), top_n=top_n)
    return _render(request, "position_distribution.html", {
        "active_tab": "position",
        "result": result,
        "top_n": top_n,
    })


# @MX:NOTE: [AUTO] SPEC-LOTTO-106 — 홀짝·고저 조합 매트릭스 분석 페이지
# @MX:SPEC: SPEC-LOTTO-106 REQ-CROSS-011
@router.get("/stats/cross-pattern")
async def cross_pattern_page(
    request: Request,
    top_n: int = Query(default=10, ge=1, le=49),
) -> TemplateResponse:
    """조합 매트릭스 페이지 — 홀짝 개수×고번호(>23) 개수 7×7 교차 빈도 (SPEC-LOTTO-106).

    - 7×7 매트릭스 테이블, 상위 조합 강조, 주변합 행/열, top_n 선택기(5/10/20), disclaimer.
    - top_n 쿼리로 상위 조합 개수를 조정한다 (REQ-CROSS-010, 서버 렌더링·JS 비의존).
    - 데이터 부재 시에도 200 (빈 상태를 자연스럽게 렌더링).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    result = wd.get_cross_pattern_stats(wd.get_draws(), top_n=top_n)
    return _render(request, "cross_pattern.html", {
        "active_tab": "cross_pattern",
        "result": result,
        "top_n": top_n,
    })


@router.get("/stats/period-trend")
async def period_trend_page(
    request: Request,
    top_n: int = Query(default=10, ge=1, le=45),
) -> TemplateResponse:
    """추이 분석 페이지 — 초기/중기/최근 3구간 번호별 빈도 추이 (SPEC-LOTTO-107).

    - 구간 요약(early/middle/recent 회차 수), 상승/하락 상위 번호 테이블,
      top_n 선택기(5/10/20), disclaimer.
    - top_n 쿼리로 상위 번호 개수를 조정한다 (REQ-PT-008, 서버 렌더링·JS 비의존).
    - 데이터 부재 시에도 200 (빈 상태를 자연스럽게 렌더링).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    result = wd.get_period_trend(wd.get_draws(), top_n=top_n)
    return _render(request, "period_trend.html", {
        "active_tab": "period_trend",
        "result": result,
        "top_n": top_n,
    })


@router.get("/stats/monthly")
async def monthly_distribution_page(
    request: Request,
    top_n: int = Query(default=5, ge=1, le=45),
) -> TemplateResponse:
    """월별 분포 페이지 — 추첨일의 달(1~12월) 기준 번호별 출현 분포 (SPEC-LOTTO-108).

    - 12개월 요약(회차 수), 월별 상위 번호, 번호별 최빈 월, top_n 선택기(3/5/10), disclaimer.
    - top_n 쿼리로 월별 상위 번호 개수를 조정한다 (REQ-MD-007, 서버 렌더링·JS 비의존).
    - 데이터 부재 시에도 200 (빈 상태를 자연스럽게 렌더링).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    result = wd.get_monthly_distribution(wd.get_draws(), top_n=top_n)
    return _render(request, "monthly_distribution.html", {
        "active_tab": "monthly",
        "result": result,
        "top_n": top_n,
    })


@router.get("/stats/yearly")
async def yearly_distribution_page(
    request: Request,
    top_n: int = Query(default=5, ge=1, le=45),
) -> TemplateResponse:
    """연도별 분포 페이지 — 추첨일의 연도(달력 연도) 기준 번호별 출현 분포 (SPEC-LOTTO-110).

    - 연도별 요약(회차 수), 연도별 상위 번호, 번호별 최빈 연도, top_n 선택기(3/5/10),
      disclaimer.
    - top_n 쿼리로 연도별 상위 번호 개수를 조정한다 (REQ-YD-009, 서버 렌더링·JS 비의존).
    - 데이터 부재 시에도 200 (빈 상태를 자연스럽게 렌더링).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    result = wd.get_yearly_distribution(wd.get_draws(), top_n=top_n)
    return _render(request, "yearly_distribution.html", {
        "active_tab": "yearly",
        "result": result,
        "top_n": top_n,
    })


@router.get("/stats/historic-match")
async def historic_match_page(
    request: Request,
    numbers: Optional[str] = Query(None),
) -> TemplateResponse:
    """SPEC-LOTTO-114: 역대 당첨 일치 이력 조회 페이지."""
    from lotto.web import data as wd

    stats = None
    error_msg = None

    if numbers:
        try:
            nums = [int(x.strip()) for x in numbers.split(",") if x.strip()]
            if len(nums) != 6:
                error_msg = "6개 번호를 입력해주세요."
            elif not all(1 <= n <= 45 for n in nums):
                error_msg = "번호는 1~45 사이여야 합니다."
            elif len(set(nums)) != 6:
                error_msg = "중복된 번호가 있습니다."
            else:
                stats = wd.get_historic_match(nums, wd.get_draws())
        except (ValueError, TypeError) as exc:
            error_msg = str(exc)

    return _render(request, "historic_match.html", {
        "active_tab": "historic_match",
        "stats": stats,
        "numbers": numbers or "",
        "error_msg": error_msg,
    })


@router.get("/stats/gap-distribution")
async def gap_distribution_page(request: Request) -> TemplateResponse:
    """간격 분포 페이지 — 번호별 연속 출현 간격(drwNo 차이) 상세 분포 (SPEC-LOTTO-109).

    - 전체 요약(역대 최대·최소 간격), 45개 번호 테이블(간격 수/avg/min/max/std/
      6버킷 히스토그램), disclaimer. 서버 렌더링·JS 비의존.
    - top_n 파라미터 없음 — 항상 45개 번호 전부 렌더링한다.
    - 데이터 부재 시에도 200 (빈 상태를 자연스럽게 렌더링).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    result = wd.get_gap_distribution(wd.get_draws())
    return _render(request, "gap_distribution.html", {
        "active_tab": "gap_dist",
        "result": result,
    })


@router.get("/stats/heatmap")
async def heatmap_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-117: 번호별 통합 점수 히트맵."""
    data = wd.get_number_heatmap()
    return _render(request, "heatmap.html", {
        "active_tab": "heatmap",
        "heatmap_data": data,
    })


@router.get("/stats/carryover")
async def carryover_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-118: 이월 번호 분석."""
    data = wd.get_carryover_analysis()
    return _render(request, "carryover.html", {
        "active_tab": "carryover",
        "data": data,
    })


@router.get("/stats/combo-guide")
async def combo_guide_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-119: 번호 조합 가이드."""
    data = wd.get_combo_guide()
    return _render(request, "combo_guide.html", {
        "active_tab": "combo_guide",
        "data": data,
    })


@router.get("/stats/seasonal")
async def seasonal_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-120: 계절별 번호 출현 분석."""
    data = wd.get_seasonal_analysis()
    return _render(request, "seasonal.html", {
        "active_tab": "seasonal",
        "data": data,
    })


@router.get("/stats/prime-numbers")
async def prime_numbers_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-124: 소수 번호 분석."""
    data = wd.get_prime_analysis()
    return _render(request, "prime_numbers.html", {
        "active_tab": "prime_numbers",
        "data": data,
    })


@router.get("/stats/std-deviation")
async def std_deviation_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-125: 번호 표준편차 분석."""
    data = wd.get_std_deviation_analysis()
    return _render(request, "std_deviation.html", {
        "active_tab": "std_deviation",
        "data": data,
    })


@router.get("/stats/range-combo")
async def range_combo_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-126: 번호 구간 조합 분석."""
    data = wd.get_range_combo_analysis()
    return _render(request, "range_combo.html", {
        "active_tab": "range_combo",
        "data": data,
    })


@router.get("/stats/multiples")
async def multiples_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-127: 배수 분석."""
    data = wd.get_multiples_analysis()
    return _render(request, "multiples.html", {
        "active_tab": "multiples",
        "data": data,
    })


@router.get("/stats/hot-cold")
async def hot_cold_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-128: 핫/콜드 번호 분석."""
    data = wd.get_hot_cold_analysis()
    return _render(request, "hot_cold.html", {
        "active_tab": "hot_cold",
        "data": data,
    })


@router.get("/stats/pair-frequency")
async def pair_frequency_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-133: 번호 쌍 동시 출현 빈도 분석."""
    data = wd.get_pair_frequency_analysis()
    return _render(request, "pair_frequency.html", {
        "active_tab": "pair_frequency",
        "data": data,
    })


@router.get("/stats/shared-numbers")
async def shared_numbers_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-134: 연속 회차 공유 번호 분석."""
    data = wd.get_shared_numbers_analysis()
    return _render(request, "shared_numbers.html", {
        "active_tab": "shared_numbers",
        "data": data,
    })


@router.get("/stats/special-numbers")
async def special_numbers_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-135: 특수 번호(삼각수·제곱수) 분석."""
    data = wd.get_special_numbers_analysis()
    return _render(request, "special_numbers.html", {
        "active_tab": "special_numbers",
        "data": data,
    })


@router.get("/stats/position-dist")
async def position_dist_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-136: 번호 위치별 분포 분석."""
    data = wd.get_position_dist_analysis()
    return _render(request, "position_dist.html", {
        "active_tab": "position_dist",
        "data": data,
    })


@router.get("/stats/units-digit")
async def units_digit_page(request: Request) -> TemplateResponse:
    """SPEC-LOTTO-137: 번호 끝자리(일의 자리) 분포 분석."""
    data = wd.get_units_digit_analysis()
    return _render(request, "units_digit.html", {
        "active_tab": "units_digit",
        "data": data,
    })
