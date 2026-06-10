"""API 라우터 — JSON 엔드포인트.

# @MX:ANCHOR: [AUTO] 웹 대시보드 REST API 게이트웨이
# @MX:REASON: 외부 클라이언트(브라우저 JS, 자동화 도구)에서 직접 호출되는 공개 API 경계
"""

from __future__ import annotations

import datetime
import io
import logging
import threading
from pathlib import Path
from typing import (  # noqa: UP035 — FastAPI는 Python 3.9에서 List/Union 런타임 평가 필요
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,  # noqa: UP045 — FastAPI requires Optional for Query params on Python 3.9
    Union,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi import Path as FastAPIPath  # noqa: N814 — pathlib.Path와 충돌 방지 별칭
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, field_validator, model_validator

from lotto.config import settings
from lotto.web import data as wd  # SPEC-LOTTO-054: 모듈 레벨 patch 호환용 별칭
from lotto.web.data import (
    get_draws,
    get_favorites,
    get_history,
    get_recommendations,
    get_reservations,
    get_simulation,
    get_stats,
    hot_cold_analysis,
    invalidate_cache,
    pattern_analysis,
    save_favorites,
    save_reservations,
    save_simulation_result,
    trend_heatmap,
    weekly_report,
)

# SPEC-LOTTO-002: 모듈 로거 — 무음 예외를 구조화 로깅으로 전환
logger = logging.getLogger(__name__)

# 수집 진행 상태 (단일 서버 프로세스 내 공유)
_collect_state: dict[str, Any] = {
    "status": "idle",   # idle | running | done | error
    "current": 0,
    "total": 0,
    "collected": 0,
    "message": "",
}
_collect_lock = threading.Lock()

# SPEC-LOTTO-012 REQ-HLT-004: 서버 가동 시각 — /api/health uptime 계산용
# 모듈 로딩 시 임시 값을 두고, FastAPI lifespan 시작 시점에서 재설정한다.
_startup_time: datetime.datetime = datetime.datetime.now()


# @MX:NOTE: [AUTO] importlib.metadata.version 우회 진입점 — 테스트에서 패치 가능
# @MX:SPEC: SPEC-LOTTO-012 REQ-HLT-005
def _pkg_version_lookup(name: str) -> str:
    """패키지 버전 조회를 별도 함수로 분리하여 테스트 가능하게 한다."""
    from importlib.metadata import version as _v

    return _v(name)


router = APIRouter(prefix="/api")


# SPEC-LOTTO-012: GET /api/health 응답 모델
class HealthDataResponse(BaseModel):
    """헬스체크 데이터 상태 하위 객체."""

    csv_exists: bool
    csv_rows: int
    stats_exists: bool
    last_sync: Optional[str]  # noqa: UP045 — Pydantic + Python 3.9 호환


class HealthResponse(BaseModel):
    """GET /api/health 응답 모델 (REQ-HLT-001~005)."""

    status: str  # "ok" or "degraded"
    uptime_seconds: float
    data: HealthDataResponse
    version: str


# @MX:ANCHOR: [AUTO] 운영 모니터링 진입점 — 외부 헬스체크/k8s probe 가 의존
# @MX:REASON: 가용성 판정의 단일 진실 공급원 — 변경 시 SLO/알람 영향
# @MX:SPEC: SPEC-LOTTO-012 REQ-HLT-001~005
@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """운영 상태 확인 엔드포인트.

    - REQ-HLT-001: HTTP 200 상태로 status 필드("ok"/"degraded") 반환
    - REQ-HLT-002: csv + stats 모두 존재 시 "ok", 아니면 "degraded"
    - REQ-HLT-003: data.csv_rows 는 헤더 제외 행 수
    - REQ-HLT-004: uptime_seconds 는 서버 시작 이후 경과 초
    - REQ-HLT-005: version 미설치 시 "unknown" 반환
    """
    from importlib.metadata import PackageNotFoundError

    csv_path = Path("data/draws.csv")
    stats_path = Path("data/stats.json")
    last_sync_path = Path("data/last_sync.json")

    csv_exists = csv_path.exists()
    stats_exists = stats_path.exists()

    csv_rows = 0
    if csv_exists:
        try:
            # 큰 파일도 안전하도록 스트리밍으로 행 수 계산 (헤더 제외)
            with csv_path.open() as f:
                csv_rows = sum(1 for _ in f) - 1
        except OSError:
            csv_rows = 0

    last_sync: Optional[str] = None  # noqa: UP045
    if last_sync_path.exists():
        try:
            import json

            data = json.loads(last_sync_path.read_text())
            last_sync = data.get("last_sync_date") or data.get("date")
        except (OSError, ValueError, KeyError):
            # 손상된 last_sync.json 은 무시하고 None 으로 유지 (REQ-HLT-005)
            last_sync = None

    try:
        pkg_version = _pkg_version_lookup("lotto")
    except PackageNotFoundError:
        pkg_version = "unknown"

    status = "ok" if (csv_exists and stats_exists) else "degraded"
    uptime = (datetime.datetime.now() - _startup_time).total_seconds()

    return HealthResponse(
        status=status,
        uptime_seconds=uptime,
        data=HealthDataResponse(
            csv_exists=csv_exists,
            csv_rows=max(csv_rows, 0),
            stats_exists=stats_exists,
            last_sync=last_sync,
        ),
        version=pkg_version,
    )


@router.get("/draws")
async def list_draws(
    limit: int = Query(default=50, ge=1, le=200, description="페이지 크기 (1~200)"),
    offset: int = Query(default=0, ge=0, description="페이지 오프셋 (>=0)"),
    from_round: Optional[int] = Query(  # noqa: UP045
        default=None, ge=1, description="회차 범위 시작 (포함, >=1)"
    ),
    to_round: Optional[int] = Query(  # noqa: UP045
        default=None, ge=1, description="회차 범위 끝 (포함, >=1)"
    ),
    sort: Optional[str] = Query(  # noqa: UP045
        default=None, description="정렬 순서 (desc=최신순, asc=오래된순)"
    ),
) -> dict[str, Any]:
    """수집된 추첨 데이터를 페이지네이션 응답으로 반환합니다.

    SPEC-LOTTO-006:
    - REQ-PAGE-001: limit(기본 50, 최대 200), offset(기본 0)
    - REQ-PAGE-002: {total, limit, offset, items} 래퍼 응답
    - REQ-PAGE-003: from_round/to_round 회차 범위 필터링
    - REQ-PAGE-004: 빈 결과는 500이 아닌 200 + total=0 + items=[]
    """
    draws = get_draws()
    if draws is None:
        raise HTTPException(
            503,
            detail={
                "error": "data_unavailable",
                "message": "데이터가 없습니다. 먼저 수집을 실행해주세요.",
            },
        )

    # REQ-PAGE-003: 회차 범위 필터링
    if from_round is not None:
        draws = [d for d in draws if d.drwNo >= from_round]
    if to_round is not None:
        draws = [d for d in draws if d.drwNo <= to_round]

    # 정렬: desc=최신순(drwNo 내림차순)
    if sort == "desc":
        draws = list(reversed(draws))

    total = len(draws)
    page = draws[offset : offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [d.model_dump() for d in page],
    }


# @MX:NOTE: [AUTO] SPEC-LOTTO-029 REQ-DETAIL-001 — 회차별 상세 보기 공개 API
# @MX:SPEC: SPEC-LOTTO-029 REQ-DETAIL-001
@router.get("/draws/{drw_no}")
async def get_draw_detail(drw_no: int) -> dict[str, Any]:
    """특정 회차의 상세 정보를 반환합니다 (REQ-DETAIL-001).

    - 응답: {drwNo, drwNoDate, numbers, bonus, prize1Amount, prize1Winners}
    - prize1Amount / prize1Winners: 데이터 없으면 null
    - 회차 미존재 또는 drw_no <= 0 → 404
    """
    # drw_no <= 0 은 미존재와 동일하게 404 처리 (인수 조건)
    if drw_no <= 0:
        raise HTTPException(
            status_code=404,
            detail={"error": "draw_not_found", "message": f"{drw_no}회차를 찾을 수 없습니다."},
        )

    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    draws = wd.get_draws() or []
    draw = next((d for d in draws if d.drwNo == drw_no), None)
    if draw is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "draw_not_found", "message": f"{drw_no}회차를 찾을 수 없습니다."},
        )

    return {
        "drwNo": draw.drwNo,
        "drwNoDate": str(draw.date),
        "numbers": draw.numbers(),
        "bonus": draw.bonus,
        "prize1Amount": draw.prize1Amount,
        "prize1Winners": draw.prize1Winners,
    }


@router.get("/stats")
async def get_statistics() -> dict[str, Any]:
    """통계 분석 결과를 반환합니다. 보너스 번호 빈도 포함. 파일 없으면 503."""
    stats = get_stats()
    if stats is None:
        raise HTTPException(
            503,
            detail={
                "error": "data_unavailable",
                "message": "통계 데이터가 없습니다. 분석을 먼저 실행해주세요.",
            },
        )
    return stats.model_dump()


@router.get("/recommendations")
async def get_recommendation_list(
    count: int = Query(default=5, ge=1, le=20, description="추천 세트 수 (1~20)"),
    strategy: Optional[str] = Query(  # noqa: UP045
        default=None, description="특정 전략 라벨만 필터링 (예: 고빈도, 저빈도, 균형 등)"
    ),
) -> list[dict[str, Any]]:
    """번호 추천 결과를 반환합니다. 파일 없으면 503.

    SPEC-LOTTO-006:
    - REQ-FILTER-001: strategy 파라미터로 특정 전략만 반환
    - REQ-FILTER-002: 파라미터 미지정 시 기존 동작 유지 (count 만큼 전략 순환)
    - REQ-FILTER-003: 존재하지 않는 전략은 200 + 빈 리스트
    """
    recs = get_recommendations(count=count)
    if recs is None:
        raise HTTPException(
            503,
            detail={"error": "data_unavailable", "message": "데이터가 없습니다."},
        )
    # REQ-FILTER-001/003: 전략 필터링 — 일치하는 항목만 반환 (불일치는 빈 리스트)
    if strategy is not None:
        recs = [r for r in recs if r.strategy_label == strategy]

    # SPEC-LOTTO-033: 추천 결과를 생성 이력에 자동 저장 (실패해도 응답은 정상 반환)
    # lotto.web.data 의 append_gen_history 를 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    for r in recs:
        try:
            wd.append_gen_history(strategy=r.strategy_label, numbers=r.numbers)
        except Exception as exc:  # noqa: BLE001 — 이력 저장 실패는 응답을 막지 않는다
            logger.warning("Failed to append gen_history: %s", exc, exc_info=True)

    # SPEC-LOTTO-051 REQ-CONS-005/011: 추천 객체마다 consensus 필드 추가.
    # 11개 전략 스캔은 요청당 1회 — 모든 추천 번호의 합집합을 target으로 한 번에 계산한다.
    consensus_map: dict[int, int] = {}
    stats = wd.get_stats()
    if recs and stats is not None:
        from lotto.recommender import LottoRecommender

        target_numbers = sorted({n for r in recs for n in r.numbers})
        consensus_map = wd.get_cross_strategy_consensus(
            LottoRecommender(stats), target_numbers
        )

    payload: list[dict[str, Any]] = []
    for r in recs:
        item = r.model_dump()
        # 해당 세트 번호에 대한 합의 카운트만 추출 (번호→카운트)
        item["consensus"] = {n: consensus_map.get(n, 0) for n in r.numbers}
        payload.append(item)
    return payload


# @MX:NOTE: [AUTO] SPEC-LOTTO-033 — 번호 생성 이력 조회 공개 API
# @MX:SPEC: SPEC-LOTTO-033
@router.get("/gen-history")
async def list_gen_history() -> dict[str, Any]:
    """번호 생성 이력을 최신순 최대 50건 반환합니다 (SPEC-LOTTO-033).

    Response: {total, items: [{id, generated_at, strategy, numbers}, ...]}
    """
    from lotto.web import data as wd

    history = wd.get_gen_history()
    # 최신순 (append 순서 역순) 후 최대 50건
    items = list(reversed(history))[:50]
    return {"total": len(history), "items": items}


