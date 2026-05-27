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
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,  # noqa: UP045 — FastAPI requires Optional for Query params on Python 3.9
)

if TYPE_CHECKING:
    from collections.abc import Iterator

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, field_validator, model_validator

from lotto.config import settings
from lotto.web.data import (
    get_draws,
    get_favorites,
    get_history,
    get_recommendations,
    get_simulation,
    get_stats,
    invalidate_cache,
    pattern_analysis,
    save_favorites,
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
    return [r.model_dump() for r in recs]


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
