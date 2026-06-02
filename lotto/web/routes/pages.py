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
