"""API 라우터 — JSON 엔드포인트.

# @MX:ANCHOR: [AUTO] 웹 대시보드 REST API 게이트웨이
# @MX:REASON: 외부 클라이언트(브라우저 JS, 자동화 도구)에서 직접 호출되는 공개 API 경계
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from lotto.web.data import (
    get_draws,
    get_recommendations,
    get_simulation,
    get_stats,
)

router = APIRouter(prefix="/api")


@router.get("/draws")
async def list_draws() -> list[dict]:
    """수집된 추첨 데이터를 반환합니다. 파일 없으면 503."""
    draws = get_draws()
    if draws is None:
        raise HTTPException(
            503,
            detail={
                "error": "data_unavailable",
                "message": "데이터가 없습니다. 먼저 수집을 실행해주세요.",
            },
        )
    return [d.model_dump() for d in draws]


@router.get("/stats")
async def get_statistics() -> dict:
    """통계 분석 결과를 반환합니다. 파일 없으면 503."""
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
) -> list[dict]:
    """번호 추천 결과를 반환합니다. 파일 없으면 503."""
    recs = get_recommendations(count=count)
    if recs is None:
        raise HTTPException(
            503,
            detail={"error": "data_unavailable", "message": "데이터가 없습니다."},
        )
    return [r.model_dump() for r in recs]


@router.get("/simulation")
async def run_simulation_results(
    rounds: int = Query(default=1000, ge=1, le=100000, description="시뮬레이션 회차 수 (1~100000)"),
) -> dict:
    """시뮬레이션 결과를 반환합니다. 파일 없으면 503."""
    result = get_simulation(rounds=rounds)
    if result is None:
        raise HTTPException(
            503,
            detail={"error": "data_unavailable", "message": "데이터가 없습니다."},
        )
    return result.model_dump()


@router.post("/collect", status_code=202)
async def trigger_collect(background_tasks: BackgroundTasks) -> dict:
    """데이터 수집을 백그라운드에서 시작합니다."""
    from lotto.collector import LottoCollector

    collector = LottoCollector()
    existing = collector.load_existing()
    latest = max((d.drwNo for d in existing), default=0)

    background_tasks.add_task(collector.collect_new, latest_drw_no=latest + 50)
    return {"status": "started", "message": "데이터 수집을 시작했습니다."}


@router.post("/analyze", status_code=202)
async def trigger_analyze(background_tasks: BackgroundTasks) -> dict:
    """통계 분석을 백그라운드에서 시작합니다."""
    from pathlib import Path

    from lotto.analyzer import LottoAnalyzer
    from lotto.collector import LottoCollector

    def _run_analyze() -> None:
        draws = LottoCollector().load_existing()
        if draws:
            analyzer = LottoAnalyzer()
            stats = analyzer.analyze(draws)
            analyzer.save_stats(stats, Path("data/stats.json"))

    background_tasks.add_task(_run_analyze)
    return {"status": "started", "message": "통계 분석을 시작했습니다."}
