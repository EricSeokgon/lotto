"""데이터 접근 레이어 — 기존 lotto 모듈을 래핑하는 읽기 전용 함수들.

# @MX:ANCHOR: [AUTO] 웹 대시보드의 핵심 데이터 접근 게이트웨이
# @MX:REASON: pages.py, api.py, app.py 등 다수 모듈에서 호출됨
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lotto.config import settings

if TYPE_CHECKING:  # pragma: no cover
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
# SPEC-LOTTO-016: 번호 즐겨찾기 저장 경로
_FAVORITES_PATH = settings.data_dir / "favorites.json"

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


# SPEC-LOTTO-016: 즐겨찾기 데이터 접근자 — history와 동일한 JSON 리스트 모델
def get_favorites() -> list[dict[str, Any]]:
    """저장된 번호 즐겨찾기 목록을 저장 순서대로 반환합니다.

    파일이 없거나 손상되어 있으면 빈 리스트를 반환한다.
    """
    if not _FAVORITES_PATH.exists():
        return []
    try:
        data = json.loads(_FAVORITES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        # SPEC-LOTTO-002 REQ-ERR-002: 손상된 파일은 무음으로 삼키지 않고 경고만 남김
        logger.warning("Failed to read favorites.json: %s", exc, exc_info=True)
        return []
    if not isinstance(data, list):
        logger.warning("favorites.json 최상위가 list 아님 — 빈 목록 반환")
        return []
    return data  # type: ignore[no-any-return]


def save_favorites(favorites: list[dict[str, Any]]) -> None:
    """즐겨찾기 목록을 원자적으로 저장합니다.

    임시 파일에 먼저 기록한 뒤 os.replace로 최종 경로에 교체하여
    쓰기 중단 시에도 기존 파일이 손상되지 않도록 한다.
    """
    _FAVORITES_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 동일 디렉터리에 임시 파일 생성 — os.replace의 원자성 보장 조건
    fd, tmp_path = tempfile.mkstemp(
        prefix=".favorites_", suffix=".json.tmp", dir=str(_FAVORITES_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(favorites, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _FAVORITES_PATH)
    except Exception:
        # 실패 시 임시 파일 정리 — 정리 실패 자체는 무시
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


# SPEC-LOTTO-015 REQ-PRIZE-006: 영문 코드 → 한국어 라벨 매핑 (단일 소스)
# 템플릿 rank_label과 동일한 매핑. 서버사이드에서 prize 한국어 필드 생성 시 사용.
_RANK_KO_LABEL: dict[str, str] = {
    "1st": "1등",
    "2nd": "2등",
    "3rd": "3등",
    "4th": "4등",
    "5th": "5등",
    "none": "낙첨",
    "pending": "미추첨",
}


def _calc_prize(matched: int, bonus: bool) -> str:
    """일치 번호 수와 보너스 일치 여부로 등수를 계산합니다.

    # @MX:NOTE: [AUTO] SPEC-LOTTO-015 REQ-PRIZE-005 - lotto.purchase.calc_prize에 위임
    # 한국어 라벨 반환 형식은 기존 호출자 (test_web_data.py, history.html 템플릿)와의
    # 하위 호환을 위해 유지. 신규 코드는 lotto.purchase.calc_prize 직접 사용 권장.
    """
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
    # @MX:SPEC: SPEC-LOTTO-015 REQ-PRIZE-001, REQ-PRIZE-002, REQ-PRIZE-005

    SPEC-LOTTO-015 변경:
    - prize_rank/prize_amount/matched_count/matched_bonus 7개 신규 필드 추가
    - 등수 계산은 lotto.purchase.calc_prize에 위임 (단일 소스)
    - 추첨 데이터 없는 회차는 prize_rank='pending' (REQ-PRIZE-002)
    """
    from lotto.purchase import calc_prize  # 지연 import (순환 의존 방지)

    tickets = get_history()
    draws = get_draws()
    draw_map = {d.drwNo: d for d in draws} if draws else {}

    results: list[dict[str, Any]] = []
    for t in tickets:
        drw_no = t["drwNo"]
        draw = draw_map.get(drw_no)
        # SPEC-LOTTO-015 REQ-PRIZE-005: calc_prize 단일 호출로 등수/당첨금/일치/보너스 결정
        rank, amount, matched, bonus_match = calc_prize(t["numbers"], draw)
        prize_ko = _RANK_KO_LABEL.get(rank, "낙첨")

        if draw is not None:
            results.append({
                "ticket": t,
                "draw_numbers": draw.numbers(),
                "draw_bonus": draw.bonus,
                "draw_date": str(draw.date),
                # 기존 필드 (하위 호환)
                "matched": matched,
                "bonus_match": bonus_match,
                "prize": prize_ko,
                # SPEC-LOTTO-015 신규 필드
                "prize_rank": rank,
                "prize_amount": amount,
                "matched_count": matched,
                "matched_bonus": bonus_match,
            })
        else:
            # 추첨 데이터 없음 → pending
            results.append({
                "ticket": t,
                "draw_numbers": [],
                "draw_bonus": 0,
                "draw_date": "",
                # 기존 필드 (하위 호환)
                "matched": 0,
                "bonus_match": False,
                "prize": "미추첨",
                # SPEC-LOTTO-015 신규 필드
                "prize_rank": "pending",
                "prize_amount": 0,
                "matched_count": 0,
                "matched_bonus": False,
            })
    # 최신 회차 순
    results.sort(key=lambda r: r["ticket"]["drwNo"], reverse=True)
    return results


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-019 REQ-PAT-001 — 번호 패턴 분석 단일 진입점
# @MX:REASON: /api/pattern-analysis 및 /analyze 페이지(REQ-PAT-002) 양쪽에서 호출됨
# @MX:SPEC: SPEC-LOTTO-019 REQ-PAT-001
def pattern_analysis(draws: list[DrawResult] | None = None) -> dict[str, Any]:
    """전체 추첨 데이터에서 번호 패턴 분포를 계산합니다.

    Args:
        draws: 분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
               호출자가 이미 draws를 보유한 경우 중복 CSV 파싱을 피하기 위해 전달.

    반환 구조:
        - odd_even: {"0".."6": draws-with-N-odd-numbers}
        - range_dist: {"1-9","10-19","20-29","30-39","40-45": 누적 번호 개수}
        - consecutive: 연속 번호 쌍을 포함한 회차 비율 (0.0~1.0)
        - sum_range: 회차 합계의 10단위 버킷 분포 (예: "100-109")
        - last_digit: {"0".."9": 모든 번호의 끝자리 누적 빈도}
        - total_draws: 분석 회차 수

    draws.csv 부재(get_draws() is None) 또는 빈 데이터인 경우
    total_draws=0의 빈 구조를 반환한다.
    """
    # 빈/None 데이터에서도 키 셋이 일관되도록 0으로 초기화
    odd_even: dict[str, int] = {str(i): 0 for i in range(7)}
    range_dist: dict[str, int] = {
        "1-9": 0, "10-19": 0, "20-29": 0, "30-39": 0, "40-45": 0,
    }
    last_digit: dict[str, int] = {str(i): 0 for i in range(10)}
    sum_range: dict[str, int] = {}

    if draws is None:
        draws = get_draws()
    if not draws:
        return {
            "odd_even": odd_even,
            "range_dist": range_dist,
            "consecutive": 0.0,
            "sum_range": sum_range,
            "last_digit": last_digit,
            "total_draws": 0,
        }

    consecutive_count = 0
    for draw in draws:
        nums = draw.numbers()  # 정렬된 6개

        # 홀짝 분포 (홀수 개수)
        odd_count = sum(1 for n in nums if n % 2 == 1)
        odd_even[str(odd_count)] = odd_even.get(str(odd_count), 0) + 1

        # 범위 분포 (각 번호의 구간 누적)
        for n in nums:
            if n <= 9:  # noqa: PLR2004
                range_dist["1-9"] += 1
            elif n <= 19:  # noqa: PLR2004
                range_dist["10-19"] += 1
            elif n <= 29:  # noqa: PLR2004
                range_dist["20-29"] += 1
            elif n <= 39:  # noqa: PLR2004
                range_dist["30-39"] += 1
            else:  # 40~45
                range_dist["40-45"] += 1

        # 연속 번호 (정렬된 인접 차이 1)
        has_consecutive = any(nums[i + 1] - nums[i] == 1 for i in range(len(nums) - 1))
        if has_consecutive:
            consecutive_count += 1

        # 합계 10단위 버킷
        total = sum(nums)
        bucket_lo = (total // 10) * 10
        bucket_key = f"{bucket_lo}-{bucket_lo + 9}"
        sum_range[bucket_key] = sum_range.get(bucket_key, 0) + 1

        # 끝자리 (6개 모두 누적)
        for n in nums:
            last_digit[str(n % 10)] += 1

    total_draws = len(draws)
    return {
        "odd_even": odd_even,
        "range_dist": range_dist,
        "consecutive": consecutive_count / total_draws if total_draws else 0.0,
        "sum_range": sum_range,
        "last_digit": last_digit,
        "total_draws": total_draws,
    }


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


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-017 REQ-PRIZE-D-002 — 1등 당첨금 통계 단일 진입점
# @MX:REASON: /api/prize-stats 및 홈 페이지 카드 양쪽에서 호출되는 공개 데이터 함수
# @MX:SPEC: SPEC-LOTTO-017 REQ-PRIZE-D-002
def get_prize_stats(recent_limit: int = 20) -> dict[str, Any]:
    """1등 당첨금 통계를 계산하여 반환합니다.

    prize 데이터가 있는 회차(prize1Amount is not None)만 통계에 포함한다.
    데이터가 전혀 없으면 nulls 와 빈 recent 리스트를 반환한다.

    반환 구조:
        - total_draws: 전체 회차 수
        - draws_with_prize_data: prize 데이터 있는 회차 수
        - avg_prize1: 평균 1등 당첨금 (정수, 없으면 None)
        - max_prize1: 최대 1등 당첨금 (정수, 없으면 None)
        - min_prize1: 최소 1등 당첨금 (정수, 없으면 None)
        - recent: 최근 recent_limit 개 회차 [{drwNo, date, prize1Amount, prize1Winners}]
    """
    draws = get_draws()
    if not draws:
        return {
            "total_draws": 0,
            "draws_with_prize_data": 0,
            "avg_prize1": None,
            "max_prize1": None,
            "min_prize1": None,
            "recent": [],
        }

    with_prize = [d for d in draws if d.prize1Amount is not None]
    total = len(draws)
    count = len(with_prize)

    if count == 0:
        return {
            "total_draws": total,
            "draws_with_prize_data": 0,
            "avg_prize1": None,
            "max_prize1": None,
            "min_prize1": None,
            "recent": [],
        }

    amounts = [d.prize1Amount for d in with_prize if d.prize1Amount is not None]
    avg = int(sum(amounts) // len(amounts))
    # 최근 drwNo 기준 내림차순 정렬 후 recent_limit 만큼
    recent_sorted = sorted(with_prize, key=lambda d: d.drwNo, reverse=True)[:recent_limit]
    recent_payload = [
        {
            "drwNo": d.drwNo,
            "date": str(d.date),
            "prize1Amount": d.prize1Amount,
            "prize1Winners": d.prize1Winners,
        }
        for d in recent_sorted
    ]
    return {
        "total_draws": total,
        "draws_with_prize_data": count,
        "avg_prize1": avg,
        "max_prize1": max(amounts),
        "min_prize1": min(amounts),
        "recent": recent_payload,
    }


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
