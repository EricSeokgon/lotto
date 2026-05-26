"""API 라우터 — JSON 엔드포인트.

# @MX:ANCHOR: [AUTO] 웹 대시보드 REST API 게이트웨이
# @MX:REASON: 외부 클라이언트(브라우저 JS, 자동화 도구)에서 직접 호출되는 공개 API 경계
"""

from __future__ import annotations

import datetime
import logging
import threading
from pathlib import Path
from typing import (
    Any,
    Optional,  # noqa: UP035 — FastAPI requires Optional for Query params on Python 3.9
)

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, field_validator, model_validator

from lotto.config import settings
from lotto.web.data import (
    get_draws,
    get_recommendations,
    get_simulation,
    get_stats,
    invalidate_cache,
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


@router.post("/collect", status_code=202)
async def trigger_collect(
    background_tasks: BackgroundTasks,
    full: bool = Query(default=False, description="True면 전체 재수집"),
    count: int = Query(default=0, ge=0, description="최근 N회 수집 (0=증분, full=True면 무시)"),
) -> dict[str, Any]:
    """데이터 수집을 백그라운드에서 시작합니다.
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
    from lotto.web.data import compute_ticket_results
    return compute_ticket_results()


@router.post("/history", status_code=201)
async def add_history(req: PurchaseRequest) -> dict[str, Any]:
    """구매 티켓(회차·번호·구매일)을 히스토리에 추가하고 UUID를 발급합니다."""
    import uuid

    from lotto.web.data import get_history, save_history

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
    tickets = get_history()
    ticket = {
        "id": str(uuid.uuid4()),
        "drwNo": req.drwNo,
        "numbers": nums,
        "bought_at": req.bought_at,
    }
    tickets.append(ticket)
    save_history(tickets)
    return {"status": "ok", "ticket": ticket}


@router.delete("/history/{ticket_id}", status_code=200)
async def delete_history(ticket_id: str) -> dict[str, Any]:
    """지정한 UUID의 구매 티켓을 삭제합니다. 존재하지 않으면 404를 반환합니다."""
    from lotto.web.data import get_history, save_history

    tickets = get_history()
    new_tickets = [t for t in tickets if t["id"] != ticket_id]
    if len(new_tickets) == len(tickets):
        raise HTTPException(
            404,
            detail={"error": "not_found", "message": "티켓을 찾을 수 없습니다."},
        )
    save_history(new_tickets)
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