# @MX:NOTE: [AUTO] SPEC-LOTTO-033 — 번호 생성 이력 전체 삭제 공개 API
# @MX:SPEC: SPEC-LOTTO-033
@router.delete("/gen-history", status_code=200)
async def delete_gen_history() -> dict[str, Any]:
    """번호 생성 이력을 전체 삭제하고 삭제 건수를 반환합니다 (SPEC-LOTTO-033)."""
    from lotto.web import data as wd

    deleted = wd.clear_gen_history()
    return {"deleted": deleted}


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-019 REQ-PAT-001 — 번호 패턴 분석 API 경계
# @MX:REASON: 외부 클라이언트(analyze 페이지 JS)에서 직접 호출되는 공개 API
# @MX:SPEC: SPEC-LOTTO-019 REQ-PAT-001
@router.get("/pattern-analysis")
async def get_pattern_analysis() -> dict[str, Any]:
    """전체 추첨 데이터의 번호 패턴 분포를 반환합니다.

    REQ-PAT-001: odd_even/range_dist/consecutive/sum_range/last_digit/total_draws
    draws.csv 부재 시 503.
    """
    draws = get_draws()
    if draws is None:
        raise HTTPException(
            503,
            detail={
                "error": "data_unavailable",
                "message": "데이터가 없습니다. 먼저 수집을 실행해주세요.",
            },
        )
    return pattern_analysis(draws)


