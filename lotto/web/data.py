"""데이터 접근 레이어 — 기존 lotto 모듈을 래핑하는 읽기 전용 함수들.

# @MX:ANCHOR: [AUTO] 웹 대시보드의 핵심 데이터 접근 게이트웨이
# @MX:REASON: pages.py, api.py, app.py 등 다수 모듈에서 호출됨
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lotto.config import settings

if TYPE_CHECKING:
    from lotto.models import (
        DrawResult,
        Recommendation,
        SimulationResult,
        Statistics,
    )

# SPEC-LOTTO-002: 데이터 경로 외부화 — LOTTO_DATA_DIR 환경 변수로 오버라이드
DRAWS_PATH = settings.data_dir / "draws.csv"
STATS_PATH = settings.data_dir / "stats.json"
_HISTORY_PATH = settings.data_dir / "history.json"
# SPEC-LOTTO-009 REQ-LAST-002: last_sync.json은 SPEC-LOTTO-007에서 생성됨
LAST_SYNC_PATH = settings.data_dir / "last_sync.json"

# SPEC-LOTTO-002: 모듈 로거 — 무음 예외를 구조화 로깅으로 전환
logger = logging.getLogger(__name__)

# SPEC-LOTTO-009 REQ-CACHE-001/002: TTL 60초 모듈 레벨 캐시
# @MX:NOTE: [AUTO] 표준 라이브러리 time 모듈만 사용. 단일 ASGI 워커 환경 기준.
_CACHE_TTL_SECONDS = 60.0


class _CacheEntry:
    """캐시 항목 — 값과 적재 시각을 보관."""

    __slots__ = ("value", "ts")

    def __init__(self, value: Any, ts: float) -> None:  # noqa: ANN401 — 캐시는 다양한 도메인 객체를 보관
        self.value = value
        self.ts = ts


_draws_cache: _CacheEntry | None = None
_stats_cache: _CacheEntry | None = None


def invalidate_cache() -> None:
    """get_draws/get_stats의 메모리 캐시를 비웁니다.

    SPEC-LOTTO-009 REQ-CACHE-003: 데이터 수집/분석/크롤링 완료 후 호출됩니다.
    """
    global _draws_cache, _stats_cache  # noqa: PLW0603 — 모듈 레벨 캐시는 의도된 전역 상태
    _draws_cache = None
    _stats_cache = None


def interpolate_color(t: float) -> str:
    """빈도 백분위수를 색상 hex 문자열로 변환합니다.

    Args:
        t: 0.0(저빈도) ~ 1.0(고빈도) 사이의 값

    Returns:
        #RRGGBB 형식 hex 색상 (저빈도: #E2E8F0, 고빈도: #3B82F6)
    """
    t = max(0.0, min(1.0, t))
    low = (0xE2, 0xE8, 0xF0)
    high = (0x3B, 0x82, 0xF6)
    r = int(low[0] + (high[0] - low[0]) * t)
    g = int(low[1] + (high[1] - low[1]) * t)
    b = int(low[2] + (high[2] - low[2]) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def compute_frequency_percentiles(frequency: dict[int, int]) -> dict[int, float]:
    """각 번호의 빈도 백분위수(0.0~1.0)를 계산합니다.

    동일 빈도가 있을 경우 번호 오름차순으로 타이 브레이크합니다.

    Args:
        frequency: {번호: 빈도수} 딕셔너리

    Returns:
        {번호: 백분위수} 딕셔너리
    """
    sorted_items = sorted(frequency.items(), key=lambda x: (x[1], x[0]))
    n = len(sorted_items)
    if n <= 1:
        return {k: 0.0 for k, _ in sorted_items}
    return {k: i / (n - 1) for i, (k, _) in enumerate(sorted_items)}


@dataclass
class DataStatus:
    """데이터 파일 가용 상태."""

    draws_available: bool
    stats_available: bool


def get_data_status() -> DataStatus:
    """draws.csv 및 stats.json 존재 여부를 반환합니다."""
    return DataStatus(
        draws_available=DRAWS_PATH.exists(),
        stats_available=STATS_PATH.exists(),
    )


def get_draws() -> list[DrawResult] | None:
    """기존 수집 데이터를 반환합니다. 파일 없거나 비어있으면 None.

    SPEC-LOTTO-009 REQ-CACHE-001: 60초 TTL 메모리 캐시 적용.
    캐시 적중 시 CSV를 재파싱하지 않고 메모리 보관된 결과 반환.
    """
    global _draws_cache  # noqa: PLW0603 — 의도된 모듈 캐시 상태
    now = time.time()
    if _draws_cache is not None and (now - _draws_cache.ts) < _CACHE_TTL_SECONDS:
        cached: list[DrawResult] | None = _draws_cache.value
        return cached

    if not DRAWS_PATH.exists():
        return None
    try:
        from lotto.collector import LottoCollector

        result = LottoCollector(data_dir=DRAWS_PATH.parent).load_existing()
        value: list[DrawResult] | None = result if result else None
    except Exception as exc:  # noqa: BLE001
        # SPEC-LOTTO-002 REQ-ERR-002: 캐시 로드 실패는 무음으로 삼키지 않고 경고 로그 기록
        logger.warning("Failed to load cached draws data: %s", exc, exc_info=True)
        return None

    _draws_cache = _CacheEntry(value, now)
    return value


def get_stats() -> Statistics | None:
    """통계 분석 결과를 반환합니다. 파일 없으면 None.

    SPEC-LOTTO-009 REQ-CACHE-002: 60초 TTL 메모리 캐시 적용.
    """
    global _stats_cache  # noqa: PLW0603 — 의도된 모듈 캐시 상태
    now = time.time()
    if _stats_cache is not None and (now - _stats_cache.ts) < _CACHE_TTL_SECONDS:
        cached: Statistics | None = _stats_cache.value
        return cached

    if not STATS_PATH.exists():
        return None
    from lotto.analyzer import LottoAnalyzer

    value = LottoAnalyzer.load_stats(STATS_PATH)
    _stats_cache = _CacheEntry(value, now)
    return value


def get_recommendations(count: int = 5) -> list[Recommendation] | None:
    """번호 추천 결과를 반환합니다. stats.json 없으면 None."""
    if not STATS_PATH.exists():
        return None
    from lotto.recommender import LottoRecommender

    stats = get_stats()
    if stats is None:
        return None
    return LottoRecommender(stats).recommend(count=count)


def get_history() -> list[dict[str, Any]]:
    """저장된 구매 티켓 목록을 반환합니다."""
    if not _HISTORY_PATH.exists():
        return []
    try:
        return json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return []


def save_history(tickets: list[dict[str, Any]]) -> None:
    """구매 티켓 목록을 저장합니다."""
    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_PATH.write_text(
        json.dumps(tickets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _calc_prize(matched: int, bonus: bool) -> str:
    """일치 번호 수와 보너스 일치 여부로 등수를 계산합니다."""
    if matched == 6:  # noqa: PLR2004
        return "1등"
    if matched == 5 and bonus:  # noqa: PLR2004
        return "2등"
    if matched == 5:  # noqa: PLR2004
        return "3등"
    if matched == 4:  # noqa: PLR2004
        return "4등"
    if matched == 3:  # noqa: PLR2004
        return "5등"
    return "낙첨"


def compute_ticket_results() -> list[dict[str, Any]]:
    """티켓 목록에 추첨 결과를 합산합니다.

    # @MX:ANCHOR: [AUTO] 구매 히스토리와 추첨 데이터를 합산하는 핵심 함수
    # @MX:REASON: api.py의 /api/history GET과 pages.py의 /history 페이지 양쪽에서 호출됨
    """
    tickets = get_history()
    draws = get_draws()
    draw_map = {d.drwNo: d for d in draws} if draws else {}

    results: list[dict[str, Any]] = []
    for t in tickets:
        drw_no = t["drwNo"]
        draw = draw_map.get(drw_no)
        if draw:
            drawn = set(draw.numbers())
            purchased = set(t["numbers"])
            matched = len(drawn & purchased)
            # Python 3.9 호환: zip(strict=True) 대신 명시적 길이 확인
            bonus_match = draw.bonus in purchased and draw.bonus not in drawn
            prize = _calc_prize(matched, bonus_match)
            results.append({
                "ticket": t,
                "draw_numbers": draw.numbers(),
                "draw_bonus": draw.bonus,
                "draw_date": str(draw.date),
                "matched": matched,
                "bonus_match": bonus_match,
                "prize": prize,
            })
        else:
            results.append({
                "ticket": t,
                "draw_numbers": [],
                "draw_bonus": 0,
                "draw_date": "",
                "matched": 0,
                "bonus_match": False,
                "prize": "미추첨",
            })
    # 최신 회차 순
    results.sort(key=lambda r: r["ticket"]["drwNo"], reverse=True)
    return results


def get_simulation(rounds: int = 1000) -> SimulationResult | None:
    """시뮬레이션 결과를 반환합니다. draws.csv 없으면 None."""
    if not DRAWS_PATH.exists():
        return None
    draws = get_draws()
    if not draws:
        return None
    from lotto.simulator import LottoSimulator

    return LottoSimulator(draws).simulate(rounds=rounds)


def get_strategy_comparison(rounds: int = 100) -> list[dict[str, Any]] | None:
    """전략별 시뮬레이션 비교 결과를 반환합니다.

    pre-computed stats.json 기반 빠른 비교 (비인과적이지만 상대 비교에 충분)
    """
    if not DRAWS_PATH.exists() or not STATS_PATH.exists():
        return None
    draws = get_draws()
    stats = get_stats()
    if not draws or not stats:
        return None

    from lotto.recommender import STRATEGY_LABELS, LottoRecommender
    from lotto.simulator import LottoSimulator

    sim = LottoSimulator(draws)
    recommender = LottoRecommender(stats)
    test_draws = draws[-min(rounds, 200):]

    comparison: list[dict[str, Any]] = []
    for label in STRATEGY_LABELS:
        prize_counts: dict[str, int] = {
            "1등": 0, "2등": 0, "3등": 0, "4등": 0, "5등": 0, "낙첨": 0,
        }
        hits = 0
        for target in test_draws:
            rec = recommender.recommend_by_strategy(label)
            prize = sim._evaluate_round(rec.numbers, target)
            prize_counts[prize] = prize_counts.get(prize, 0) + 1
            if prize != "낙첨":
                hits += 1
        hit_rate = hits / len(test_draws) if test_draws else 0.0
        comparison.append({
            "strategy_label": label,
            "hit_count": hits,
            "hit_rate": round(hit_rate * 100, 2),
            "prize_counts": prize_counts,
            "total_rounds": len(test_draws),
        })
    return comparison


# @MX:NOTE: [AUTO] SPEC-LOTTO-009 REQ-LAST-002 — last_sync.json 우선, draws 최신 회차 폴백
def get_last_sync_date() -> str | None:
    """마지막 수집 날짜를 YYYY-MM-DD 형식 문자열로 반환합니다.

    SPEC-LOTTO-009 REQ-LAST-002 우선순위:
    1. data/last_sync.json의 synced_at 앞 10자
    2. draws.csv의 최신 회차 date 문자열
    3. 둘 다 없으면 None
    """
    if LAST_SYNC_PATH.exists():
        try:
            meta = json.loads(LAST_SYNC_PATH.read_text(encoding="utf-8"))
            synced_at = meta.get("synced_at", "") if isinstance(meta, dict) else ""
            if synced_at:
                return synced_at[:10]
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read last_sync.json: %s", exc, exc_info=True)

    draws = get_draws()
    if draws:
        latest = max(draws, key=lambda d: d.drwNo)
        return str(latest.date)
    return None