# @MX:NOTE: [AUTO] SPEC-LOTTO-026 REQ-TREND-002 — 번호 트렌드 히트맵 공개 API
# @MX:SPEC: SPEC-LOTTO-026 REQ-TREND-002
@router.get("/trend-heatmap")
async def get_trend_heatmap(
    period: str = Query(
        default="yearly",
        description="집계 기간 단위 (yearly | quarterly)",
    ),
) -> dict[str, Any]:
    """번호(1~45) × 기간별 출현 빈도 행렬을 반환합니다 (REQ-TREND-002).

    - period: yearly(기본) | quarterly. 그 외 값은 400.
    - 데이터 부재 시에도 200으로 정상 응답 (빈 periods/matrix).
    """
    if period not in ("yearly", "quarterly"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_period",
                "message": "period는 yearly 또는 quarterly여야 합니다.",
            },
        )
    return trend_heatmap(period, get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-026 REQ-TREND-004 — 핫/콜드 번호 분석 공개 API
# @MX:SPEC: SPEC-LOTTO-026 REQ-TREND-004
@router.get("/hot-cold")
async def get_hot_cold(
    recent_n: int = Query(
        default=20,
        ge=1,
        description="최근 N회 표본 크기 (최소 1, 기본 20)",
    ),
) -> dict[str, Any]:
    """최근 N회 vs 전체 평균 비교로 핫/콜드 번호를 반환합니다 (REQ-TREND-004).

    - recent_n: 최소 1, 기본 20. 총 회차보다 크면 가용 전체 사용.
    - 데이터 부재 시에도 200으로 정상 응답 (빈 hot/cold).
    """
    return hot_cold_analysis(recent_n, get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-034 — 주간 통계 리포트 공개 API
# @MX:SPEC: SPEC-LOTTO-034
@router.get("/weekly-report")
async def get_weekly_report(
    weeks: int = Query(
        default=4,
        ge=1,
        le=52,
        description="최근 N주(회차) — 최소 1, 최대 52, 기본 4",
    ),
) -> dict[str, Any]:
    """최근 N주 번호 출현 경향 요약 리포트를 반환합니다 (SPEC-LOTTO-034).

    - weeks: 1~52 범위. 범위 초과 시 FastAPI가 자동으로 422를 반환한다.
    - 데이터 부재 시에도 200으로 정상 응답 (0/빈 리스트/빈 문자열).
    """
    return weekly_report(weeks, get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-017 REQ-PRIZE-D-002 — 1등 당첨금 통계 공개 API
# @MX:SPEC: SPEC-LOTTO-017 REQ-PRIZE-D-002
@router.get("/prize-stats")
async def get_prize_statistics() -> dict[str, Any]:
    """1등 당첨금 통계를 반환합니다.

    데이터 부재 시에도 200 으로 정상 응답 (nulls + 빈 recent).
    이는 홈 페이지 카드가 빈 상태 메시지를 자연스럽게 렌더링하도록 한다.
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.get_prize_stats()


# @MX:NOTE: [AUTO] SPEC-LOTTO-038 — 전체 이력 통계 대시보드 공개 API
# @MX:SPEC: SPEC-LOTTO-038
@router.get("/stats/overview")
async def api_stats_overview() -> dict[str, Any]:
    """전체 추첨 이력 통계 요약을 반환합니다 (SPEC-LOTTO-038).

    데이터 부재 시에도 200 으로 정상 응답 (zeros + None + 빈 리스트).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.dashboard_overview(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-041 — 회차 구간 통계 공개 API
# @MX:SPEC: SPEC-LOTTO-041 REQ-RANGE-006
@router.get("/stats/range")
async def api_stats_range(
    start_drw: int = Query(..., ge=1, description="구간 시작 회차 (포함, >=1)"),
    end_drw: int = Query(..., ge=1, description="구간 끝 회차 (포함, >=1)"),
) -> dict[str, Any]:
    """지정한 회차 구간(start_drw ~ end_drw)의 통계를 반환합니다 (SPEC-LOTTO-041).

    - start_drw / end_drw: 1 이상 필수. 누락/범위 위반 시 FastAPI가 422 반환.
    - start_drw > end_drw 이면 422 (REQ-RANGE-009).
    - 데이터 부재 시에도 200 으로 정상 응답 (빈 구조).
    """
    if start_drw > end_drw:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_range",
                "message": "start_drw는 end_drw보다 클 수 없습니다.",
            },
        )
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.range_stats(start_drw, end_drw, wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-046 — 당첨금 연도별 비교 공개 API
# @MX:SPEC: SPEC-LOTTO-046
@router.get("/stats/yearly-prize")
async def api_stats_yearly_prize() -> dict[str, Any]:
    """연도별 1등 당첨금 통계 비교를 반환합니다 (SPEC-LOTTO-046).

    쿼리 파라미터 없이 전체 회차를 분석한다.
    데이터 부재 시에도 200 으로 정상 응답 (total_years=0 + 빈 years).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.yearly_prize_comparison(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-039 — 당첨번호 예측 리포트 공개 API
# @MX:SPEC: SPEC-LOTTO-039
@router.get("/prediction/report")
async def api_prediction_report(
    recent_n: int = Query(
        default=50,
        ge=1,
        le=200,
        description="분석 대상 최근 회차 수 (1~200, 기본 50)",
    ),
) -> dict[str, Any]:
    """최근 N회차 복합 스코어링 예측 리포트를 반환합니다 (SPEC-LOTTO-039).

    - recent_n: 1~200 범위. 범위 초과 시 FastAPI가 자동으로 422를 반환한다.
    - 데이터 부재 시에도 200으로 정상 응답 (빈 후보/조합 구조).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.prediction_report(wd.get_draws(), recent_n=recent_n)


# SPEC-LOTTO-042: 번호 추이 트래커 — 추적 번호 개수 한계
_TREND_MAX_NUMBERS = 3
# SPEC-LOTTO-049: 합계 평가 엔드포인트가 요구하는 번호 개수 (로또 본번호 6개)
_SUM_EVAL_REQUIRED_COUNT = 6


# @MX:NOTE: [AUTO] SPEC-LOTTO-042 — 번호 추이 트래커 공개 API
# @MX:SPEC: SPEC-LOTTO-042 REQ-TREND-T-013
@router.get("/numbers/trend")
async def get_number_trend(
    n: List[int] = Query(  # noqa: UP006, B008 — FastAPI는 Python 3.9에서 반복 Query에 List 필요
        ..., description="추적할 번호 1~3개 (예: ?n=7&n=14&n=21), 각 1~45, 중복 없음"
    ),
    recent_n: int = Query(
        default=100,
        ge=10,
        le=500,
        description="분석 대상 최신 회차 수 (10~500, 기본 100)",
    ),
) -> dict[str, Any]:
    """선택 번호(1~3개)의 최근 N회차 출현 추이를 반환합니다 (SPEC-LOTTO-042).

    - n: 1~3개, 각 1~45, 모두 서로 달라야 한다. 위반 시 422.
    - recent_n: 10~500. 범위 초과 시 FastAPI가 자동으로 422를 반환한다.
    - 데이터 부재 시에도 200으로 정상 응답 (draws_analyzed=0, numbers=[]).
    """
    # 개수 검증 (1~3개) — FastAPI는 빈 리스트를 허용하지 않으므로 상한만 확인
    if not (1 <= len(n) <= _TREND_MAX_NUMBERS):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_count",
                "message": "번호는 1~3개여야 합니다.",
            },
        )
    # 범위 검증 (각 1~45)
    if any(not (1 <= num <= 45) for num in n):  # noqa: PLR2004
        raise HTTPException(
            status_code=422,
            detail={
                "error": "out_of_range",
                "message": "번호는 1~45 범위여야 합니다.",
            },
        )
    # 중복 검증
    if len(set(n)) != len(n):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "duplicate",
                "message": "번호에 중복이 있습니다.",
            },
        )

    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.number_trend(n, recent_n=recent_n, draws=wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-047 — 번호별 당첨 주기 분석 공개 API
# @MX:SPEC: SPEC-LOTTO-047
# 주의: 정적 경로이므로 /numbers/{number}/stats 등 동적 라우트와 충돌하지 않는다.
@router.get("/numbers/cycle")
async def get_number_cycle() -> dict[str, Any]:
    """번호 1~45의 평균 출현 주기/현재 간격/상태 분석을 반환합니다 (SPEC-LOTTO-047).

    쿼리 파라미터 없이 전체 회차를 분석한다.
    데이터 부재 시에도 200 으로 정상 응답 (total_draws=0 + 전부 never 구조).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.cycle_analysis(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-049 — 회차 합계 범위 분포 공개 API
# @MX:SPEC: SPEC-LOTTO-049
@router.get("/stats/sum-range")
async def get_sum_range() -> dict[str, Any]:
    """회차 본번호 6개 합계의 분포/공통 영역 분석을 반환합니다 (SPEC-LOTTO-049).

    쿼리 파라미터 없이 전체 회차를 분석한다.
    데이터 부재 시에도 200으로 정상 응답 (total_draws=0 + 빈 구조).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.sum_range_analysis(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-054 — 롤링 윈도우 빈도 분석 API
# @MX:SPEC: SPEC-LOTTO-054 REQ-RW-010/011
@router.get("/stats/rolling")
async def get_rolling(
    windows: str = Query(
        default="10,20,50,100",
        description="비교할 윈도우 크기 (콤마 구분, 예: 10,20,50,100)",
    ),
) -> dict[str, Any]:
    """롤링 윈도우 빈도/델타/추세 분석 결과를 반환합니다 (SPEC-LOTTO-054).

    - windows: 콤마로 구분된 윈도우 크기 목록 (기본 10,20,50,100, REQ-RW-011).
    - 가용 회차보다 큰 윈도우는 조용히 생략된다 (REQ-RW-012).
    - 데이터 부재 시에도 200 으로 정상 응답 (빈 객체).

    JSON 키는 문자열이어야 하므로 윈도우 크기를 문자열 키로 직렬화한다.
    """
    # 콤마 구분 윈도우 파싱 — 정수가 아닌 토큰은 무시하고, 양의 정수만 채택한다
    parsed: list[int] = []
    for token in windows.split(","):
        token = token.strip()
        if token.isdigit() and int(token) > 0:
            parsed.append(int(token))
    window_tuple = tuple(parsed) if parsed else (10, 20, 50, 100)

    results = wd.get_rolling_frequency(wd.get_draws(), windows=window_tuple)
    # int 키 → str 키로 변환하여 JSON 직렬화 (REQ-RW-010)
    return {str(w): result for w, result in results.items()}


# @MX:NOTE: [AUTO] SPEC-LOTTO-055 — 끝자리(1의 자리) 분포 분석 API
# @MX:SPEC: SPEC-LOTTO-055 REQ-LD-012
@router.get("/stats/last-digit")
async def get_last_digit() -> list[dict[str, Any]]:
    """끝자리 0~9별 출현 분포(count/pct/avg_expected/deviation)를 반환합니다 (SPEC-LOTTO-055).

    - 끝자리 오름차순(0이 먼저)으로 10개 항목 리스트를 반환한다 (REQ-LD-012).
    - 데이터 부재 시에도 200 으로 정상 응답 (10개 모두 count 0, REQ-LD-013).
    """
    stats = wd.get_last_digit_stats(wd.get_draws())
    # dict(int 키) → 끝자리 오름차순 리스트로 직렬화
    return [stats[d] for d in range(10)]


# @MX:NOTE: [AUTO] SPEC-LOTTO-056 — 번호 간격 패턴 분석 API
# @MX:SPEC: SPEC-LOTTO-056
@router.get("/stats/gap")
async def get_gap() -> dict[str, Any]:
    """정렬된 본번호 6개의 인접 간격 패턴 통계를 반환합니다 (SPEC-LOTTO-056).

    - 회차당 5개 간격을 소(1~5)/중(6~10)/대(11+)로 분류하고 위치별 평균을 산출한다.
    - 데이터 부재 시에도 200 으로 정상 응답 (모든 수치 0).
    """
    return wd.get_gap_stats(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-057 — AC값(산술 복잡도) 분석 API
# @MX:SPEC: SPEC-LOTTO-057
@router.get("/stats/ac")
async def get_ac() -> dict[str, Any]:
    """본번호 6개의 AC값(산술 복잡도) 분포 통계를 반환합니다 (SPEC-LOTTO-057).

    - 회차별 AC(0~10)를 분포/평균/최빈/고저복잡도 비율로 집계한다.
    - ac_distribution 키는 int(0~10)이며 JSON 직렬화 시 문자열로 변환된다.
    - 데이터 부재 시에도 200 으로 정상 응답 (모든 수치 0).
    """
    return wd.get_ac_stats(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-058 — 소수/합성수 분포 분석 API
# @MX:SPEC: SPEC-LOTTO-058
@router.get("/stats/prime")
async def get_prime() -> dict[str, Any]:
    """본번호 6개의 소수/합성수 분포 통계를 반환합니다 (SPEC-LOTTO-058).

    - 회차별 소수/합성수 개수(0~6)를 분포/평균/최빈/1 출현 비율로 집계한다.
    - prime_distribution 키는 int(0~6)이며 JSON 직렬화 시 문자열로 변환된다.
    - 데이터 부재 시에도 200 으로 정상 응답 (모든 수치 0).
    """
    return wd.get_prime_stats(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-059 — 십의 자리 구간 분포 분석 API
# @MX:SPEC: SPEC-LOTTO-059
@router.get("/stats/decade")
async def get_decade() -> dict[str, Any]:
    """본번호 6개의 십의 자리 구간 분포 통계를 반환합니다 (SPEC-LOTTO-059).

    - 5개 구간(01-09 ~ 40-45)별 평균/기대/편차/출현 분포를 집계한다.
    - distribution 키는 int(0~6)이며 JSON 직렬화 시 문자열로 변환된다.
    - 데이터 부재 시에도 200 으로 정상 응답 (total_draws=0).
    """
    return wd.get_decade_stats(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-060 — 홀짝 비율 분석 API
# @MX:SPEC: SPEC-LOTTO-060
@router.get("/stats/odd-even")
async def get_odd_even() -> dict[str, Any]:
    """본번호 6개의 홀짝 비율 분포 통계를 반환합니다 (SPEC-LOTTO-060).

    - 회차별 홀수 개수(0~6)와 짝수 개수(6-홀수)를 집계해 평균/분포/비율,
      최빈 개수, 균형(3:3) 회차 수/비율을 제공한다.
    - distribution 키는 int(0~6)이며 JSON 직렬화 시 문자열로 변환된다.
    - 데이터 부재 시에도 200 으로 정상 응답 (total_draws=0).
    """
    return wd.get_odd_even_stats(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-061 — 고저 비율 분석 API
# @MX:SPEC: SPEC-LOTTO-061
@router.get("/stats/high-low")
async def get_high_low() -> dict[str, Any]:
    """본번호 6개의 고저 비율 분포 통계를 반환합니다 (SPEC-LOTTO-061).

    - 회차별 저(1~22) 개수(0~6)와 고(23~45) 개수(6-저)를 집계해 평균/분포/비율,
      최빈 개수, 균형(3:3) 회차 수/비율을 제공한다.
    - distribution 키는 int(0~6)이며 JSON 직렬화 시 문자열로 변환된다.
    - 데이터 부재 시에도 200 으로 정상 응답 (total_draws=0).
    """
    return wd.get_high_low_stats(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-049 — 임의 조합 합계의 공통 영역 진입 여부 평가 API
# @MX:SPEC: SPEC-LOTTO-049
@router.get("/stats/sum-range/evaluate")
async def evaluate_sum_combination(
    n: List[int] = Query(  # noqa: UP006, B008 — FastAPI는 Python 3.9에서 반복 Query에 List 필요
        ..., description="평가할 번호 6개 (예: ?n=1&n=7&...), 각 1~45, 중복 없음"
    ),
) -> dict[str, Any]:
    """입력 조합(6개) 합계의 공통 영역 진입 여부와 백분위를 반환합니다 (SPEC-LOTTO-049).

    - n: 정확히 6개, 각 1~45, 모두 서로 달라야 한다. 위반 시 422.
    - 데이터 부재 시에도 200 (common_zone {0,0}, percentile 0.0).
    """
    # 개수 검증 (정확히 6개)
    if len(n) != _SUM_EVAL_REQUIRED_COUNT:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_count",
                "message": "번호는 정확히 6개여야 합니다.",
            },
        )
    # 범위 검증 (각 1~45)
    if any(not (1 <= num <= 45) for num in n):  # noqa: PLR2004
        raise HTTPException(
            status_code=422,
            detail={
                "error": "out_of_range",
                "message": "번호는 1~45 범위여야 합니다.",
            },
        )
    # 중복 검증
    if len(set(n)) != len(n):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "duplicate",
                "message": "번호에 중복이 있습니다.",
            },
        )

    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.evaluate_sum(n, wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-052 — 전략 백테스팅 공개 API
# @MX:SPEC: SPEC-LOTTO-052
@router.get("/backtest")
async def get_backtest(
    n: int = Query(default=50, ge=1, description="평가할 최근 회차 수 (기본 50)"),
) -> dict[str, Any]:
    """11개 전략의 과거 적중 성능 백테스트 결과를 JSON으로 반환합니다 (SPEC-LOTTO-052).

    - 각 전략 라벨 → {match_counts, avg_match, best_draw, score} 매핑.
    - 회차 부족(20회 미만) 시 {"error": ...} 페이로드를 반환한다 (REQ-BT-009).
    - look-ahead bias 제거: 회차마다 prior_draws로 통계를 재구성한다 (run_backtest).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    draws = wd.get_draws() or []
    return wd.run_backtest(draws, n_past=n)


# @MX:NOTE: [AUTO] SPEC-LOTTO-030 — 번호별 상세 통계 공개 API
# @MX:SPEC: SPEC-LOTTO-030
@router.get("/numbers/{number}/stats")
async def get_number_statistics(
    number: int = FastAPIPath(..., ge=1, le=45, description="조회할 번호 (1~45)"),
) -> dict[str, Any]:
    """특정 번호의 출현 이력과 상세 통계를 반환합니다 (SPEC-LOTTO-030).

    - number: 1~45. FastAPI Path 검증으로 범위 초과 시 422.
    - 데이터 부재 시에도 200 으로 정상 응답 (카운트 0, 빈 리스트, nulls).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.number_stats(number, wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-043 — 연속 번호 패턴 분석 공개 API
# @MX:SPEC: SPEC-LOTTO-043 REQ-CONSEC-014
@router.get("/patterns/consecutive")
async def get_consecutive_pattern(
    recent_n: Optional[int] = Query(  # noqa: UP045 — FastAPI는 Python 3.9에서 Optional 필요
        default=None,
        ge=1,
        le=2000,
        description="분석 대상 최신 회차 수 (미지정 시 전체, 1~2000)",
    ),
) -> dict[str, Any]:
    """역대 당첨번호의 연속 번호 패턴 통계를 반환합니다 (SPEC-LOTTO-043).

    - recent_n: 미지정 시 전체, 지정 시 최신 N회차(1~2000). 범위 초과 시 422.
    - 데이터 부재 시에도 200 으로 정상 응답 (빈 구조).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.consecutive_pattern(wd.get_draws(), recent_n=recent_n)


# @MX:NOTE: [AUTO] SPEC-LOTTO-044 — 번호 궁합 추천기 공개 API
# @MX:SPEC: SPEC-LOTTO-044 REQ-AFFINITY-010
@router.get("/numbers/affinity")
async def get_number_affinity(
    target: int = Query(..., ge=1, le=45, description="궁합을 분석할 번호 (1~45)"),
    top_k: int = Query(
        default=10,
        ge=1,
        le=44,
        description="반환할 상위 파트너 수 (1~44, 기본 10)",
    ),
) -> dict[str, Any]:
    """대상 번호와 동반 출현한 파트너 궁합 + 추천 조합을 반환합니다 (SPEC-LOTTO-044).

    - target: 1~45. FastAPI Query 검증으로 누락/범위 초과 시 422.
    - top_k: 1~44. 범위 초과 시 422.
    - 데이터 부재 시에도 200 으로 정상 응답 (빈 구조).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.number_affinity(target, wd.get_draws(), top_k=top_k)


# @MX:NOTE: [AUTO] SPEC-LOTTO-053 — 번호 동시 출현 분석 API (number 유/무 분기)
# @MX:SPEC: SPEC-LOTTO-053 REQ-CO-009, REQ-CO-010
@router.get("/numbers/cooccurrence")
async def get_cooccurrence(
    number: Optional[int] = Query(  # noqa: UP045 — FastAPI는 Python 3.9에서 Optional 필요
        default=None, ge=1, le=45, description="동반 파트너를 조회할 번호 (1~45)"
    ),
    top: int = Query(
        default=20, ge=1, le=100,
        description="반환할 상위 쌍/파트너 수 (1~100, 기본 20)",
    ),
) -> dict[str, Any]:
    """번호 동시 출현 분석 결과를 반환합니다 (SPEC-LOTTO-053).

    - number 지정(1~45): 해당 번호의 상위 top 동반 파트너 (REQ-CO-009).
    - number 없음: 전체 상위 top 동시 출현 쌍 (REQ-CO-010, 기본 top=20).
    - 데이터 부재 시에도 200 으로 정상 응답 (빈 목록).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    draws = wd.get_draws()
    if number is not None:
        return {
            "number": number,
            "partners": wd.get_number_partners(draws, number, top_k=top),
        }
    return {"pairs": wd.get_top_cooccurrences(draws, n=top)}


@router.get("/simulation")
async def run_simulation_results(
    rounds: int = Query(default=1000, ge=1, le=100000, description="시뮬레이션 회차 수 (1~100000)"),
) -> dict[str, Any]:
    """인과 안전 백테스팅 시뮬레이션 결과를 반환합니다. 파일 없으면 503."""
    result = get_simulation(rounds=rounds)
    if result is None:
        raise HTTPException(
            503,
            detail={"error": "data_unavailable", "message": "데이터가 없습니다."},
        )
    return result.model_dump()


# @MX:NOTE: [AUTO] SPEC-LOTTO-032 REQ-CMP-001 — 전략별 백테스트 비교 공개 API
# @MX:SPEC: SPEC-LOTTO-032
@router.get("/simulation/compare")
async def compare_strategies(
    rounds: int = Query(default=100, ge=10, le=500, description="비교 대상 최근 회차 수 (10~500)"),
) -> dict[str, Any]:
    """8가지 추천 전략을 동일 기간에 백테스트하여 성과를 비교합니다 (REQ-CMP-001).

    - rounds: 10~500. 범위 초과 시 422.
    - 데이터/통계 부재 시에도 200 으로 정상 응답 (빈 strategies 리스트).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.strategy_compare(rounds, wd.get_draws(), wd.get_stats())


# SPEC-LOTTO-005 REQ-PDF-001: PDF 리포트 다운로드 엔드포인트
@router.get("/report/pdf")
async def download_pdf_report() -> Response:
    """추천/통계/시뮬레이션 결과를 단일 PDF로 다운로드합니다.

    데이터가 부재해도 빈 섹션 표시로 정상 PDF를 반환합니다 (REQ-PDF-006).
    """
    from lotto.pdf_report import generate_report

    stats = get_stats()
    recs = get_recommendations()
    sim = get_simulation()
    pdf_bytes = generate_report(stats=stats, recommendations=recs, simulation=sim)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=lotto_report.pdf",
        },
    )


# ─── SPEC-LOTTO-020: 데이터 내보내기 (CSV/JSON) ────────────────────────────

# @MX:NOTE: [AUTO] 추첨/구매이력 데이터를 외부 도구(Excel 등)로 내보내는 다운로드 엔드포인트
# @MX:SPEC: SPEC-LOTTO-020 REQ-EXP-001~003

_DRAWS_CSV_COLUMNS: list[str] = [
    "drwNo", "date", "n1", "n2", "n3", "n4", "n5", "n6", "bonus",
]
_HISTORY_CSV_COLUMNS: list[str] = [
    "id", "purchase_date", "numbers", "draw_no", "prize_rank", "prize_amount",
]


def _today_yyyymmdd() -> str:
    """오늘 날짜를 YYYYMMDD 형식으로 반환합니다."""
    return datetime.date.today().strftime("%Y%m%d")


def _draws_csv_iter(draws: list[Any]) -> Iterator[str]:
    """추첨 데이터를 CSV 행 단위로 yield 하는 제너레이터."""
    import csv

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_DRAWS_CSV_COLUMNS)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for d in draws:
        writer.writerow([
            d.drwNo, str(d.date),
            d.n1, d.n2, d.n3, d.n4, d.n5, d.n6, d.bonus,
        ])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


@router.get("/export/draws")
async def export_draws_csv(
    from_drw: Optional[int] = Query(  # noqa: UP045
        default=None, ge=1, description="시작 회차 (포함, >=1)"
    ),
    to_drw: Optional[int] = Query(  # noqa: UP045
        default=None, ge=1, description="끝 회차 (포함, >=1)"
    ),
) -> StreamingResponse:
    """추첨 데이터를 CSV 파일로 내보냅니다 (SPEC-LOTTO-020 REQ-EXP-001).

    - 컬럼: drwNo, date, n1~n6, bonus
    - 파일명: lotto_draws_YYYYMMDD.csv (today)
    - 데이터 없어도 200 + 헤더만 있는 CSV 반환
    - from_drw/to_drw 로 회차 범위 필터링
    """
    draws = get_draws() or []
    if from_drw is not None:
        draws = [d for d in draws if d.drwNo >= from_drw]
    if to_drw is not None:
        draws = [d for d in draws if d.drwNo <= to_drw]

    filename = f"lotto_draws_{_today_yyyymmdd()}.csv"
    return StreamingResponse(
        _draws_csv_iter(draws),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_history_rows(tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """티켓 목록을 export용 행 dict 리스트로 변환합니다.

    당첨 결과(prize_rank, prize_amount)는 compute_ticket_results 와 동일한
    purchase 계산을 사용한다.
    """
    from lotto.purchase import calc_prize

    draws = get_draws() or []
    draw_map = {d.drwNo: d for d in draws}

    rows: list[dict[str, Any]] = []
    for t in tickets:
        drw_no = t.get("drwNo", 0)
        draw = draw_map.get(drw_no)
        rank, amount, _matched, _bonus = calc_prize(t.get("numbers", []), draw)
        rows.append({
            "id": t.get("id", ""),
            "purchase_date": t.get("bought_at", ""),
            "numbers": ",".join(str(n) for n in t.get("numbers", [])),
            "draw_no": drw_no,
            "prize_rank": rank,
            "prize_amount": amount,
        })
    return rows


def _history_csv_iter(rows: list[dict[str, Any]]) -> Iterator[str]:
    """구매 이력 행을 CSV 단위로 yield 한다."""
    import csv

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_HISTORY_CSV_COLUMNS)
    writer.writeheader()
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for row in rows:
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


@router.get("/export/history")
async def export_history(
    format: str = Query(  # noqa: A002
        default="csv", description="내보내기 형식 (csv 또는 json)",
    ),
) -> Response:
    """구매 이력을 CSV 또는 JSON 으로 내보냅니다 (REQ-EXP-002, REQ-EXP-003).

    - 기본 format=csv: text/csv 다운로드
    - format=json: application/json 다운로드
    - 파일명: lotto_history_YYYYMMDD.(csv|json)
    - 이력이 없어도 200 + 빈 CSV(헤더만) 또는 빈 JSON 배열 반환
    """
    import json as _json

    tickets = get_history()
    rows = _build_history_rows(tickets)
    date_suffix = _today_yyyymmdd()

    if format.lower() == "json":
        filename = f"lotto_history_{date_suffix}.json"
        return Response(
            content=_json.dumps(rows, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    filename = f"lotto_history_{date_suffix}.csv"
    return StreamingResponse(
        _history_csv_iter(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _run_analyze_sync() -> None:
    """수집 데이터 기반 통계 분석을 동기 실행합니다.

    SPEC-LOTTO-009 REQ-CACHE-003: 분석 완료 후 캐시를 무효화하여
    다음 요청부터 최신 stats.json을 다시 로드하도록 한다.
    """
    from lotto.analyzer import LottoAnalyzer
    from lotto.collector import LottoCollector

    draws = LottoCollector().load_existing()
    if draws:
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze(draws)
        analyzer.save_stats(stats, Path("data/stats.json"))
    invalidate_cache()


def _estimate_latest_drw_no() -> int:
    """현재 날짜 기준 최신 회차 번호를 추정합니다. (1회: 2002-12-07 토요일)"""
    origin = datetime.date(2002, 12, 7)
    today = datetime.date.today()
    weeks = (today - origin).days // 7
    return max(1, weeks + 1)


# SPEC-LOTTO-002: 체크포인트 간격 외부화 — LOTTO_CHECKPOINT_INTERVAL 환경 변수로 오버라이드
_CHECKPOINT_INTERVAL = settings.checkpoint_interval  # N회마다 중간 저장


def _collect_worker(full: bool, start_from: int, max_drw_no: int) -> None:
    """백그라운드 수집 워커 — 진행 상태를 _collect_state에 기록합니다.

    # @MX:NOTE: [AUTO] 20회마다 중간 저장 — 실패 시 증분 재시작으로 이어서 수집 가능
    """
    import time

    from lotto.collector import LottoCollector
    from lotto.models import DrawResult  # noqa: TC001

    global _collect_state  # noqa: PLW0603

    collector = LottoCollector()

    # 빈 CSV 처리
    csv_path = Path("data/draws.csv")
    if csv_path.exists() and csv_path.stat().st_size < 10:
        csv_path.unlink()

    existing = collector.load_existing() if not full else []
    existing_set = {d.drwNo for d in existing}
    targets = [n for n in range(start_from, max_drw_no + 1) if n not in existing_set]

    with _collect_lock:
        _collect_state.update({
            "status": "running", "current": 0, "total": len(targets),
            "collected": 0, "message": "수집 중...",
        })

    collected: list[DrawResult] = list(existing)
    consecutive_failures = 0
    new_since_checkpoint = 0

    for idx, drw_no in enumerate(targets, 1):
        with _collect_lock:
            _collect_state["current"] = idx
            _collect_state["message"] = f"{drw_no}회차 수집 중..."

        draw = collector.fetch_draw(drw_no)
        time.sleep(0.2)

        if draw is None:
            consecutive_failures += 1
            if consecutive_failures >= 5:
                # 5회 연속 실패 = 더 이상 데이터 없음 (최신 회차 도달)
                break
        else:
            consecutive_failures = 0
            collected.append(draw)
            new_since_checkpoint += 1
            with _collect_lock:
                _collect_state["collected"] += 1

            # 주기적 중간 저장 — 실패 시 이 시점부터 증분 재시작 가능
            if new_since_checkpoint >= _CHECKPOINT_INTERVAL:
                try:
                    collector.save_csv(sorted(collected, key=lambda d: d.drwNo))
                    new_since_checkpoint = 0
                    with _collect_lock:
                        saved_count = len(collected)
                        _collect_state["message"] = (
                            f"{drw_no}회차 수집 중... (체크포인트 저장: {saved_count}회차)"
                        )
                except Exception as exc:  # noqa: BLE001
                    # SPEC-LOTTO-002 REQ-ERR-003: 체크포인트 저장 실패를 무음으로 삼키지 않음.
                    # 수집 작업 자체는 중단하지 않고 다음 체크포인트까지 계속 진행.
                    logger.warning(
                        "Checkpoint save failed at round %d: %s",
                        drw_no, exc, exc_info=True,
                    )

    if not collected:
        with _collect_lock:
            _collect_state.update({
                "status": "error",
                "message": (
                    "API에서 데이터를 가져올 수 없습니다. 블로그 크롤링 기능을 사용해보세요."
                ),
            })
        # SPEC-LOTTO-009 REQ-CACHE-003: 워커 종료 시점에 캐시 무효화 (안전 측면)
        invalidate_cache()
        return

    try:
        sorted_draws = sorted(collected, key=lambda d: d.drwNo)
        collector.save_csv(sorted_draws)
        total_saved = len(sorted_draws)
        with _collect_lock:
            _collect_state.update({
                "status": "running",
                "message": "통계 분석 중...",
                "total": total_saved,
            })
        _run_analyze_sync()
        with _collect_lock:
            _collect_state.update({
                "status": "done",
                "message": f"수집 완료 — 총 {total_saved}회차 저장, 통계 분석 완료",
                "total": total_saved,
            })
    except Exception as exc:
        with _collect_lock:
            _collect_state.update({"status": "error", "message": f"저장 실패: {exc}"})
    # SPEC-LOTTO-009 REQ-CACHE-003: 성공·실패 모두 캐시 무효화로 최신성 보장
    invalidate_cache()


@router.get("/collect/status")
async def collect_status() -> dict[str, Any]:
    """데이터 수집 진행 상태(idle/running/done/error)와 진행률을 반환합니다."""
    with _collect_lock:
        return dict(_collect_state)


# @MX:NOTE: [AUTO] SPEC-LOTTO-031 — 수집 현황 요약 + 누락 회차 감지 공개 API
# @MX:SPEC: SPEC-LOTTO-031
@router.get("/collect/summary")
async def collect_summary_endpoint() -> dict[str, Any]:
    """데이터 수집 현황 요약을 반환합니다 (SPEC-LOTTO-031).

    데이터 부재 시에도 200 으로 정상 응답 (zeros + 빈 리스트).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.collect_summary(wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-022 REQ-PRIZE-C-002 — 1등 당첨금 소급 업데이트 백그라운드 워커
def _update_prizes_worker() -> None:
    """기존 데이터의 prize1Amount=None 행만 API 재요청하여 업데이트한다.

    진행 상태를 _collect_state에 기록하여 /api/collect/status로 폴링 가능.
    """
    from lotto.collector import LottoCollector

    global _collect_state  # noqa: PLW0603

    collector = LottoCollector()

    # 누락 행 카운트
    existing = collector.load_existing()
    missing_count = sum(1 for d in existing if d.prize1Amount is None)

    with _collect_lock:
        _collect_state.update({
            "status": "running",
            "current": 0,
            "total": missing_count,
            "collected": 0,
            "message": "1등 당첨금 업데이트 중...",
        })

    if missing_count == 0:
        with _collect_lock:
            _collect_state.update({
                "status": "done",
                "message": "업데이트할 누락 회차가 없습니다.",
            })
        invalidate_cache()
        return

    def _on_progress(current: int, total: int, drw_no: int) -> None:
        with _collect_lock:
            _collect_state["current"] = current
            _collect_state["message"] = f"{drw_no}회차 당첨금 업데이트 중..."

    try:
        updated = collector.update_prizes(on_progress=_on_progress)
        with _collect_lock:
            _collect_state.update({
                "status": "done",
                "collected": updated,
                "message": f"1등 당첨금 업데이트 완료 — {updated}회차 갱신",
            })
    except Exception as exc:  # noqa: BLE001
        with _collect_lock:
            _collect_state.update({
                "status": "error",
                "message": f"당첨금 업데이트 실패: {exc}",
            })
        # SPEC-LOTTO-002 REQ-ERR-002: 실패는 로그에 흔적을 남김
        logger.warning("Prize update worker failed: %s", exc, exc_info=True)
    # SPEC-LOTTO-009 REQ-CACHE-003: 성공·실패 모두 캐시 무효화로 최신성 보장
    invalidate_cache()


@router.post("/collect", status_code=202)
async def trigger_collect(
    background_tasks: BackgroundTasks,
    full: bool = Query(default=False, description="True면 전체 재수집"),
    count: int = Query(default=0, ge=0, description="최근 N회 수집 (0=증분, full=True면 무시)"),
    update_prizes: bool = Query(  # noqa: FBT001 — FastAPI Query 패턴
        default=False,
        description="True면 기존 데이터의 1등 당첨금만 소급 업데이트 (SPEC-LOTTO-022)",
    ),
) -> dict[str, Any]:
    """데이터 수집을 백그라운드에서 시작합니다.
    - update_prizes=true: 기존 회차 중 prize1Amount=None 행만 재요청
    - full=true: 1회차부터 전체 재수집
    - count>0: 최근 N회차 수집
    - 기본: 마지막 저장 회차 이후 증분 수집
    """
    with _collect_lock:
        if _collect_state["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail={"error": "already_running", "message": "이미 수집이 진행 중입니다."},
            )

    csv_path = Path("data/draws.csv")
    if csv_path.exists() and csv_path.stat().st_size < 10:
        csv_path.unlink()

    # SPEC-LOTTO-022 REQ-PRIZE-C-002: update_prizes 최우선 분기
    if update_prizes:
        background_tasks.add_task(_update_prizes_worker)
        return {
            "status": "started",
            "message": "1등 당첨금 소급 업데이트를 시작했습니다.",
        }

    from lotto.collector import LottoCollector

    max_drw_no = _estimate_latest_drw_no()

    if full:
        start_from = 1
        mode = "전체"
    elif count > 0:
        start_from = max(1, max_drw_no - count + 1)
        mode = f"최근 {count}회"
    else:
        existing = LottoCollector().load_existing()
        start_from = (max(d.drwNo for d in existing) + 1) if existing else 1
        mode = "증분"

    background_tasks.add_task(_collect_worker, full, start_from, max_drw_no)
    return {
        "status": "started",
        "message": f"{mode} 수집을 시작했습니다.",
        "start_from": start_from,
        "max_drw_no": max_drw_no,
    }


class ManualDrawRequest(BaseModel):
    """수동 회차 입력 요청 모델."""

    drwNo: int  # noqa: N815
    date: str
    numbers: list[int]
    bonus: int

    @field_validator("drwNo")
    @classmethod
    def validate_drw_no(cls, v: int) -> int:
        if v < 1:
            raise ValueError("회차 번호는 1 이상이어야 합니다.")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if len(v) != 8 or not v.isdigit():  # noqa: PLR2004
            raise ValueError("날짜는 8자리 숫자(YYYYMMDD)여야 합니다.")
        try:
            datetime.datetime.strptime(v, "%Y%m%d")
        except ValueError as err:
            raise ValueError("날짜 형식이 올바르지 않습니다. (YYYYMMDD)") from err
        return v

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        if len(v) != 6:
            raise ValueError("번호는 정확히 6개여야 합니다.")
        if len(set(v)) != 6:
            raise ValueError("번호에 중복이 있습니다.")
        for n in v:
            if not (1 <= n <= 45):
                raise ValueError(f"번호 {n}은 1~45 범위를 벗어납니다.")
        return sorted(v)

    @field_validator("bonus")
    @classmethod
    def validate_bonus(cls, v: int) -> int:
        if not (1 <= v <= 45):
            raise ValueError(f"보너스 번호 {v}은 1~45 범위를 벗어납니다.")
        return v

    @model_validator(mode="after")
    def bonus_not_in_numbers(self) -> ManualDrawRequest:
        if self.bonus in self.numbers:
            raise ValueError("보너스 번호가 당첨 번호와 중복됩니다.")
        return self


@router.post("/draws/manual", status_code=201)
async def add_manual_draw(req: ManualDrawRequest) -> dict[str, Any]:
    """회차 데이터를 수동으로 추가합니다. 중복 회차는 409를 반환합니다."""

    from lotto.collector import LottoCollector
    from lotto.models import DrawResult

    collector = LottoCollector()

    # 빈 CSV 파일은 미리 제거하여 pandas EmptyDataError 방지
    csv_path = Path("data/draws.csv")
    if csv_path.exists() and csv_path.stat().st_size < 10:
        csv_path.unlink()

    existing = collector.load_existing()

    if any(d.drwNo == req.drwNo for d in existing):
        raise HTTPException(
            status_code=409,
            detail={"error": "duplicate", "message": f"{req.drwNo}회차는 이미 존재합니다."},
        )

    new_draw = DrawResult(
        drwNo=req.drwNo,
        date=datetime.datetime.strptime(req.date, "%Y%m%d").date(),
        n1=req.numbers[0],
        n2=req.numbers[1],
        n3=req.numbers[2],
        n4=req.numbers[3],
        n5=req.numbers[4],
        n6=req.numbers[5],
        bonus=req.bonus,
    )

    all_draws = sorted(existing + [new_draw], key=lambda d: d.drwNo)
    collector.save_csv(all_draws)
    return {
        "status": "ok",
        "message": f"{req.drwNo}회차 데이터가 저장되었습니다.",
        "total": len(all_draws),
    }


@router.delete("/draws/{drw_no}", status_code=200)
async def delete_draw(drw_no: int) -> dict[str, Any]:
    """지정한 회차 데이터를 삭제합니다. 존재하지 않으면 404를 반환합니다."""

    from lotto.collector import LottoCollector

    collector = LottoCollector()
    existing = collector.load_existing()
    filtered = [d for d in existing if d.drwNo != drw_no]

    if len(filtered) == len(existing):
        raise HTTPException(status_code=404, detail=f"{drw_no}회차를 찾을 수 없습니다.")

    collector.save_csv(filtered)
    invalidate_cache()
    return {"status": "ok", "message": f"{drw_no}회차가 삭제되었습니다.", "total": len(filtered)}


# ─── SPEC-LOTTO-016: 번호 즐겨찾기 (favorites) ──────────────────────────────


class FavoriteRequest(BaseModel):
    """즐겨찾기 추가 요청 모델 (REQ-FAV-001).

    - numbers: 1~45 범위의 중복 없는 6개 정수 (정렬 후 저장)
    - name: 선택, 최대 20자. 생략 시 서버에서 "번호조합 N" 자동 부여
    """

    numbers: list[int]
    name: Optional[str] = None  # noqa: UP045 — Pydantic + Python 3.9 호환

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        if len(v) != 6:  # noqa: PLR2004
            raise ValueError("번호는 정확히 6개여야 합니다.")
        if len(set(v)) != 6:  # noqa: PLR2004
            raise ValueError("번호에 중복이 있습니다.")
        for n in v:
            if not (1 <= n <= 45):  # noqa: PLR2004
                raise ValueError(f"번호 {n}은 1~45 범위를 벗어납니다.")
        return sorted(v)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:  # noqa: UP045
        if v is None:
            return None
        # 최대 20자 (인수 기준)
        if len(v) > 20:  # noqa: PLR2004
            raise ValueError("이름은 최대 20자여야 합니다.")
        return v


def _next_auto_name(favorites: list[dict[str, Any]]) -> str:
    """기존 '번호조합 N' 형식 이름을 보고 다음 자동 이름을 결정한다.

    사용자 지정 이름이 섞여 있어도 자동 카운터만 단조 증가하도록 한다.
    """
    prefix = "번호조합 "
    max_n = 0
    for fav in favorites:
        name = fav.get("name", "")
        if isinstance(name, str) and name.startswith(prefix):
            tail = name[len(prefix):]
            if tail.isdigit():
                try:
                    n = int(tail)
                except ValueError:
                    continue
                if n > max_n:
                    max_n = n
    return f"{prefix}{max_n + 1}"


@router.post("/favorites", status_code=201)
async def add_favorite(req: FavoriteRequest) -> dict[str, Any]:
    """번호 조합을 즐겨찾기에 추가합니다 (REQ-FAV-001).

    - 동일 번호 집합(순서 무관)이 이미 존재하면 409를 반환한다.
    - 이름이 생략되면 "번호조합 N" 형식으로 자동 부여한다.
    """
    import uuid

    favorites = get_favorites()

    # 중복 검사 (순서 무관 — set 비교)
    req_set = set(req.numbers)
    for fav in favorites:
        existing_nums = fav.get("numbers", [])
        if isinstance(existing_nums, list) and set(existing_nums) == req_set:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "duplicate",
                    "message": "동일한 번호 조합이 이미 존재합니다.",
                },
            )

    name = req.name if req.name else _next_auto_name(favorites)
    favorite = {
        "id": str(uuid.uuid4()),
        "name": name,
        "numbers": req.numbers,  # validator에서 정렬 보장
    }
    favorites.append(favorite)
    save_favorites(favorites)
    # SPEC-LOTTO-009 REQ-CACHE-003: 다른 데이터 무효화 패턴 일관성 유지
    invalidate_cache()
    return favorite


@router.get("/favorites")
async def list_favorites() -> list[dict[str, Any]]:
    """저장된 즐겨찾기를 저장 순서대로 반환합니다 (REQ-FAV-002)."""
    return get_favorites()


@router.delete("/favorites/{fav_id}", status_code=200)
async def delete_favorite(fav_id: str) -> dict[str, Any]:
    """지정한 ID의 즐겨찾기를 삭제합니다 (REQ-FAV-003).

    존재하지 않는 ID면 404를 반환한다.
    """
    favorites = get_favorites()
    new_favorites = [fav for fav in favorites if fav.get("id") != fav_id]
    if len(new_favorites) == len(favorites):
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "즐겨찾기를 찾을 수 없습니다."},
        )
    save_favorites(new_favorites)
    invalidate_cache()
    return {"status": "ok"}


# ─── SPEC-LOTTO-048: 시뮬레이션 결과 저장/비교 (sim_history) ──────────────────


class SimHistoryRequest(BaseModel):
    """시뮬레이션 결과 저장 요청 모델 (SPEC-LOTTO-048).

    - label: 필수, 1~50자(공백 trim 후 비어 있으면 거부).
    - strategy / numbers / iterations / rank_counts: 시뮬레이션 결과 본문.
    - total_spent / total_won / roi: 선택(예산 분석 결과).
    """

    label: str
    strategy: str = "random"
    numbers: List[int] = []  # noqa: UP006 — Pydantic + Python 3.9 호환
    iterations: int = 0
    rank_counts: Dict[str, int] = {}  # noqa: UP006 — Pydantic + Python 3.9 호환
    total_spent: Optional[int] = None  # noqa: UP045 — Pydantic + Python 3.9 호환
    total_won: Optional[int] = None  # noqa: UP045
    roi: Optional[float] = None  # noqa: UP045

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("라벨은 비어 있을 수 없습니다.")
        if len(stripped) > 50:  # noqa: PLR2004
            raise ValueError("라벨은 최대 50자여야 합니다.")
        return stripped


# @MX:NOTE: [AUTO] SPEC-LOTTO-048 — 시뮬레이션 결과 저장 API
# @MX:SPEC: SPEC-LOTTO-048
@router.post("/simulation-history", status_code=200)
async def add_simulation_history(req: SimHistoryRequest) -> dict[str, Any]:
    """시뮬레이션 결과를 라벨과 함께 저장합니다 (SPEC-LOTTO-048).

    빈 라벨은 Pydantic 검증 단계에서 422로 거부된다.
    """
    entry: dict[str, Any] = {
        "label": req.label,
        "strategy": req.strategy,
        "numbers": req.numbers,
        "iterations": req.iterations,
        "rank_counts": req.rank_counts,
        "total_spent": req.total_spent,
        "total_won": req.total_won,
        "roi": req.roi,
    }
    return save_simulation_result(entry)


# @MX:NOTE: [AUTO] SPEC-LOTTO-048 — 저장된 시뮬레이션 결과 목록 조회 API
# @MX:SPEC: SPEC-LOTTO-048
@router.get("/simulation-history")
async def list_simulation_history() -> list[dict[str, Any]]:
    """저장된 시뮬레이션 결과를 최신순으로 반환합니다 (SPEC-LOTTO-048)."""
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.list_simulation_results()


# @MX:NOTE: [AUTO] SPEC-LOTTO-048 — 저장된 시뮬레이션 결과 삭제 API
# @MX:SPEC: SPEC-LOTTO-048
@router.delete("/simulation-history/{result_id}", status_code=200)
async def delete_simulation_history(result_id: str) -> dict[str, Any]:
    """지정한 id의 저장된 시뮬레이션 결과를 삭제합니다 (SPEC-LOTTO-048).

    존재하지 않는 id면 404를 반환한다.
    """
    from lotto.web import data as wd

    if not wd.delete_simulation_result(result_id):
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "저장된 시뮬레이션 결과를 찾을 수 없습니다."},
        )
    return {"deleted": True}


# ─── SPEC-LOTTO-036: 번호 메모 (number_notes) ───────────────────────────────


class NoteRequest(BaseModel):
    """번호 메모 저장 요청 모델 (SPEC-LOTTO-036).

    note가 빈 문자열이면 해당 번호 메모를 삭제 처리한다.
    """

    note: str = ""


# @MX:NOTE: [AUTO] SPEC-LOTTO-036 — 번호 메모 저장/삭제 API
# @MX:SPEC: SPEC-LOTTO-036
@router.post("/numbers/{number}/note")
async def save_number_note(
    req: NoteRequest,
    number: int = FastAPIPath(..., ge=1, le=45, description="메모를 달 번호 (1~45)"),
) -> dict[str, Any]:
    """특정 번호(1~45)에 메모를 저장합니다 (SPEC-LOTTO-036).

    - number: 1~45. 범위 초과 시 FastAPI Path 검증으로 422.
    - note가 빈 문자열이면 해당 번호 메모를 삭제하고 updated_at=None을 반환한다.
    - note가 있으면 저장 후 갱신된 updated_at(ISO-8601)을 반환한다.
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    notes = wd.get_number_notes()
    key = str(number)
    stripped = req.note.strip()

    if stripped == "":
        # 빈 문자열 → 삭제 처리 (없으면 무동작)
        notes.pop(key, None)
        wd.save_number_notes(notes)
        return {"number": number, "note": "", "updated_at": None}

    # SPEC-LOTTO-036: UTC ISO-8601 (Python 3.9 호환)
    updated_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()  # noqa: UP017
    notes[key] = {"note": stripped, "updated_at": updated_at}
    wd.save_number_notes(notes)
    return {"number": number, "note": stripped, "updated_at": updated_at}


@router.get("/numbers/notes")
async def list_number_notes() -> dict[str, Any]:
    """메모가 등록된 번호 전체를 번호 오름차순으로 반환합니다 (SPEC-LOTTO-036).

    Response: {"total": N, "items": [{"number", "note", "updated_at"}, ...]}
    """
    from lotto.web import data as wd

    notes = wd.get_number_notes()
    items: list[dict[str, Any]] = []
    for key, value in notes.items():
        if not isinstance(value, dict):
            continue
        try:
            num = int(key)
        except ValueError:
            continue
        items.append({
            "number": num,
            "note": value.get("note", ""),
            "updated_at": value.get("updated_at"),
        })
    # 번호 오름차순 정렬
    items.sort(key=lambda i: i["number"])
    return {"total": len(items), "items": items}


@router.get("/numbers/{number}/note")
async def get_number_note(
    number: int = FastAPIPath(..., ge=1, le=45, description="조회할 번호 (1~45)"),
) -> dict[str, Any]:
    """특정 번호의 메모를 조회합니다 (SPEC-LOTTO-036).

    - number: 1~45. 범위 초과 시 422.
    - 메모가 없으면 note="", updated_at=None 으로 정상 응답(200)한다.
    """
    from lotto.web import data as wd

    notes = wd.get_number_notes()
    entry = notes.get(str(number))
    if not isinstance(entry, dict):
        return {"number": number, "note": "", "updated_at": None}
    return {
        "number": number,
        "note": entry.get("note", ""),
        "updated_at": entry.get("updated_at"),
    }


# ─── SPEC-LOTTO-037: 고급 필터 추천 (filtered recommend) ─────────────────────

# SPEC-LOTTO-037: 조합 생성 기본값 / 한계
_FILTER_SUM_MIN = 21       # 1+2+3+4+5+6
_FILTER_SUM_MAX = 255      # 40+41+42+43+44+45
_FILTER_ODD_MIN = 0
_FILTER_ODD_MAX = 6
_FILTER_MAX_INCLUDE = 6
_FILTER_MAX_ATTEMPTS = 1000


class FilteredRecommendRequest(BaseModel):
    """고급 필터 추천 요청 모델 (SPEC-LOTTO-037).

    모든 필드는 선택 사항이며, 생략 시 합 21~255 / 홀수 0~6 / 포함·제외 빈 리스트 /
    count=5 기본값이 적용된다.
    """

    sum_min: int = _FILTER_SUM_MIN
    sum_max: int = _FILTER_SUM_MAX
    odd_min: int = _FILTER_ODD_MIN
    odd_max: int = _FILTER_ODD_MAX
    include_numbers: list[int] = []  # noqa: RUF012 — Pydantic 기본 빈 리스트는 인스턴스별 복제됨
    exclude_numbers: list[int] = []  # noqa: RUF012
    count: int = 5

    @field_validator("include_numbers", "exclude_numbers")
    @classmethod
    def validate_number_range(cls, v: list[int]) -> list[int]:
        for n in v:
            if not (1 <= n <= 45):  # noqa: PLR2004
                raise ValueError(f"번호 {n}은 1~45 범위를 벗어납니다.")
        return v

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        if not (1 <= v <= 20):  # noqa: PLR2004
            raise ValueError("count는 1~20 범위여야 합니다.")
        return v

    @model_validator(mode="after")
    def validate_constraints(self) -> FilteredRecommendRequest:
        if self.sum_min > self.sum_max:
            raise ValueError("sum_min은 sum_max보다 클 수 없습니다.")
        if self.odd_min > self.odd_max:
            raise ValueError("odd_min은 odd_max보다 클 수 없습니다.")
        if len(self.include_numbers) > _FILTER_MAX_INCLUDE:
            raise ValueError("include_numbers는 최대 6개입니다.")
        if set(self.include_numbers) & set(self.exclude_numbers):
            raise ValueError("include_numbers와 exclude_numbers에 중복 번호가 있습니다.")
        return self


def _generate_filtered_combinations(req: FilteredRecommendRequest) -> list[list[int]]:
    """조건에 맞는 번호 조합을 최대 count개 생성합니다 (SPEC-LOTTO-037).

    알고리즘:
    1. include_numbers를 고정으로 두고, 나머지 슬롯(6 - len(include))을
       (1~45) - (include ∪ exclude) 풀에서 무작위로 채운다.
    2. 정렬 후 합계/홀수 개수 제약을 검사하고, 통과하면 채택한다.
    3. 최대 1000회 시도해도 채우지 못하면 현재까지의 결과만 반환한다(빈 리스트 가능).

    동일 조합 중복은 허용하지 않는다(set로 추적).
    """
    import random

    include = sorted(set(req.include_numbers))
    exclude = set(req.exclude_numbers)
    remaining_slots = 6 - len(include)
    # 채울 후보 풀 — include/exclude 제외
    pool = [n for n in range(1, 46) if n not in exclude and n not in include]

    combinations: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()

    # 슬롯을 채울 수 없으면(풀 부족) 즉시 빈 결과
    if remaining_slots < 0 or len(pool) < remaining_slots:
        return []

    attempts = 0
    while len(combinations) < req.count and attempts < _FILTER_MAX_ATTEMPTS:
        attempts += 1
        picked = random.sample(pool, remaining_slots) if remaining_slots > 0 else []
        combo = sorted(include + picked)
        key = tuple(combo)
        if key in seen:
            continue
        total = sum(combo)
        odd = sum(1 for n in combo if n % 2 == 1)
        if not (req.sum_min <= total <= req.sum_max):
            continue
        if not (req.odd_min <= odd <= req.odd_max):
            continue
        seen.add(key)
        combinations.append(combo)

    return combinations


# @MX:NOTE: [AUTO] SPEC-LOTTO-037 — 조건 기반 번호 추천 공개 API
# @MX:SPEC: SPEC-LOTTO-037
@router.post("/recommend/filtered")
async def recommend_filtered(req: FilteredRecommendRequest) -> dict[str, Any]:
    """사용자 지정 조건에 맞는 번호 조합을 추천합니다 (SPEC-LOTTO-037).

    검증 실패(합/홀수 범위 역전, include·exclude 중복, include 6개 초과, count 범위)는
    Pydantic 검증에서 422로 반환된다. 조건을 만족하는 조합을 못 찾으면 빈 리스트를 반환한다.

    Response: {"count": N, "combinations": [[3,7,14,22,35,42], ...]}
    """
    combinations = _generate_filtered_combinations(req)
    return {"count": len(combinations), "combinations": combinations}


# ─── SPEC-LOTTO-035: 번호 예약 (reservations) ────────────────────────────────

# SPEC-LOTTO-035: 최대 예약 개수 (data._RESERVATIONS_MAX와 동일 정책)
_RESERVATIONS_MAX_API = 10


class ReservationRequest(BaseModel):
    """번호 예약 추가 요청 모델 (SPEC-LOTTO-035).

    - numbers: 1~45 범위의 중복 없는 6개 정수 (정렬 후 저장)
    - note: 선택 메모. 생략 시 빈 문자열로 저장된다.
    """

    numbers: list[int]
    note: str = ""

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        if len(v) != 6:  # noqa: PLR2004
            raise ValueError("번호는 정확히 6개여야 합니다.")
        if len(set(v)) != 6:  # noqa: PLR2004
            raise ValueError("번호에 중복이 있습니다.")
        for n in v:
            if not (1 <= n <= 45):  # noqa: PLR2004
                raise ValueError(f"번호 {n}은 1~45 범위를 벗어납니다.")
        return sorted(v)


@router.post("/reservations", status_code=201)
async def add_reservation(req: ReservationRequest) -> dict[str, Any]:
    """다음 추첨에 구매할 번호 조합을 예약합니다 (SPEC-LOTTO-035).

    - 최대 10개까지 예약 가능하며, 초과 시 HTTP 400을 반환한다.
    - id는 8자리 hex, created_at은 UTC ISO-8601 문자열이다.
    """
    import uuid

    reservations = get_reservations()
    if len(reservations) >= _RESERVATIONS_MAX_API:
        raise HTTPException(
            status_code=400,
            detail="최대 10개까지 예약 가능합니다",
        )

    reservation = {
        "id": uuid.uuid4().hex[:8],
        "numbers": req.numbers,  # validator에서 정렬 보장
        "note": req.note,
        # SPEC-LOTTO-035: UTC ISO-8601 (Python 3.9 호환)
        "created_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),  # noqa: UP017
    }
    reservations.append(reservation)
    save_reservations(reservations)
    return reservation


@router.get("/reservations")
async def list_reservations() -> dict[str, Any]:
    """예약 목록을 생성 역순(최신 먼저)으로 반환합니다 (SPEC-LOTTO-035)."""
    reservations = get_reservations()
    items = list(reversed(reservations))
    return {"total": len(items), "items": items}


@router.delete("/reservations", status_code=200)
async def delete_all_reservations() -> dict[str, int]:
    """모든 예약을 삭제하고 삭제 건수를 반환합니다 (SPEC-LOTTO-035)."""
    reservations = get_reservations()
    count = len(reservations)
    save_reservations([])
    return {"deleted": count}


@router.delete("/reservations/{reservation_id}", status_code=200)
async def delete_reservation(reservation_id: str) -> dict[str, Any]:
    """지정한 ID의 예약을 삭제합니다 (SPEC-LOTTO-035).

    존재하지 않는 ID면 404를 반환한다.
    """
    reservations = get_reservations()
    remaining = [r for r in reservations if r.get("id") != reservation_id]
    if len(remaining) == len(reservations):
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "예약을 찾을 수 없습니다."},
        )
    save_reservations(remaining)
    return {"status": "ok"}


def _scrape_worker() -> None:
    """블로그 크롤링 워커 — 두 URL에서 전체 회차 데이터를 수집합니다."""
    from lotto.collector import LottoCollector
    from lotto.scraper import scrape_all

    global _collect_state  # noqa: PLW0603

    with _collect_lock:
        _collect_state.update({
            "status": "running",
            "current": 0,
            "total": 1224,
            "collected": 0,
            "message": "블로그 크롤링 시작...",
        })

    def _on_progress(drw_no: int, row_idx: int, count: int) -> None:
        with _collect_lock:
            _collect_state["current"] = row_idx
            _collect_state["collected"] = count
            if drw_no:
                _collect_state["message"] = f"{drw_no}회차 처리 중..."

    try:
        draws = scrape_all(on_progress=_on_progress)
        if not draws:
            with _collect_lock:
                _collect_state.update({"status": "error", "message": "크롤링 결과가 없습니다."})
            # SPEC-LOTTO-009 REQ-CACHE-003: 빈 결과여도 캐시는 비워둔다
            invalidate_cache()
            return

        with _collect_lock:
            _collect_state.update({
                "status": "running",
                "message": "저장 및 통계 분석 중...",
                "total": len(draws),
            })

        collector = LottoCollector()
        collector.save_csv(draws)
        _run_analyze_sync()

        with _collect_lock:
            _collect_state.update({
                "status": "done",
                "message": f"크롤링 완료 — 총 {len(draws)}회차 저장, 통계 분석 완료",
                "total": len(draws),
                "collected": len(draws),
            })
    except Exception as exc:
        with _collect_lock:
            _collect_state.update({"status": "error", "message": f"크롤링 오류: {exc}"})
    # SPEC-LOTTO-009 REQ-CACHE-003: 성공·실패 모두 캐시 무효화로 최신성 보장
    invalidate_cache()


@router.post("/scrape", status_code=202)
async def trigger_scrape(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """블로그에서 전체 회차 데이터를 크롤링합니다.

    동행복권 API 차단 환경에서 대체 데이터 수집 수단입니다.
    """
    with _collect_lock:
        if _collect_state["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail={"error": "already_running", "message": "이미 수집이 진행 중입니다."},
            )

    background_tasks.add_task(_scrape_worker)
    return {"status": "started", "message": "블로그 크롤링을 시작했습니다."}


class PurchaseRequest(BaseModel):
    """구매 티켓 추가 요청 모델."""

    drwNo: int  # noqa: N815
    numbers: list[int]
    bought_at: str  # YYYY-MM-DD

    @field_validator("drwNo")
    @classmethod
    def validate_drw_no(cls, v: int) -> int:
        if v < 1:
            raise ValueError("회차 번호는 1 이상이어야 합니다.")
        return v

    @field_validator("bought_at")
    @classmethod
    def validate_bought_at(cls, v: str) -> str:
        import datetime as _dt
        try:
            _dt.date.fromisoformat(v)
        except ValueError as err:
            raise ValueError("날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)") from err
        return v


@router.get("/history")
async def list_history() -> list[dict[str, Any]]:
    """저장된 구매 티켓 목록과 각 회차의 당첨 결과를 함께 반환합니다."""
    # 기존 테스트(test_web_api.py)가 lotto.web.data.compute_ticket_results를
    # 직접 patch 하므로 로컬 import를 유지한다.
    from lotto.web.data import compute_ticket_results as _compute
    return _compute()


@router.post("/history", status_code=201)
async def add_history(req: PurchaseRequest) -> dict[str, Any]:
    """구매 티켓(회차·번호·구매일)을 히스토리에 추가하고 UUID를 발급합니다."""
    import uuid

    # 기존 테스트가 lotto.web.data 의 함수를 직접 patch 하므로 로컬 import 유지
    from lotto.web.data import get_history as _get_history
    from lotto.web.data import save_history as _save_history

    # 번호 검증 (Python 3.9 호환: 명시적 길이 확인)
    nums = sorted(set(req.numbers))
    if len(nums) != 6 or not all(1 <= n <= 45 for n in nums):  # noqa: PLR2004
        raise HTTPException(
            400,
            detail={
                "error": "invalid_numbers",
                "message": "번호를 확인하세요. (1~45 범위의 중복 없는 6개)",
            },
        )
    tickets = _get_history()
    ticket = {
        "id": str(uuid.uuid4()),
        "drwNo": req.drwNo,
        "numbers": nums,
        "bought_at": req.bought_at,
    }
    tickets.append(ticket)
    _save_history(tickets)
    return {"status": "ok", "ticket": ticket}


@router.delete("/history/{ticket_id}", status_code=200)
async def delete_history(ticket_id: str) -> dict[str, Any]:
    """지정한 UUID의 구매 티켓을 삭제합니다. 존재하지 않으면 404를 반환합니다."""
    # 기존 테스트가 lotto.web.data 의 함수를 직접 patch 하므로 로컬 import 유지
    from lotto.web.data import get_history as _get_history
    from lotto.web.data import save_history as _save_history

    tickets = _get_history()
    new_tickets = [t for t in tickets if t["id"] != ticket_id]
    if len(new_tickets) == len(tickets):
        raise HTTPException(
            404,
            detail={"error": "not_found", "message": "티켓을 찾을 수 없습니다."},
        )
    _save_history(new_tickets)
    return {"status": "ok"}


@router.post("/analyze", status_code=202)
async def trigger_analyze(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """수집된 당첨 데이터를 기반으로 통계 분석을 백그라운드에서 시작합니다."""
    from pathlib import Path

    from lotto.analyzer import LottoAnalyzer
    from lotto.collector import LottoCollector

    def _run_analyze() -> None:
        draws = LottoCollector().load_existing()
        if draws:
            analyzer = LottoAnalyzer()
            stats = analyzer.analyze(draws)
            analyzer.save_stats(stats, Path("data/stats.json"))
        # SPEC-LOTTO-009 REQ-CACHE-003: 분석 완료 후 캐시 무효화
        invalidate_cache()

    background_tasks.add_task(_run_analyze)
    return {"status": "started", "message": "통계 분석을 시작했습니다."}


# ─── SPEC-LOTTO-024: 번호 즉시 검증 도구 ──────────────────────────────────

# 등수별 고정 당첨금 (정수 키 기반, lotto.purchase._PRIZE_AMOUNTS 와 동일 정책)
_CHECK_PRIZE_AMOUNTS: dict[int, int] = {
    1: 0,           # 변동 (당첨자 수에 따라)
    2: 0,           # 변동
    3: 1_500_000,
    4: 50_000,
    5: 5_000,
    0: 0,           # 미당첨
}


def _parse_numbers_csv(raw: str) -> list[int]:
    """콤마 구분 문자열 "1,7,13,22,35,44" 를 정수 리스트로 파싱.

    형식 오류는 ValueError 로 위임 (호출부에서 422 변환).
    """
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [int(p) for p in parts]


def _calc_check_rank(
    user_numbers: list[int],
    draw: Any,  # noqa: ANN401 — DrawResult; runtime duck-typed for monkeypatch 호환
) -> tuple[int, list[int], bool]:
    """사용자 번호와 추첨 결과를 비교하여 (등수, 일치 번호, 보너스 일치) 반환.

    등수 매핑:
    - 6개 일치: 1등
    - 5개 일치 + 보너스: 2등
    - 5개 일치, 보너스 미일치: 3등
    - 4개 일치: 4등
    - 3개 일치: 5등
    - 그 외: 0 (미당첨)
    """
    draw_numbers = set(draw.numbers())
    user_set = set(user_numbers)
    matched_set = user_set & draw_numbers
    matched_count = len(matched_set)
    bonus_matched = draw.bonus in user_set

    if matched_count == 6:  # noqa: PLR2004
        rank = 1
    elif matched_count == 5 and bonus_matched:  # noqa: PLR2004
        rank = 2
    elif matched_count == 5:  # noqa: PLR2004
        rank = 3
    elif matched_count == 4:  # noqa: PLR2004
        rank = 4
    elif matched_count == 3:  # noqa: PLR2004
        rank = 5
    else:
        rank = 0

    return rank, sorted(matched_set), bonus_matched


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-024 REQ-CHECK-001 — 번호 즉시 검증 공개 API
# @MX:REASON: 외부 클라이언트(check 페이지 JS)에서 직접 호출되는 공개 경계
# @MX:SPEC: SPEC-LOTTO-024 REQ-CHECK-001
@router.get("/check")
async def check_numbers(
    drw_no: int = Query(..., ge=1, description="확인할 추첨 회차 번호"),
    numbers: str = Query(..., description="확인할 6개 번호 (콤마 구분, 예: 1,7,13,22,35,44)"),
) -> dict[str, Any]:
    """입력 번호의 등수를 즉시 계산하여 반환합니다 (REQ-CHECK-001).

    - 응답: {drwNo, rank, matched, bonus_matched, prize_amount, draw_date}
    - rank: 1~5 (당첨), 0 (미당첨)
    - 회차 미존재 시 404, 번호 형식 오류 시 422
    """
    # 번호 파싱 — 형식 오류는 422
    try:
        parsed = _parse_numbers_csv(numbers)
    except ValueError as err:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_numbers", "message": f"번호 형식이 올바르지 않습니다: {err}"},
        ) from err

    # 길이/범위/중복 검증
    if len(parsed) != 6:  # noqa: PLR2004
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_count", "message": "번호는 정확히 6개여야 합니다."},
        )
    if any(not (1 <= n <= 45) for n in parsed):  # noqa: PLR2004
        raise HTTPException(
            status_code=422,
            detail={"error": "out_of_range", "message": "번호는 1~45 범위여야 합니다."},
        )
    if len(set(parsed)) != 6:  # noqa: PLR2004
        raise HTTPException(
            status_code=422,
            detail={"error": "duplicate", "message": "번호에 중복이 있습니다."},
        )

    # 회차 조회 — lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    draws = wd.get_draws() or []
    draw = next((d for d in draws if d.drwNo == drw_no), None)
    if draw is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "draw_not_found", "message": f"{drw_no}회차를 찾을 수 없습니다."},
        )

    rank, matched, bonus_matched = _calc_check_rank(parsed, draw)
    return {
        "drwNo": drw_no,
        "rank": rank,
        "matched": matched,
        "bonus_matched": bonus_matched,
        "prize_amount": _CHECK_PRIZE_AMOUNTS[rank],
        "draw_date": str(draw.date),
    }


# ─── SPEC-LOTTO-028: 번호 조합 분석기 ─────────────────────────────────────

# 조합 분석에서 사용하는 상수
_COMBINATION_SIZE = 6  # 입력 번호 개수
_HISTORICAL_MATCH_MIN = 5  # historical_match로 인정하는 최소 일치 개수
_HISTORICAL_MATCH_LIMIT = 5  # 반환하는 최대 historical_match 개수
_RECENT_WINDOW = 20  # recent_score 계산에 사용하는 최근 회차 수
_VERDICT_HOT_RATIO = 1.15  # 전체 평균 대비 hot 판정 배율
_VERDICT_COLD_RATIO = 0.85  # 전체 평균 대비 cold 판정 배율
# range_distribution 5개 구간 경계 (상한, 라벨)
_RANGE_BUCKETS: tuple[tuple[int, str], ...] = (
    (10, "1-10"),
    (20, "11-20"),
    (30, "21-30"),
    (40, "31-40"),
    (45, "41-45"),
)


class CombinationRequest(BaseModel):
    """조합 분석 요청 모델 — 6개 번호 (1~45, 중복 없음)."""

    numbers: list[int]

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        """정확히 6개, 1~45 범위, 중복 없는 정수인지 검증합니다."""
        if len(v) != _COMBINATION_SIZE:
            raise ValueError("번호는 정확히 6개여야 합니다.")
        if len(set(v)) != _COMBINATION_SIZE:
            raise ValueError("번호에 중복이 있습니다.")
        for n in v:
            if not (1 <= n <= 45):  # noqa: PLR2004
                raise ValueError(f"번호 {n}은 1~45 범위를 벗어납니다.")
        return sorted(v)


def _range_distribution(numbers: list[int]) -> dict[str, int]:
    """번호를 5개 구간(1-10/11-20/21-30/31-40/41-45)으로 분류합니다."""
    dist: dict[str, int] = {label: 0 for _, label in _RANGE_BUCKETS}
    for n in numbers:
        for upper, label in _RANGE_BUCKETS:
            if n <= upper:
                dist[label] += 1
                break
    return dist


def _consecutive_count(numbers: list[int]) -> int:
    """정렬된 번호에서 인접 차이가 1인 연속쌍의 개수를 셉니다."""
    return sum(1 for i in range(len(numbers) - 1) if numbers[i + 1] - numbers[i] == 1)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-028 REQ-COMB-001 — 번호 조합 분석 단일 진입점
# @MX:REASON: /api/analyze-combination 및 /recommend 페이지 조합 분석 섹션에서 호출됨
# @MX:SPEC: SPEC-LOTTO-028 REQ-COMB-001
@router.post("/analyze-combination")
async def analyze_combination(req: CombinationRequest) -> dict[str, Any]:
    """입력 6개 번호의 조합 특성을 분석합니다 (REQ-COMB-001~004).

    - 순수 통계(sum/홀짝/구간분포/연속): 항상 계산
    - 점수(빈도/최근/동반) 및 historical_match/verdict: draws 데이터 필요
    - draws 없음/빈 데이터: 점수=0.0, historical_match=[], verdict='balanced'
    """
    numbers = req.numbers  # validator가 정렬·검증을 마침
    num_set = set(numbers)

    # 순수 통계 — 데이터 유무와 무관하게 계산 가능
    result: dict[str, Any] = {
        "numbers": numbers,
        "sum": sum(numbers),
        "odd_count": sum(1 for n in numbers if n % 2 == 1),
        "even_count": sum(1 for n in numbers if n % 2 == 0),
        "range_distribution": _range_distribution(numbers),
        "consecutive_count": _consecutive_count(numbers),
    }

    # 회차 데이터 — lotto.web.data를 직접 patch하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    draws = wd.get_draws() or []

    if not draws:
        # REQ-COMB-002: 빈 데이터 → 점수 0, 매칭 없음, balanced
        result["frequency_score"] = 0.0
        result["recent_score"] = 0.0
        result["companion_score"] = 0.0
        result["historical_match"] = []
        result["verdict"] = "balanced"
        return result

    total_draws = len(draws)

    # 전체 빈도 (본번호 1~45 절대 출현 횟수)
    abs_freq: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    for d in draws:
        for n in d.numbers():
            abs_freq[n] += 1

    # frequency_score: 입력 번호들의 평균 절대 빈도
    frequency_score = sum(abs_freq[n] for n in numbers) / _COMBINATION_SIZE

    # recent_score: 최근 N회 내 입력 번호 평균 출현 횟수
    window = min(_RECENT_WINDOW, total_draws)
    recent_draws = draws[-window:]
    recent_counts: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    for d in recent_draws:
        for n in d.numbers():
            recent_counts[n] += 1
    recent_score = sum(recent_counts[n] for n in numbers) / _COMBINATION_SIZE

    # companion_score: 입력 15개 쌍(C(6,2))의 평균 동반 출현 횟수
    pair_cooccur = 0
    pair_total = 0
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            a, b = numbers[i], numbers[j]
            count = sum(1 for d in draws if a in set(d.numbers()) and b in set(d.numbers()))
            pair_cooccur += count
            pair_total += 1
    companion_score = pair_cooccur / pair_total if pair_total else 0.0

    # REQ-COMB-004: 5개 이상 일치 회차 — 최신순 최대 5개
    matches: list[dict[str, Any]] = []
    for d in draws:
        matched = len(num_set & set(d.numbers()))
        if matched >= _HISTORICAL_MATCH_MIN:
            matches.append({
                "drwNo": d.drwNo,
                "matched": matched,
                "numbers": d.numbers(),
                "bonus": d.bonus,
            })
    matches.sort(key=lambda m: m["drwNo"], reverse=True)
    historical_match = matches[:_HISTORICAL_MATCH_LIMIT]

    # REQ-COMB-003: 전체 평균(45개 번호 절대 빈도 평균) 대비 hot/cold/balanced
    overall_avg = sum(abs_freq.values()) / 45
    if frequency_score > overall_avg * _VERDICT_HOT_RATIO:
        verdict = "hot"
    elif frequency_score < overall_avg * _VERDICT_COLD_RATIO:
        verdict = "cold"
    else:
        verdict = "balanced"

    result["frequency_score"] = round(frequency_score, 2)
    result["recent_score"] = round(recent_score, 2)
    result["companion_score"] = round(companion_score, 2)
    result["historical_match"] = historical_match
    result["verdict"] = verdict
    return result


# ─── SPEC-LOTTO-040: 번호 비교 분석기 (compare) ──────────────────────────────


class CompareRequest(BaseModel):
    """번호 비교 요청 모델 — 6개 번호 (1~45, 중복 없음) (SPEC-LOTTO-040)."""

    numbers: list[int]

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        """정확히 6개, 1~45 범위, 중복 없는 정수인지 검증합니다."""
        if len(v) != 6:  # noqa: PLR2004
            raise ValueError("번호는 정확히 6개여야 합니다.")
        if len(set(v)) != 6:  # noqa: PLR2004
            raise ValueError("번호에 중복이 있습니다.")
        for n in v:
            if not (1 <= n <= 45):  # noqa: PLR2004
                raise ValueError(f"번호 {n}은 1~45 범위를 벗어납니다.")
        return sorted(v)


# @MX:NOTE: [AUTO] SPEC-LOTTO-040 — 번호 비교 분석 공개 API
# @MX:SPEC: SPEC-LOTTO-040
@router.post("/compare")
async def compare_numbers_endpoint(req: CompareRequest) -> dict[str, Any]:
    """입력 6개 번호를 전체 추첨 회차와 비교한 분석 결과를 반환합니다 (SPEC-LOTTO-040).

    검증 실패(6개 아님/범위 외/중복)는 Pydantic 검증에서 422로 반환된다.
    데이터 부재 시에도 200으로 정상 응답 (빈 구조).
    """
    # lotto.web.data 의 함수를 직접 patch 하는 테스트와 호환되도록 동적 호출
    from lotto.web import data as wd

    return wd.compare_numbers(req.numbers, wd.get_draws())


# @MX:NOTE: [AUTO] SPEC-LOTTO-023 REQ-SCHED-003 — 스케줄러 상태 / 수동 트리거 API
# @MX:SPEC: SPEC-LOTTO-023 REQ-SCHED-003
@router.get("/scheduler/status")
async def scheduler_status() -> dict[str, Any]:
    """주간 자동 수집 스케줄러의 현재 상태를 반환한다 (REQ-SCHED-003).

    Returns:
        enabled, running, next_run, last_run_at, last_run_result, last_run_error,
        cron, tz
    """
    # 함수 내부 임포트: 순환 임포트 방지 및 테스트에서 patch 가능하도록
    from lotto.web import scheduler as _sched

    return _sched.get_status()


@router.post("/scheduler/trigger", status_code=200)
async def scheduler_trigger() -> dict[str, Any]:
    """주간 수집 작업을 즉시 수동 트리거한다 (REQ-SCHED-003).

    실행은 백그라운드 스레드에서 진행되며, 응답은 즉시 반환된다.
    """
    from lotto.web import scheduler as _sched

    return _sched.trigger_now()


# @MX:NOTE: [AUTO] SPEC-LOTTO-025 REQ-NOTIF-004 — 알림 이력/설정 공개 API
# @MX:SPEC: SPEC-LOTTO-025 REQ-NOTIF-004,005
@router.get("/notifications")
async def list_notifications() -> dict[str, Any]:
    """알림 이력 최근 50건과 마스킹된 설정 상태를 반환한다 (REQ-NOTIF-004,005).

    Response: {"settings": {...}, "items": [...]}
    파일 부재 시 items=[] (graceful).
    """
    from lotto.web import notifier as _notifier

    history = _notifier.load_history()
    # 최신순 정렬 (sent_at desc) 후 최대 50건
    sorted_history = sorted(
        history, key=lambda e: e.get("sent_at", ""), reverse=True,
    )[:50]
    return {
        "settings": _notifier.get_settings_status(),
        "items": sorted_history,
    }


# SPEC-LOTTO-027 REQ-SET-005: 테스트 발송에 사용할 샘플 페이로드
# (실데이터 대신 고정 샘플 — 외부 발송 시 "테스트 알림"임을 식별)
_TEST_DRAW_INFO: dict[str, Any] = {
    "drwNo": 0,
    "numbers": [1, 7, 13, 22, 35, 44],
    "bonus": 9,
    "prize1Amount": 0,
    "prize1Winners": 0,
}


# @MX:NOTE: [AUTO] SPEC-LOTTO-027 REQ-SET-002 — 설정 현황 공개 API (마스킹)
# @MX:SPEC: SPEC-LOTTO-027 REQ-SET-002
@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    """현재 설정 상태를 마스킹하여 반환한다 (REQ-SET-002).

    Response: {webhook_enabled, webhook_url_masked, email_enabled,
               email_to_masked, scheduler_enabled, collect_cron, notify_threshold}
    실제 URL/이메일 값은 노출되지 않는다.
    """
    from lotto.web import notifier as _notifier

    return _notifier.get_full_settings_status()


# @MX:NOTE: [AUTO] SPEC-LOTTO-027 REQ-SET-003 — Webhook 테스트 발송 API
# @MX:SPEC: SPEC-LOTTO-027 REQ-SET-003
@router.post("/settings/test-webhook", response_model=None)
async def test_webhook() -> Union[Response, dict[str, Any]]:  # noqa: UP007 — Python 3.9 런타임 호환
    """Webhook 테스트 발송 (REQ-SET-003).

    - 미설정 시 HTTP 400 + {sent: False, reason: "not_configured"}
    - 발송 성공 시 {sent: True}
    - 발송 실패(예외/False) 시 {sent: False, reason: <메시지>}
    """
    from lotto.web import notifier as _notifier

    if not _notifier.is_webhook_configured():
        return JSONResponse(
            status_code=400,
            content={"sent": False, "reason": "not_configured"},
        )
    try:
        sent = _notifier.send_webhook(_TEST_DRAW_INFO)
    except Exception as exc:  # noqa: BLE001 — 발송 실패는 사유와 함께 정상 응답
        return {"sent": False, "reason": str(exc)}
    if sent:
        return {"sent": True}
    return {"sent": False, "reason": "Webhook 전송 실패 (상세는 로그 참조)"}


# @MX:NOTE: [AUTO] SPEC-LOTTO-027 REQ-SET-004 — Email 테스트 발송 API
# @MX:SPEC: SPEC-LOTTO-027 REQ-SET-004
@router.post("/settings/test-email", response_model=None)
async def test_email() -> Union[Response, dict[str, Any]]:  # noqa: UP007 — Python 3.9 런타임 호환
    """이메일 테스트 발송 (REQ-SET-004).

    - 미설정(host/to/from 중 누락) 시 HTTP 400 + {sent: False, reason: "not_configured"}
    - 발송 성공 시 {sent: True}
    - 발송 실패(예외/False) 시 {sent: False, reason: <메시지>}
    """
    from lotto.web import notifier as _notifier

    if not _notifier.is_email_configured():
        return JSONResponse(
            status_code=400,
            content={"sent": False, "reason": "not_configured"},
        )
    try:
        sent = _notifier.send_email(_TEST_DRAW_INFO)
    except Exception as exc:  # noqa: BLE001 — 발송 실패는 사유와 함께 정상 응답
        return {"sent": False, "reason": str(exc)}
    if sent:
        return {"sent": True}
    return {"sent": False, "reason": "Email 전송 실패 (상세는 로그 참조)"}
