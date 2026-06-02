"""데이터 접근 레이어 — 기존 lotto 모듈을 래핑하는 읽기 전용 함수들.

# @MX:ANCHOR: [AUTO] 웹 대시보드의 핵심 데이터 접근 게이트웨이
# @MX:REASON: pages.py, api.py, app.py 등 다수 모듈에서 호출됨
"""

from __future__ import annotations

import contextlib
import datetime
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

# SPEC-LOTTO-033: 번호 생성 이력 저장 경로
_GEN_HISTORY_PATH = settings.data_dir / "gen_history.json"
# SPEC-LOTTO-033: 이력 최대 보관 건수 / 조회 시 반환 최대 건수
_GEN_HISTORY_MAX = 200
_GEN_HISTORY_VIEW_LIMIT = 50

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
    return data


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


# ─── SPEC-LOTTO-036: 번호 메모 (number_notes) ───────────────────────────────

# SPEC-LOTTO-036: 번호 메모 저장 경로 — {번호(str): {"note": str, "updated_at": ISO str}}
_NUMBER_NOTES_PATH = settings.data_dir / "number_notes.json"


def get_number_notes() -> dict[str, dict[str, Any]]:
    """저장된 번호 메모 전체를 dict로 반환합니다 (SPEC-LOTTO-036).

    구조는 {번호(str): {"note": str, "updated_at": ISO str}} 이며,
    파일이 없거나 손상되어 있으면 빈 dict를 반환한다.
    """
    if not _NUMBER_NOTES_PATH.exists():
        return {}
    try:
        data = json.loads(_NUMBER_NOTES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read number_notes.json: %s", exc, exc_info=True)
        return {}
    if not isinstance(data, dict):
        logger.warning("number_notes.json 최상위가 dict 아님 — 빈 dict 반환")
        return {}
    return data


def save_number_notes(notes: dict[str, dict[str, Any]]) -> None:
    """번호 메모 전체를 원자적으로 저장합니다 (SPEC-LOTTO-036).

    임시 파일에 먼저 기록한 뒤 os.replace로 교체하여 쓰기 중단 시에도
    기존 파일이 손상되지 않도록 한다 (favorites와 동일 패턴).
    """
    _NUMBER_NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".number_notes_", suffix=".json.tmp", dir=str(_NUMBER_NOTES_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(notes, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _NUMBER_NOTES_PATH)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


# ─── SPEC-LOTTO-033: 번호 생성 이력 (gen_history) ──────────────────────────


def get_gen_history() -> list[dict[str, Any]]:
    """저장된 번호 생성 이력을 저장 순서대로 반환합니다 (SPEC-LOTTO-033).

    파일이 없거나 손상되어 있으면 빈 리스트를 반환한다.
    """
    if not _GEN_HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(_GEN_HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read gen_history.json: %s", exc, exc_info=True)
        return []
    if not isinstance(data, list):
        logger.warning("gen_history.json 최상위가 list 아님 — 빈 목록 반환")
        return []
    return data


# @MX:NOTE: [AUTO] SPEC-LOTTO-033 — 추천 결과를 이력에 append (저장 실패는 조용히 무시)
def append_gen_history(strategy: str, numbers: list[int]) -> None:
    """번호 생성 이력에 항목 1건을 추가합니다 (SPEC-LOTTO-033).

    최근 _GEN_HISTORY_MAX 건만 유지하며, 저장 실패 시 예외를 전파하지 않는다
    (호출자인 추천 API 응답은 정상 반환되어야 한다).
    """
    import uuid

    entry = {
        "id": uuid.uuid4().hex[:8],
        # SPEC-LOTTO-033: UTC ISO-8601 (Python 3.9 호환)
        "generated_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),  # noqa: UP017
        "strategy": strategy,
        "numbers": list(numbers),
        "source": "api",
    }
    try:
        history = get_gen_history()
        history.append(entry)
        # 최근 N건만 유지 (초과 시 오래된 것부터 제거)
        if len(history) > _GEN_HISTORY_MAX:
            history = history[-_GEN_HISTORY_MAX:]
        _GEN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GEN_HISTORY_PATH.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 — 이력 저장 실패는 추천 응답을 막지 않는다
        logger.warning("Failed to append gen_history: %s", exc, exc_info=True)


def clear_gen_history() -> int:
    """번호 생성 이력을 전체 삭제하고 삭제된 건수를 반환합니다 (SPEC-LOTTO-033)."""
    history = get_gen_history()
    count = len(history)
    try:
        _GEN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GEN_HISTORY_PATH.write_text("[]", encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to clear gen_history.json: %s", exc, exc_info=True)
    return count


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


# SPEC-LOTTO-026: 트렌드 히트맵에서 허용하는 기간 단위
_TREND_PERIODS = ("yearly", "quarterly")

# SPEC-LOTTO-026: draws 인자 미전달 vs 명시적 None을 구분하기 위한 센티넬.
# - 인자 생략(센티넬): 내부에서 get_draws()로 자동 로드 (단위 테스트 호환)
# - 명시적 None 전달: 데이터 없음으로 처리 (API가 get_draws() 결과를 그대로 위임)
_UNSET: Any = object()


def _period_key(d: DrawResult, period: str) -> str:
    """추첨 결과를 period 단위 그룹 키로 변환합니다.

    - yearly:    "YYYY"        (예: "2020")
    - quarterly: "YYYY-Qn"     (예: "2020-Q1")
    """
    if period == "quarterly":
        quarter = (d.date.month - 1) // 3 + 1
        return f"{d.date.year}-Q{quarter}"
    return str(d.date.year)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-026 REQ-TREND-001 — 번호 트렌드 히트맵 단일 진입점
# @MX:REASON: /api/trend-heatmap 및 /analyze 트렌드 탭(REQ-TREND-002) 양쪽에서 호출됨
# @MX:SPEC: SPEC-LOTTO-026 REQ-TREND-001
def trend_heatmap(
    period: str = "yearly",
    draws: list[DrawResult] | None = _UNSET,
) -> dict[str, Any]:
    """번호(1~45) × 기간(연도/분기)별 출현 빈도 행렬을 계산합니다.

    Args:
        period: "yearly" 또는 "quarterly". 그 외 값은 yearly로 처리한다.
                (유효성 검증은 API 레이어에서 수행 — 여기서는 안전한 기본값 폴백)
        draws:  분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.

    반환 구조:
        - period:  요청한 기간 단위 문자열
        - periods: 시간순 정렬된 기간 라벨 리스트 (예: ["2020", "2021"])
        - numbers: 번호 축 — 항상 [1..45]
        - matrix:  numbers × periods 빈도 행렬. matrix[i][j] = (i+1)번 번호가
                   periods[j] 기간에 출현한 횟수

    draws.csv 부재 또는 빈 데이터인 경우 periods/matrix를 빈 리스트로,
    numbers는 [1..45]로 반환한다.
    """
    numbers = list(range(1, 46))
    if period not in _TREND_PERIODS:
        period = "yearly"

    if draws is _UNSET:
        draws = get_draws()
    if not draws:
        return {
            "period": period,
            "periods": [],
            "numbers": numbers,
            "matrix": [],
        }

    # 기간 라벨별 {번호: 출현 횟수} 누적
    period_counts: dict[str, dict[int, int]] = {}
    for d in draws:
        key = _period_key(d, period)
        bucket = period_counts.setdefault(key, {})
        for n in d.numbers():
            bucket[n] = bucket.get(n, 0) + 1

    # 기간 라벨은 문자열 정렬로 시간순 보장 ("2020" < "2021", "2020-Q1" < "2020-Q3")
    periods = sorted(period_counts.keys())

    # matrix[번호인덱스][기간인덱스]
    matrix = [
        [period_counts[p].get(num, 0) for p in periods]
        for num in numbers
    ]

    return {
        "period": period,
        "periods": periods,
        "numbers": numbers,
        "matrix": matrix,
    }


# SPEC-LOTTO-026: 핫/콜드 분석에서 반환하는 상위/하위 항목 수
_HOT_COLD_TOP_N = 10


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-026 REQ-TREND-003 — 핫/콜드 번호 분석 단일 진입점
# @MX:REASON: /api/hot-cold 및 /analyze 트렌드 탭(REQ-TREND-004) 양쪽에서 호출됨
# @MX:SPEC: SPEC-LOTTO-026 REQ-TREND-003
def hot_cold_analysis(
    recent_n: int = 20,
    draws: list[DrawResult] | None = _UNSET,
) -> dict[str, Any]:
    """최근 N회 출현 빈도를 전체 평균과 비교하여 핫/콜드 번호를 산출합니다.

    각 번호에 대해:
        - recent_count: 최근 N회(또는 가용 전체) 내 출현 횟수
        - avg_count:    전체 데이터 기준, 동일 표본 크기(window)에서 기대되는 평균 출현 횟수
                        = 전체 출현 횟수 / 전체 회차 수 * window
        - diff:         recent_count - avg_count (양수=핫, 음수=콜드)

    hot은 diff 내림차순 상위 10개, cold는 diff 오름차순 하위 10개를 반환한다.

    Args:
        recent_n: 최근 회차 표본 크기. 총 회차 수보다 크면 가용한 전체를 사용한다.
        draws:    분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.

    반환 구조:
        - recent_n: 요청한 recent_n (가용 회차로 잘리더라도 요청값 그대로 반영)
        - hot:  [{number, recent_count, avg_count, diff}, ...]  (diff 내림차순)
        - cold: [{number, recent_count, avg_count, diff}, ...]  (diff 오름차순)

    draws.csv 부재 또는 빈 데이터인 경우 hot/cold를 빈 리스트로 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()
    if not draws:
        return {"recent_n": recent_n, "hot": [], "cold": []}

    total_draws = len(draws)
    # 최근 N회 (요청값이 더 크면 가용한 전체 사용)
    window = min(recent_n, total_draws)
    recent_draws = draws[-window:]

    # 전체 / 최근 출현 횟수 집계
    total_counts: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    recent_counts: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    for d in draws:
        for n in d.numbers():
            total_counts[n] += 1
    for d in recent_draws:
        for n in d.numbers():
            recent_counts[n] += 1

    # 각 번호의 (recent vs 동일 window 기대치) 비교
    items: list[dict[str, Any]] = []
    for n in range(1, 46):
        avg_count = total_counts[n] / total_draws * window
        items.append({
            "number": n,
            "recent_count": recent_counts[n],
            "avg_count": round(avg_count, 2),
            "diff": round(recent_counts[n] - avg_count, 2),
        })

    # 핫: diff 내림차순 (동률은 번호 오름차순) / 콜드: diff 오름차순
    hot = sorted(items, key=lambda x: (-x["diff"], x["number"]))[:_HOT_COLD_TOP_N]
    cold = sorted(items, key=lambda x: (x["diff"], x["number"]))[:_HOT_COLD_TOP_N]

    return {"recent_n": recent_n, "hot": hot, "cold": cold}


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


# SPEC-LOTTO-032: 전략 비교에서 사용하는 등수별 당첨금 (시뮬레이션 페이지와 동일 정책)
_COMPARE_PRIZE_VALUES: dict[str, int] = {
    "1등": 2_000_000_000,
    "2등": 60_000_000,
    "3등": 1_500_000,
    "4등": 50_000,
    "5등": 5_000,
    "낙첨": 0,
}
# SPEC-LOTTO-032: 회차당 구매 비용 (원) — total_spent 산출 기준
_COMPARE_TICKET_COST = 1000
# SPEC-LOTTO-032: 등수 우선순위 (작을수록 높은 등수) — best_rank 판정용
_COMPARE_RANK_ORDER: dict[str, int] = {
    "1등": 1, "2등": 2, "3등": 3, "4등": 4, "5등": 5, "낙첨": 6,
}


# @MX:NOTE: [AUTO] SPEC-LOTTO-032 REQ-CMP-001 — 전략별 백테스트 비교 단일 진입점
# @MX:SPEC: SPEC-LOTTO-032
def strategy_compare(
    rounds: int = 100,
    draws: list[DrawResult] | None = _UNSET,
    stats: Statistics | None = _UNSET,
) -> dict[str, Any]:
    """8가지 추천 전략을 동일 기간에 백테스트하여 성과를 비교합니다 (SPEC-LOTTO-032).

    각 전략에 대해 최근 N회차를 대상으로 recommend_by_strategy 추천 후
    등수를 집계하고 ROI/등수별 당첨 횟수/최고 등수를 산출한다.

    Args:
        rounds: 최근 N회차 (API 레이어에서 10~500 검증). 가용 회차보다 크면 가용 전체 사용.
        draws:  분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
        stats:  추천에 사용할 통계. 생략 시 get_stats()로 자동 로드한다.

    반환 구조:
        - rounds: 실제 백테스트에 사용한 회차 수 (요청값을 가용 회차로 자른 결과)
        - strategies: [{strategy, label, total_spent, total_prize, roi,
                        match3_count, match4_count, match5_count,
                        match5b_count, match6_count, best_rank}, ...]

    draws/stats 부재 또는 빈 데이터인 경우 strategies=[] 를 반환한다 (rounds는 요청값 유지).
    """
    if draws is _UNSET:
        draws = get_draws()
    if stats is _UNSET:
        stats = get_stats()

    # 데이터 부재 → 빈 비교 (요청 rounds는 그대로 노출)
    if not draws or stats is None:
        return {"rounds": rounds, "strategies": []}

    from lotto.recommender import STRATEGY_LABELS, LottoRecommender
    from lotto.simulator import LottoSimulator

    # 최근 N회차 (가용 회차보다 크면 가용 전체)
    used_rounds = min(rounds, len(draws))
    test_draws = draws[-used_rounds:]

    sim = LottoSimulator(draws)
    recommender = LottoRecommender(stats)
    total_spent = used_rounds * _COMPARE_TICKET_COST

    strategies: list[dict[str, Any]] = []
    for label in STRATEGY_LABELS:
        # 등수별 당첨 횟수 집계
        prize_counts: dict[str, int] = dict.fromkeys(_COMPARE_PRIZE_VALUES, 0)
        for target in test_draws:
            rec = recommender.recommend_by_strategy(label)
            prize = sim._evaluate_round(rec.numbers, target)
            prize_counts[prize] = prize_counts.get(prize, 0) + 1

        total_prize = sum(
            prize_counts.get(p, 0) * amount
            for p, amount in _COMPARE_PRIZE_VALUES.items()
        )
        roi = round((total_prize - total_spent) / total_spent * 100, 1) if total_spent else 0.0

        # 최고 등수 — 1회라도 당첨된 가장 높은 등수
        best_rank = "낙첨"
        for rank in ("1등", "2등", "3등", "4등", "5등"):
            if prize_counts.get(rank, 0) > 0:
                best_rank = rank
                break

        strategies.append({
            "strategy": label,
            "label": f"{label} 전략",
            "total_spent": total_spent,
            "total_prize": total_prize,
            "roi": roi,
            "match3_count": prize_counts.get("5등", 0),
            "match4_count": prize_counts.get("4등", 0),
            "match5_count": prize_counts.get("3등", 0),
            "match5b_count": prize_counts.get("2등", 0),
            "match6_count": prize_counts.get("1등", 0),
            "best_rank": best_rank,
        })

    return {"rounds": used_rounds, "strategies": strategies}


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


# SPEC-LOTTO-030: 번호 상세 통계에서 사용하는 위치 라벨 (정렬된 6개 번호의 1~6번째)
_POSITION_LABELS = ("1st", "2nd", "3rd", "4th", "5th", "6th")
# SPEC-LOTTO-030: 동반 번호 / 최근 출현 윈도 상수
_COMPANION_TOP_N = 5
_RECENT_WINDOW = 20


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-030 REQ-NUMSTAT-001 — 번호별 상세 통계 단일 진입점
# @MX:REASON: /api/numbers/{n}/stats, /numbers, /numbers/{n} 세 라우트에서 호출됨
# @MX:SPEC: SPEC-LOTTO-030
def number_stats(
    number: int,
    draws: list[DrawResult] | None = _UNSET,
) -> dict[str, Any]:
    """특정 번호(1~45)의 전체 출현 이력과 상세 통계를 계산합니다.

    Args:
        number: 통계를 계산할 번호 (1~45). 범위 검증은 API 레이어가 수행한다.
        draws:  분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.

    반환 구조:
        - number:           대상 번호
        - total_count:      본번호로 출현한 총 횟수
        - total_draws:      전체 회차 수
        - frequency_pct:    출현율(%) = total_count / total_draws * 100 (소수 2자리)
        - last_appeared:    마지막 출현 회차 번호 (없으면 None)
        - gap_since_last:   최신 회차 - 마지막 출현 회차 (없으면 None)
        - longest_absence:  최장 연속 미출현 회차 수
        - avg_gap:          출현 간 평균 간격 (소수 1자리, 출현 1회 이하면 0.0)
        - recent_20_count:  최근 20회 내 출현 횟수
        - companion_top5:   동반 출현 상위 5개 [{number, count}] (자기 자신 제외)
        - by_position:      정렬된 당첨번호 중 위치(1st~6th)별 출현 빈도

    draws가 비어 있으면 모든 카운트 0, 리스트 빈값, 적절한 None을 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    # 위치 빈도는 항상 6개 키가 존재하도록 0으로 초기화
    by_position: dict[str, int] = dict.fromkeys(_POSITION_LABELS, 0)

    if not draws:
        return {
            "number": number,
            "total_count": 0,
            "total_draws": 0,
            "frequency_pct": 0.0,
            "last_appeared": None,
            "gap_since_last": None,
            "longest_absence": 0,
            "avg_gap": 0.0,
            "recent_20_count": 0,
            "companion_top5": [],
            "by_position": by_position,
        }

    # 회차 오름차순 정렬 — 간격/미출현 계산은 시간순 전제
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    total_draws = len(sorted_draws)
    latest_drw_no = sorted_draws[-1].drwNo

    appeared_drw_nos: list[int] = []  # number가 출현한 회차 번호 (오름차순)
    companion_counts: dict[int, int] = {}

    for draw in sorted_draws:
        nums = draw.numbers()  # 정렬된 6개
        if number in nums:
            appeared_drw_nos.append(draw.drwNo)
            # 위치(1-based) 빈도
            position_idx = nums.index(number)  # 0~5
            by_position[_POSITION_LABELS[position_idx]] += 1
            # 동반 번호 집계 (자기 자신 제외)
            for n in nums:
                if n != number:
                    companion_counts[n] = companion_counts.get(n, 0) + 1

    total_count = len(appeared_drw_nos)
    frequency_pct = round(total_count / total_draws * 100, 2) if total_draws else 0.0

    # 마지막 출현 회차 / 최신 회차와의 간격
    last_appeared = appeared_drw_nos[-1] if appeared_drw_nos else None
    gap_since_last = (latest_drw_no - last_appeared) if last_appeared is not None else None

    # 최장 연속 미출현 회차 수 — 출현 회차 인덱스 사이의 빈 회차 + 마지막 출현 이후
    longest_absence = _compute_longest_absence(sorted_draws, appeared_drw_nos)

    # 평균 출현 간격 — 인접 출현 회차 차이의 평균 (출현 2회 미만이면 0.0)
    if total_count >= 2:  # noqa: PLR2004
        gaps = [
            appeared_drw_nos[i + 1] - appeared_drw_nos[i]
            for i in range(total_count - 1)
        ]
        avg_gap = round(sum(gaps) / len(gaps), 1)
    else:
        avg_gap = 0.0

    # 최근 N회 내 출현 횟수
    window = min(_RECENT_WINDOW, total_draws)
    recent_draws = sorted_draws[-window:]
    recent_20_count = sum(1 for d in recent_draws if number in d.numbers())

    # 동반 번호 top5 (count 내림차순, 동률은 번호 오름차순)
    companion_top5 = [
        {"number": n, "count": c}
        for n, c in sorted(companion_counts.items(), key=lambda x: (-x[1], x[0]))[:_COMPANION_TOP_N]
    ]

    return {
        "number": number,
        "total_count": total_count,
        "total_draws": total_draws,
        "frequency_pct": frequency_pct,
        "last_appeared": last_appeared,
        "gap_since_last": gap_since_last,
        "longest_absence": longest_absence,
        "avg_gap": avg_gap,
        "recent_20_count": recent_20_count,
        "companion_top5": companion_top5,
        "by_position": by_position,
    }


def _compute_longest_absence(
    sorted_draws: list[DrawResult],
    appeared_drw_nos: list[int],
) -> int:
    """정렬된 회차 목록에서 대상 번호의 최장 연속 미출현 회차 수를 계산합니다.

    출현 회차 집합을 기준으로 전체 회차를 훑으며 연속 미출현 구간의 최댓값을 구한다.
    한 번도 출현하지 않았다면 전체 회차 수가 곧 최장 미출현 구간이다.
    """
    appeared_set = set(appeared_drw_nos)
    longest = 0
    current = 0
    for draw in sorted_draws:
        if draw.drwNo in appeared_set:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


# SPEC-LOTTO-031: 누락 회차 목록 최대 반환 개수
_MISSING_LIMIT = 50


# @MX:NOTE: [AUTO] SPEC-LOTTO-031 — 수집 현황 요약 + 누락 회차 감지
# @MX:SPEC: SPEC-LOTTO-031
def collect_summary(
    draws: list[DrawResult] | None = _UNSET,
) -> dict[str, Any]:
    """데이터 수집 현황을 요약하고 누락 회차를 감지합니다 (SPEC-LOTTO-031).

    Args:
        draws: 분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.

    반환 구조:
        - total_collected: 수집된 회차 수
        - latest_drw_no:   최신(최대) 회차 번호 (없으면 0)
        - oldest_drw_no:   최오래된(최소) 회차 번호 (없으면 0)
        - missing_drw_nos: 1 ~ latest 범위에서 빠진 회차 번호 목록 (최대 50개)
        - missing_count:   누락 회차 전체 개수 (50개 초과 시에도 전체 개수)
        - coverage_pct:    수집률(%) = total_collected / latest * 100 (소수 2자리)
        - date_range:      {"from": 최오래된 회차 날짜, "to": 최신 회차 날짜} (없으면 None)

    데이터 부재 시 모든 수치 0, 빈 리스트, None 날짜를 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    if not draws:
        return {
            "total_collected": 0,
            "latest_drw_no": 0,
            "oldest_drw_no": 0,
            "missing_drw_nos": [],
            "missing_count": 0,
            "coverage_pct": 0.0,
            "date_range": {"from": None, "to": None},
        }

    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    existing_nos = {d.drwNo for d in sorted_draws}
    oldest = sorted_draws[0].drwNo
    latest = sorted_draws[-1].drwNo
    total_collected = len(sorted_draws)

    # 1 ~ latest 범위에서 누락된 회차 (전체 개수 + 최대 50개 반환)
    all_missing = [n for n in range(1, latest + 1) if n not in existing_nos]
    missing_count = len(all_missing)
    missing_drw_nos = all_missing[:_MISSING_LIMIT]

    coverage_pct = round(total_collected / latest * 100, 2) if latest else 0.0

    return {
        "total_collected": total_collected,
        "latest_drw_no": latest,
        "oldest_drw_no": oldest,
        "missing_drw_nos": missing_drw_nos,
        "missing_count": missing_count,
        "coverage_pct": coverage_pct,
        "date_range": {
            "from": str(sorted_draws[0].date),
            "to": str(sorted_draws[-1].date),
        },
    }


# ─── SPEC-LOTTO-034: 주간 통계 리포트 (weekly_report) ───────────────────────

# SPEC-LOTTO-034: 리포트에서 사용하는 5개 번호대 구간 (라벨 → (하한, 상한))
# most_common_range 동률 시 이 순서(앞쪽 우선)로 타이 브레이크한다.
_WEEKLY_RANGES: tuple[tuple[str, int, int], ...] = (
    ("1-10", 1, 10),
    ("11-20", 11, 20),
    ("21-30", 21, 30),
    ("31-40", 31, 40),
    ("41-45", 41, 45),
)
# SPEC-LOTTO-034: top/bottom 리스트 최대 반환 개수
_WEEKLY_TOP_N = 10


# @MX:NOTE: [AUTO] SPEC-LOTTO-034 REQ-WREP-001 — 주간 통계 리포트 단일 진입점
# @MX:SPEC: SPEC-LOTTO-034
def weekly_report(
    weeks: int = 4,
    draws: list[DrawResult] | None = _UNSET,
) -> dict[str, Any]:
    """최근 N주(= 최신 N회차) 번호 출현 경향을 요약합니다 (SPEC-LOTTO-034).

    주 1회 추첨 가정으로 "최근 N주" = 최신 회차 기준 N개 회차를 의미한다.
    weeks가 가용 회차보다 크면 가용 전체를 사용한다 (draws_included로 노출).

    Args:
        weeks: 최근 주(회차) 수. 범위 검증(1~52)은 API 레이어가 수행한다.
        draws: 분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.

    반환 구조:
        - weeks:             요청한 주 수 (가용 회차로 잘려도 요청값 그대로)
        - draws_included:    실제 집계에 사용한 회차 수
        - top10_numbers:     [{number, count}] 출현 상위 10개 (count 내림차순)
        - bottom10_numbers:  [{number, count}] 출현 하위 10개 (0회 포함, count 오름차순)
        - avg_sum:           회차 합계 평균 (소수 1자리)
        - odd_even_ratio:    {"odd": 회차당 평균 홀수 개수, "even": 평균 짝수 개수}
        - most_common_range: 5개 구간 중 가장 많이 나온 구간 라벨 (빈 데이터면 "")

    빈 데이터인 경우 0/빈 리스트/빈 문자열을 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    if not draws:
        return {
            "weeks": weeks,
            "draws_included": 0,
            "top10_numbers": [],
            "bottom10_numbers": [],
            "avg_sum": 0.0,
            "odd_even_ratio": {"odd": 0.0, "even": 0.0},
            "most_common_range": "",
        }

    # 최신 N회차 (drwNo 기준 정렬 후 뒤에서 weeks개)
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    window = min(weeks, len(sorted_draws))
    recent = sorted_draws[-window:]

    # 번호별 출현 횟수 (1~45 전부 0으로 초기화 → bottom에 미출현 번호 포함)
    counts: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    sum_total = 0
    odd_total = 0
    even_total = 0
    range_counts: dict[str, int] = {label: 0 for label, _, _ in _WEEKLY_RANGES}

    for d in recent:
        nums = d.numbers()
        sum_total += sum(nums)
        for n in nums:
            counts[n] += 1
            if n % 2 == 1:
                odd_total += 1
            else:
                even_total += 1
            for label, lo, hi in _WEEKLY_RANGES:
                if lo <= n <= hi:
                    range_counts[label] += 1
                    break

    # top: count 내림차순(동률은 번호 오름차순) / bottom: count 오름차순(동률은 번호 오름차순)
    top10 = [
        {"number": n, "count": c}
        for n, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:_WEEKLY_TOP_N]
    ]
    bottom10 = [
        {"number": n, "count": c}
        for n, c in sorted(counts.items(), key=lambda x: (x[1], x[0]))[:_WEEKLY_TOP_N]
    ]

    avg_sum = round(sum_total / window, 1)
    odd_even_ratio = {
        "odd": round(odd_total / window, 1),
        "even": round(even_total / window, 1),
    }

    # 최다 구간 — 동률은 _WEEKLY_RANGES 순서(앞쪽 우선)로 결정
    most_common_range = max(
        _WEEKLY_RANGES,
        key=lambda r: range_counts[r[0]],
    )[0]

    return {
        "weeks": weeks,
        "draws_included": window,
        "top10_numbers": top10,
        "bottom10_numbers": bottom10,
        "avg_sum": avg_sum,
        "odd_even_ratio": odd_even_ratio,
        "most_common_range": most_common_range,
    }


# ─── SPEC-LOTTO-035: 번호 예약 (reservations) ───────────────────────────────

# SPEC-LOTTO-035: 번호 예약 저장 경로 (favorites.json과 동일 패턴)
_RESERVATIONS_PATH = settings.data_dir / "reservations.json"
# SPEC-LOTTO-035: 최대 예약 개수
_RESERVATIONS_MAX = 10


def get_reservations() -> list[dict[str, Any]]:
    """저장된 번호 예약 목록을 저장 순서대로 반환합니다 (SPEC-LOTTO-035).

    파일이 없거나 손상되어 있으면 빈 리스트를 반환한다.
    """
    if not _RESERVATIONS_PATH.exists():
        return []
    try:
        data = json.loads(_RESERVATIONS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read reservations.json: %s", exc, exc_info=True)
        return []
    if not isinstance(data, list):
        logger.warning("reservations.json 최상위가 list 아님 — 빈 목록 반환")
        return []
    return data


def save_reservations(reservations: list[dict[str, Any]]) -> None:
    """예약 목록을 원자적으로 저장합니다 (SPEC-LOTTO-035).

    임시 파일에 먼저 기록한 뒤 os.replace로 교체하여 쓰기 중단 시에도
    기존 파일이 손상되지 않도록 한다 (favorites와 동일 패턴).
    """
    _RESERVATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".reservations_", suffix=".json.tmp", dir=str(_RESERVATIONS_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(reservations, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _RESERVATIONS_PATH)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


# ─── SPEC-LOTTO-038: 통계 대규모 대시보드 (dashboard_overview) ───────────────

# SPEC-LOTTO-038: 범위 분포 5개 구간 (라벨 → (하한, 상한))
_DASHBOARD_RANGES: tuple[tuple[str, int, int], ...] = (
    ("1-9", 1, 9),
    ("10-19", 10, 19),
    ("20-29", 20, 29),
    ("30-39", 30, 39),
    ("40-45", 40, 45),
)


# @MX:NOTE: [AUTO] SPEC-LOTTO-038 — 전체 이력 통계 대시보드 단일 진입점 (단일 O(N) 패스)
# @MX:SPEC: SPEC-LOTTO-038
def dashboard_overview(draws: list[DrawResult] | None = _UNSET) -> dict[str, Any]:  # noqa: E501
    """전체 추첨 이력에서 7개 통계 요소를 단일 O(N) 패스로 집계합니다 (SPEC-LOTTO-038).

    Args:
        draws: 분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
               명시적 None 전달 시 데이터 없음으로 처리한다.

    반환 구조:
        - total_draws:        전체 회차 수
        - total_prize1_sum:   1등 당첨금 총합 (prize1Amount=None 제외)
        - number_frequency:   [{number, count}] 본번호 1~45 출현 빈도 (번호 오름차순, 보너스 제외)
        - highest_prize1_draw: {drwNo, date, prize1Amount} 최고 1등 회차 (동률=낮은 drwNo)
        - lowest_prize1_draw:  최저 1등 회차 (동률=낮은 drwNo, 없으면 None)
        - odd_even:           {"odd": 전체 홀수 개수, "even": 전체 짝수 개수}
        - range_distribution: {"1-9","10-19","20-29","30-39","40-45": 누적 번호 개수}
        - yearly_avg_prize:   [{year, avg_prize1, draws}] 연도 오름차순 (avg는 prize 있는 회차 평균)

    데이터 부재(None) 또는 빈 리스트인 경우 일관된 0/None/빈 리스트 구조를 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    # 빈/None 데이터에서도 키 셋이 일관되도록 0으로 초기화
    freq: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    range_dist: dict[str, int] = {label: 0 for label, _, _ in _DASHBOARD_RANGES}
    odd_total = 0
    even_total = 0

    if not draws:
        return {
            "total_draws": 0,
            "total_prize1_sum": 0,
            "number_frequency": [{"number": n, "count": 0} for n in range(1, 46)],
            "highest_prize1_draw": None,
            "lowest_prize1_draw": None,
            "odd_even": {"odd": 0, "even": 0},
            "range_distribution": range_dist,
            "yearly_avg_prize": [],
        }

    total_prize1_sum = 0
    highest: DrawResult | None = None
    lowest: DrawResult | None = None
    # 연도별 누적: year(str) → [prize 합계, prize 있는 회차 수, 전체 회차 수]
    yearly: dict[str, list[int]] = {}

    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)

        # 번호 빈도 / 홀짝 / 범위 분포 (단일 루프)
        for n in nums:
            freq[n] += 1
            if n % 2 == 1:
                odd_total += 1
            else:
                even_total += 1
            for label, lo, hi in _DASHBOARD_RANGES:
                if lo <= n <= hi:
                    range_dist[label] += 1
                    break

        # 연도별 회차 수 누적 (prize 유무 무관)
        year_key = str(draw.date.year)
        bucket = yearly.setdefault(year_key, [0, 0, 0])
        bucket[2] += 1

        # 1등 당첨금 집계 (None 제외)
        amount = draw.prize1Amount
        if amount is not None:
            total_prize1_sum += amount
            bucket[0] += amount
            bucket[1] += 1
            # 최고/최저 — 동률 시 낮은 drwNo 우선
            if highest is None or _prize_beats(draw, highest, want_max=True):
                highest = draw
            if lowest is None or _prize_beats(draw, lowest, want_max=False):
                lowest = draw

    number_frequency = [{"number": n, "count": freq[n]} for n in range(1, 46)]

    yearly_avg_prize = [
        {
            "year": year,
            "avg_prize1": int(bucket[0] // bucket[1]) if bucket[1] else 0,
            "draws": bucket[2],
        }
        for year, bucket in sorted(yearly.items())
    ]

    return {
        "total_draws": len(draws),
        "total_prize1_sum": total_prize1_sum,
        "number_frequency": number_frequency,
        "highest_prize1_draw": _draw_prize_payload(highest),
        "lowest_prize1_draw": _draw_prize_payload(lowest),
        "odd_even": {"odd": odd_total, "even": even_total},
        "range_distribution": range_dist,
        "yearly_avg_prize": yearly_avg_prize,
    }


def _prize_beats(candidate: DrawResult, current: DrawResult, want_max: bool) -> bool:
    """candidate가 current보다 최고/최저 자리에 적합한지 판정합니다 (SPEC-LOTTO-038).

    동률(prize 동일) 시에는 낮은 drwNo가 우선하므로, candidate.drwNo가
    더 작을 때만 교체한다. 호출자는 candidate.prize1Amount가 None이 아님을 보장한다.
    """
    c_amount = candidate.prize1Amount
    cur_amount = current.prize1Amount
    if c_amount == cur_amount:
        return candidate.drwNo < current.drwNo
    if want_max:
        return c_amount > cur_amount  # type: ignore[operator]
    return c_amount < cur_amount  # type: ignore[operator]


def _draw_prize_payload(draw: DrawResult | None) -> dict[str, Any] | None:
    """회차를 {drwNo, date, prize1Amount} 페이로드로 변환합니다 (None은 그대로 None)."""
    if draw is None:
        return None
    return {
        "drwNo": draw.drwNo,
        "date": str(draw.date),
        "prize1Amount": draw.prize1Amount,
    }


# ─── SPEC-LOTTO-041: 회차 구간 통계 (range_stats) ───────────────────────────


def _empty_range_stats(start_drw: int, end_drw: int) -> dict[str, Any]:
    """구간 통계의 일관된 빈 구조를 생성합니다 (SPEC-LOTTO-041 REQ-RANGE-011).

    start>end / 빈 데이터 / None / 매칭 회차 없음 모든 경우에서 동일 구조를 보장한다.
    """
    return {
        "start_drw": start_drw,
        "end_drw": end_drw,
        "total_draws": 0,
        "number_frequency": [{"number": n, "count": 0} for n in range(1, 46)],
        "odd_even": {"odd": 0, "even": 0},
        "range_distribution": {label: 0 for label, _, _ in _DASHBOARD_RANGES},
        "avg_prize1": None,
        "highest_prize1_draw": None,
        "lowest_prize1_draw": None,
    }


# @MX:NOTE: [AUTO] SPEC-LOTTO-041 — 지정 구간(start~end) 통계 단일 진입점 (단일 O(N) 패스)
# @MX:SPEC: SPEC-LOTTO-041 REQ-RANGE-001
def range_stats(
    start_drw: int,
    end_drw: int,
    draws: list[DrawResult] | None = _UNSET,
) -> dict[str, Any]:
    """지정한 회차 구간(start_drw ~ end_drw)의 통계를 집계합니다 (SPEC-LOTTO-041).

    drwNo >= start_drw AND drwNo <= end_drw 를 만족하는 회차만 대상으로
    번호 빈도/홀짝/번호대/1등 당첨금 통계를 단일 O(N) 패스로 산출한다.

    Args:
        start_drw: 구간 시작 회차 (포함)
        end_drw:   구간 끝 회차 (포함)
        draws:     분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
                   명시적 None 전달 시 데이터 없음으로 처리한다.

    반환 구조:
        - start_drw / end_drw:    요청 구간 (요청값 그대로 노출)
        - total_draws:            구간 내 회차 수
        - number_frequency:       [{number, count}] 본번호 1~45 (번호 오름차순, 보너스 제외)
        - odd_even:               {"odd", "even"} 구간 내 전체 홀/짝 개수
        - range_distribution:     {"1-9","10-19","20-29","30-39","40-45": 누적 번호 개수}
        - avg_prize1:             구간 내 1등 당첨금 정수 평균 (None 제외, 없으면 None)
        - highest_prize1_draw:    최고 1등 회차 {drwNo, date, prize1Amount} (동률=낮은 drwNo)
        - lowest_prize1_draw:     최저 1등 회차 (없으면 None)

    start>end / 빈 데이터(None) / 매칭 회차 없음인 경우 예외 없이
    일관된 빈 구조(total_draws=0, 모든 빈도 0, None 당첨금)를 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    # 역전 구간 또는 데이터 부재 → 빈 구조 (요청 구간은 그대로 노출)
    if not draws or start_drw > end_drw:
        return _empty_range_stats(start_drw, end_drw)

    in_range = [d for d in draws if start_drw <= d.drwNo <= end_drw]
    if not in_range:
        return _empty_range_stats(start_drw, end_drw)

    freq: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    range_dist: dict[str, int] = {label: 0 for label, _, _ in _DASHBOARD_RANGES}
    odd_total = 0
    even_total = 0
    prize_sum = 0
    prize_count = 0
    highest: DrawResult | None = None
    lowest: DrawResult | None = None

    for draw in in_range:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        for n in nums:
            freq[n] += 1
            if n % 2 == 1:
                odd_total += 1
            else:
                even_total += 1
            for label, lo, hi in _DASHBOARD_RANGES:
                if lo <= n <= hi:
                    range_dist[label] += 1
                    break

        amount = draw.prize1Amount
        if amount is not None:
            prize_sum += amount
            prize_count += 1
            # 최고/최저 — 동률 시 낮은 drwNo 우선 (SPEC-LOTTO-038 _prize_beats 재사용)
            if highest is None or _prize_beats(draw, highest, want_max=True):
                highest = draw
            if lowest is None or _prize_beats(draw, lowest, want_max=False):
                lowest = draw

    avg_prize1 = int(prize_sum // prize_count) if prize_count else None

    return {
        "start_drw": start_drw,
        "end_drw": end_drw,
        "total_draws": len(in_range),
        "number_frequency": [{"number": n, "count": freq[n]} for n in range(1, 46)],
        "odd_even": {"odd": odd_total, "even": even_total},
        "range_distribution": range_dist,
        "avg_prize1": avg_prize1,
        "highest_prize1_draw": _draw_prize_payload(highest),
        "lowest_prize1_draw": _draw_prize_payload(lowest),
    }


# ─── SPEC-LOTTO-039: 당첨번호 예측 리포트 (prediction_report) ────────────────

# SPEC-LOTTO-039: 복합 스코어 가중치 (합 1.0)
_W_FREQUENCY = 0.40
_W_INTERVAL = 0.30
_W_ODD_EVEN = 0.15
_W_RANGE = 0.15

# SPEC-LOTTO-039: 범위 점수용 5개 번호대 구간 (라벨 → (하한, 상한))
_PREDICT_RANGES: tuple[tuple[str, int, int], ...] = (
    ("1-9", 1, 9),
    ("10-19", 10, 19),
    ("20-29", 20, 29),
    ("30-39", 30, 39),
    ("40-45", 40, 45),
)
# SPEC-LOTTO-039: 상위 후보 반환 개수
_PREDICT_TOP_N = 10


def _clamp01(x: float) -> float:
    """값을 [0.0, 1.0] 범위로 제한합니다 (SPEC-LOTTO-039)."""
    return max(0.0, min(1.0, x))


# @MX:NOTE: [AUTO] SPEC-LOTTO-039 — 최근 recent_n 회차 복합 스코어링 예측 리포트
# @MX:SPEC: SPEC-LOTTO-039
def prediction_report(draws: list[DrawResult] | None = _UNSET, recent_n: int = 50) -> dict[str, Any]:  # noqa: ANN001, E501
    """최근 recent_n 회차를 4차원 복합 스코어로 분석해 예측 리포트를 생성합니다.

    각 번호(1~45)에 대해 빈도/간격/홀짝/범위 점수를 계산하고
    가중 합산한 composite_score로 상위 후보와 3개 추천 조합을 산출한다.

    Args:
        draws:    분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
                  명시적 None 전달 시 데이터 없음으로 처리한다.
        recent_n: 분석 대상 최근 회차 수. 가용 회차보다 크면 가용 전체를 사용한다.

    반환 구조:
        - recent_n:                  요청한 recent_n (가용 회차로 잘려도 요청값 그대로)
        - draws_analyzed:            실제 분석에 사용한 회차 수 = min(recent_n, len(draws))
        - weights:                   {frequency, interval, odd_even, range} 가중치
        - top_candidates:            [{number, composite_score, breakdown}] 상위 10개
                                     (composite_score 내림차순, 동률은 낮은 번호 우선)
        - recommended_combinations:  3개 조합 [{numbers, label}] (각 6개 오름차순)

    데이터 부재(None) 또는 빈 리스트인 경우 빈 후보/조합 구조를 반환한다.
    """
    weights = {
        "frequency": _W_FREQUENCY,
        "interval": _W_INTERVAL,
        "odd_even": _W_ODD_EVEN,
        "range": _W_RANGE,
    }

    if draws is _UNSET:
        draws = get_draws()

    if not draws:
        return {
            "recent_n": recent_n,
            "draws_analyzed": 0,
            "weights": weights,
            "top_candidates": [],
            "recommended_combinations": [],
        }

    # 최근 N회차 (drwNo 기준 정렬 후 뒤에서 recent_n개)
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    window = min(recent_n, len(sorted_draws))
    sample = sorted_draws[-window:]

    # 번호별 출현 횟수 / 마지막 출현 위치(샘플 내 인덱스)
    occurrences: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    last_seen_idx: dict[int, int] = {}
    odd_total = 0
    even_total = 0
    range_counts: dict[str, int] = {label: 0 for label, _, _ in _PREDICT_RANGES}

    for idx, d in enumerate(sample):
        for n in d.numbers():
            occurrences[n] += 1
            last_seen_idx[n] = idx
            if n % 2 == 1:
                odd_total += 1
            else:
                even_total += 1
            for label, lo, hi in _PREDICT_RANGES:
                if lo <= n <= hi:
                    range_counts[label] += 1
                    break

    sample_len = len(sample)
    max_occ = max(occurrences.values())

    # 간격(gap): 표본 마지막 인덱스 기준 마지막 출현 이후 경과 회차.
    # 미출현 번호는 gap = sample_len (최대 overdue).
    gaps: dict[int, int] = {}
    for n in range(1, 46):
        if n in last_seen_idx:
            gaps[n] = (sample_len - 1) - last_seen_idx[n]
        else:
            gaps[n] = sample_len
    max_gap = max(gaps.values())

    # 홀짝 점수: 소수 집단(less-frequent parity)이 1.0, 다수 집단 0.0, 동률 0.5
    if odd_total < even_total:
        odd_score_val, even_score_val = 1.0, 0.0
    elif even_total < odd_total:
        odd_score_val, even_score_val = 0.0, 1.0
    else:
        odd_score_val = even_score_val = 0.5

    # 범위 점수: 최소 표현 구간이 1.0, 나머지는 빈도 역수 정규화 [0,1]
    range_score_by_label = _compute_range_scores(range_counts)

    # 각 번호의 4차원 점수 + composite
    items: list[dict[str, Any]] = []
    for n in range(1, 46):
        freq_score = _clamp01(occurrences[n] / max_occ) if max_occ else 0.0
        interval_score = _clamp01(gaps[n] / max_gap) if max_gap else 0.0
        odd_even_score = odd_score_val if n % 2 == 1 else even_score_val
        range_score = _clamp01(range_score_by_label[_range_label(n)])

        composite = (
            _W_FREQUENCY * freq_score
            + _W_INTERVAL * interval_score
            + _W_ODD_EVEN * odd_even_score
            + _W_RANGE * range_score
        )
        items.append({
            "number": n,
            "composite_score": round(_clamp01(composite), 4),
            "breakdown": {
                "frequency": round(freq_score, 4),
                "interval": round(interval_score, 4),
                "odd_even": round(odd_even_score, 4),
                "range": round(range_score, 4),
            },
        })

    # 상위 후보 — composite 내림차순, 동률은 낮은 번호 우선
    ranked = sorted(items, key=lambda x: (-x["composite_score"], x["number"]))
    top_candidates = ranked[:_PREDICT_TOP_N]

    cand_numbers = [c["number"] for c in top_candidates]
    recommended_combinations = _build_prediction_combos(cand_numbers)

    return {
        "recent_n": recent_n,
        "draws_analyzed": window,
        "weights": weights,
        "top_candidates": top_candidates,
        "recommended_combinations": recommended_combinations,
    }


def _range_label(n: int) -> str:
    """번호를 _PREDICT_RANGES 구간 라벨로 변환합니다 (SPEC-LOTTO-039)."""
    for label, lo, hi in _PREDICT_RANGES:
        if lo <= n <= hi:
            return label
    return _PREDICT_RANGES[-1][0]


def _compute_range_scores(range_counts: dict[str, int]) -> dict[str, float]:
    """구간별 점수를 빈도 역수 정규화로 계산합니다 (SPEC-LOTTO-039).

    최소 표현 구간이 1.0, 최대 표현 구간이 0.0이 되도록 선형 반전한다.
    모든 구간 빈도가 동일하면 전 구간 1.0(가장 적게 나온 셈)으로 처리한다.
    """
    counts = list(range_counts.values())
    lo = min(counts)
    hi = max(counts)
    if hi == lo:
        return dict.fromkeys(range_counts, 1.0)
    span = hi - lo
    return {
        label: (hi - c) / span
        for label, c in range_counts.items()
    }


def _build_prediction_combos(cand_numbers: list[int]) -> list[dict[str, Any]]:
    """상위 후보 번호로 3개 추천 조합을 결정론적으로 생성합니다 (SPEC-LOTTO-039).

    - 조합1: 상위 0~5 (6개)
    - 조합2: 상위 0~4 + 7번째(인덱스 6) (후보 7개 이상일 때), 부족하면 가용 후보
    - 조합3: 상위 0~2 + 7~9번째(인덱스 6~8) (후보 9개 이상일 때)
    각 조합은 6개 고유 번호 오름차순(6-number lotto 불변식 우선).
    후보가 6개 미만이면 가능한 만큼 반환한다.
    """
    n = len(cand_numbers)

    combo1 = sorted(cand_numbers[0:6])

    # 후보 7개 이상이면 상위 5개 + 7번째(인덱스 6), 부족하면 상위 6개
    combo2 = (
        sorted(cand_numbers[0:5] + [cand_numbers[6]])
        if n >= 7  # noqa: PLR2004
        else sorted(cand_numbers[0:6])
    )

    # 후보 9개 이상이면 상위 3개 + 중위 3개(인덱스 6~8) = 6개 (6-number 불변식 유지)
    combo3 = (
        sorted(cand_numbers[0:3] + cand_numbers[6:9])
        if n >= 9  # noqa: PLR2004
        else sorted(cand_numbers[0:6])
    )

    return [
        {"numbers": combo1, "label": "조합 1"},
        {"numbers": combo2, "label": "조합 2"},
        {"numbers": combo3, "label": "조합 3"},
    ]


# ─── SPEC-LOTTO-040: 번호 비교 분석기 (compare_numbers) ─────────────────────

# SPEC-LOTTO-040: match_summary로 집계하는 일치 수준 (높은 수준부터)
_COMPARE_MATCH_LEVELS = (6, 5, 4, 3)
# SPEC-LOTTO-040: 3+ 일치 1회당 무작위 기대 확률
# = C(6,3)*C(39,3)/C(45,6) ≈ 0.018637 (3개 이상 일치를 근사한 3개 일치 확률)
_COMPARE_EXPECTED_3PLUS_RATE = 0.0186


def _compare_grade(match3plus: int, total_draws: int) -> str:
    """3개 이상 일치 비율을 무작위 기대치와 비교해 등급 문자열을 만듭니다 (SPEC-LOTTO-040).

    actual 비율이 기대치 이상이면 "상위 N%", 미만이면 "하위 N%"로 분류한다.
    N은 actual을 기대치로 정규화한 상대 백분율(0~100 클램프)이다.
    데이터가 없으면 비교 불가이므로 중립 라벨을 반환한다.
    """
    if total_draws <= 0:
        return "데이터 없음"
    actual = match3plus / total_draws
    expected = _COMPARE_EXPECTED_3PLUS_RATE
    if actual >= expected:
        # 기대치 대비 초과분을 0~100%로 환산 (기대치의 2배면 100%)
        pct = min(100, round((actual - expected) / expected * 100))
        return f"상위 {pct}%"
    pct = min(100, round((expected - actual) / expected * 100))
    return f"하위 {pct}%"


# @MX:NOTE: [AUTO] SPEC-LOTTO-040 — 입력 6개 번호를 전체 회차와 비교 (단일 O(N) 패스)
# @MX:SPEC: SPEC-LOTTO-040
def compare_numbers(
    numbers: list[int],
    draws: list[DrawResult] | None = _UNSET,
) -> dict[str, Any]:
    """입력 6개 번호를 전체 추첨 회차와 비교하여 분석 결과를 반환합니다 (SPEC-LOTTO-040).

    Args:
        numbers: 비교할 번호 6개. 정렬 후 응답에 노출한다 (검증은 API 레이어가 수행).
        draws:   분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
                 명시적 None 전달 시 데이터 없음으로 처리한다.

    반환 구조:
        - numbers:             정렬된 입력 번호
        - total_draws_checked: 비교에 사용한 전체 회차 수
        - match_summary:       {"6"/"5"/"4"/"3": {count, draws:[{drwNo, date}]}}
                               (일치는 본번호 6개 기준, 보너스 제외)
        - number_frequency:    [{number, count, rank}] 입력 번호 오름차순,
                               rank는 count 내림차순(동률은 같은 rank) 1-based
        - grade:               3개 이상 일치 비율 기반 "상위/하위 N%" 등급

    데이터 부재(None) 또는 빈 리스트인 경우 일관된 0 구조를 반환한다.
    """
    sorted_input = sorted(numbers)
    input_set = set(sorted_input)

    if draws is _UNSET:
        draws = get_draws()

    # 일치 수준별 집계 컨테이너 (빈/None 데이터에서도 키 일관)
    match_summary: dict[str, dict[str, Any]] = {
        str(level): {"count": 0, "draws": []} for level in _COMPARE_MATCH_LEVELS
    }
    # 입력 번호별 전체 출현 횟수 (본번호 기준)
    freq: dict[int, int] = dict.fromkeys(sorted_input, 0)

    if not draws:
        number_frequency = [
            {"number": n, "count": 0, "rank": 1} for n in sorted_input
        ]
        return {
            "numbers": sorted_input,
            "total_draws_checked": 0,
            "match_summary": match_summary,
            "number_frequency": number_frequency,
            "grade": _compare_grade(0, 0),
        }

    match3plus = 0
    for draw in draws:
        draw_nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        draw_set = set(draw_nums)
        matched = len(input_set & draw_set)
        # 입력 번호 빈도 누적
        for n in sorted_input:
            if n in draw_set:
                freq[n] += 1
        # 일치 수준 집계 (3~6만)
        if matched >= 3:  # noqa: PLR2004
            match3plus += 1
            bucket = match_summary[str(matched)]
            bucket["count"] += 1
            bucket["draws"].append({"drwNo": draw.drwNo, "date": str(draw.date)})

    # 각 수준 회차 목록은 최신 회차 우선 정렬
    for level in match_summary.values():
        level["draws"].sort(key=lambda d: d["drwNo"], reverse=True)

    # 번호 빈도 랭크 — count 내림차순(동률은 동일 rank), 응답은 번호 오름차순
    distinct_counts = sorted({freq[n] for n in sorted_input}, reverse=True)
    rank_by_count = {c: i + 1 for i, c in enumerate(distinct_counts)}
    number_frequency = [
        {"number": n, "count": freq[n], "rank": rank_by_count[freq[n]]}
        for n in sorted_input
    ]

    return {
        "numbers": sorted_input,
        "total_draws_checked": len(draws),
        "match_summary": match_summary,
        "number_frequency": number_frequency,
        "grade": _compare_grade(match3plus, len(draws)),
    }


# ─── SPEC-LOTTO-042: 번호 추이 트래커 (number_trend) ─────────────────────────


# @MX:NOTE: [AUTO] SPEC-LOTTO-042 — 선택 번호(1~3개)의 최근 N회 출현 타임라인 + 간격 분석
# @MX:SPEC: SPEC-LOTTO-042 REQ-TREND-T-001
def number_trend(
    numbers: list[int],
    recent_n: int = 100,
    draws: list[DrawResult] | None = _UNSET,
) -> dict[str, Any]:
    """선택 번호의 최근 recent_n 회차 출현 타임라인과 간격 통계를 산출합니다 (SPEC-LOTTO-042).

    최신 recent_n 회차를 윈도로 잡고, 각 번호에 대해 회차별 출현 여부(timeline)와
    출현 간격(avg_gap/current_gap)을 시간 오름차순으로 계산한다.
    출현 판정은 본번호 6개 기준이며 보너스 번호는 포함하지 않는다.

    Args:
        numbers:  추적할 번호 1~3개 (범위/개수 검증은 API 레이어가 수행).
        recent_n: 분석 대상 최신 회차 수. 가용 회차보다 크면 가용 전체를 사용한다.
        draws:    분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
                  명시적 None 전달 시 데이터 없음으로 처리한다.

    반환 구조:
        - recent_n:       요청한 recent_n (윈도가 잘려도 요청값 그대로 노출)
        - draws_analyzed: 실제 분석에 사용한 회차 수 = min(recent_n, len(draws))
        - numbers:        [{number, total_appearances, avg_gap, last_appeared_drwNo,
                            current_gap, timeline}] 입력 순서 유지
            - timeline:   [{drwNo, date, appeared}] 시간 오름차순 (윈도 길이만큼)
            - avg_gap:    연속 출현 위치 간격 평균 (소수 1자리, 2회 미만이면 None)
            - current_gap: 윈도 마지막 회차 기준 마지막 출현 이후 경과 회차 수
                           (최신 회차 출현 시 0, 미출현 시 draws_analyzed)

    데이터 부재(None/빈 리스트) 또는 잘못된 번호 입력(빈 리스트)인 경우 예외 없이
    {"recent_n": recent_n, "draws_analyzed": 0, "numbers": []} 를 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    # 데이터 부재 또는 추적 번호 없음 → 빈 구조 (요청 recent_n은 그대로 노출)
    if not draws or not numbers:
        return {"recent_n": recent_n, "draws_analyzed": 0, "numbers": []}

    # 최신 recent_n 회차 (drwNo 기준 정렬 후 뒤에서 recent_n개 — 시간 오름차순 유지)
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    window = min(recent_n, len(sorted_draws))
    sample = sorted_draws[-window:]

    # 각 회차의 본번호 집합을 미리 계산 (번호별 루프에서 재사용)
    draw_number_sets = [set(d.numbers()) for d in sample]
    last_idx = window - 1

    entries: list[dict[str, Any]] = []
    for num in numbers:
        timeline: list[dict[str, Any]] = []
        appeared_positions: list[int] = []
        for idx, draw in enumerate(sample):
            appeared = num in draw_number_sets[idx]
            if appeared:
                appeared_positions.append(idx)
            timeline.append({
                "drwNo": draw.drwNo,
                "date": str(draw.date),
                "appeared": appeared,
            })

        total_appearances = len(appeared_positions)

        # 평균 간격 — 연속 출현 위치 차이의 평균 (2회 미만이면 None)
        if total_appearances >= 2:  # noqa: PLR2004
            gaps = [
                appeared_positions[i + 1] - appeared_positions[i]
                for i in range(total_appearances - 1)
            ]
            avg_gap: float | None = round(sum(gaps) / len(gaps), 1)
        else:
            avg_gap = None

        # 마지막 출현 회차 / 현재 간격
        if appeared_positions:
            last_pos = appeared_positions[-1]
            last_appeared = sample[last_pos].drwNo
            current_gap = last_idx - last_pos
        else:
            last_appeared = None
            # 미출현 → 윈도 전체를 미출현한 것으로 본다
            current_gap = window

        entries.append({
            "number": num,
            "total_appearances": total_appearances,
            "avg_gap": avg_gap,
            "last_appeared_drwNo": last_appeared,
            "current_gap": current_gap,
            "timeline": timeline,
        })

    return {
        "recent_n": recent_n,
        "draws_analyzed": window,
        "numbers": entries,
    }


# ─── SPEC-LOTTO-043: 연속 번호 패턴 분석 (consecutive_pattern) ───────────────

# SPEC-LOTTO-043: most_common_pairs 반환 최대 개수
_CONSEC_TOP_PAIRS = 10
# SPEC-LOTTO-043: run_length_distribution 키 (길이 2~6)
_CONSEC_RUN_LENGTHS = (2, 3, 4, 5, 6)


def _empty_consecutive_pattern() -> dict[str, Any]:
    """연속 패턴 분석의 일관된 빈 구조를 생성합니다 (SPEC-LOTTO-043 REQ-CONSEC-030).

    빈 데이터 / None / 빈 윈도 모든 경우에서 동일 구조를 보장한다.
    """
    return {
        "total_draws": 0,
        "draws_with_consecutive": 0,
        "consecutive_ratio": 0.0,
        "run_length_distribution": {str(length): 0 for length in _CONSEC_RUN_LENGTHS},
        "max_run_length": 0,
        "most_common_pairs": [],
        "draws_without_consecutive": 0,
    }


# @MX:NOTE: [AUTO] SPEC-LOTTO-043 — 연속 번호 패턴 분석 단일 진입점 (단일 O(N) 패스)
# @MX:SPEC: SPEC-LOTTO-043 REQ-CONSEC-001
def consecutive_pattern(
    draws: list[DrawResult] | None = _UNSET,
    recent_n: int | None = None,
) -> dict[str, Any]:
    """역대 당첨번호의 연속 번호 패턴을 집계합니다 (SPEC-LOTTO-043).

    각 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이가 1인 연속 런을
    탐지하여 런 길이 분포·연속 비율·최장 런·연속 쌍 빈도를 산출한다.

    Args:
        draws:    분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
                  명시적 None 전달 시 데이터 없음으로 처리한다.
        recent_n: 분석 대상 최신 회차 수. None이면 전체, 지정 시 최신 N회차.
                  가용 회차보다 크면 가용 전체를 사용한다.

    반환 구조:
        - total_draws:             분석 회차 수
        - draws_with_consecutive:  길이 2 이상 런을 하나라도 포함한 회차 수
        - consecutive_ratio:       draws_with_consecutive / total_draws (소수 4자리, 없으면 0.0)
        - run_length_distribution: {"2".."6": 해당 길이 런의 개수 (전체 회차 누적)}
        - max_run_length:          관측된 가장 긴 연속 런의 길이 (없으면 0)
        - most_common_pairs:       [{pair, count}] 연속 인접 쌍 상위 10개
                                   (count 내림차순, 동률은 라벨 오름차순)
        - draws_without_consecutive: 연속 런을 전혀 포함하지 않은 회차 수

    데이터 부재(None) 또는 빈 리스트인 경우 예외 없이 일관된 빈 구조를 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    if not draws:
        return _empty_consecutive_pattern()

    # recent_n 지정 시 최신 N회차로 윈도 제한 (drwNo 기준 정렬 후 뒤에서 N개)
    if recent_n is not None:
        sorted_draws = sorted(draws, key=lambda d: d.drwNo)
        window = min(recent_n, len(sorted_draws))
        target = sorted_draws[-window:]
    else:
        target = list(draws)

    run_length_distribution: dict[str, int] = {
        str(length): 0 for length in _CONSEC_RUN_LENGTHS
    }
    pair_counts: dict[str, int] = {}
    draws_with_consecutive = 0
    draws_without_consecutive = 0
    max_run_length = 0

    for draw in target:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        runs = _find_consecutive_runs(nums)

        if runs:
            draws_with_consecutive += 1
        else:
            draws_without_consecutive += 1

        for run in runs:
            length = len(run)
            run_length_distribution[str(length)] += 1
            max_run_length = max(max_run_length, length)
            # 런 내부의 (length-1)개 인접 쌍을 모두 집계
            for i in range(length - 1):
                pair_label = f"{run[i]}-{run[i + 1]}"
                pair_counts[pair_label] = pair_counts.get(pair_label, 0) + 1

    total_draws = len(target)
    consecutive_ratio = (
        round(draws_with_consecutive / total_draws, 4) if total_draws else 0.0
    )

    # 연속 쌍 top10 — count 내림차순, 동률은 라벨 오름차순
    most_common_pairs = [
        {"pair": pair, "count": count}
        for pair, count in sorted(
            pair_counts.items(), key=lambda x: (-x[1], x[0])
        )[:_CONSEC_TOP_PAIRS]
    ]

    return {
        "total_draws": total_draws,
        "draws_with_consecutive": draws_with_consecutive,
        "consecutive_ratio": consecutive_ratio,
        "run_length_distribution": run_length_distribution,
        "max_run_length": max_run_length,
        "most_common_pairs": most_common_pairs,
        "draws_without_consecutive": draws_without_consecutive,
    }


def _find_consecutive_runs(nums: list[int]) -> list[list[int]]:
    """정렬된 번호 리스트에서 길이 2 이상의 연속 런 목록을 반환합니다 (SPEC-LOTTO-043).

    인접 차이가 1인 번호들을 묶어 런으로 만들고, 길이 1(단독)은 제외한다.
    예) [3,4,5,18,33,40] → [[3,4,5]] / [7,8,19,20,41,45] → [[7,8],[19,20]]
    """
    runs: list[list[int]] = []
    current: list[int] = [nums[0]] if nums else []
    for i in range(1, len(nums)):
        if nums[i] - nums[i - 1] == 1:
            current.append(nums[i])
        else:
            if len(current) >= 2:  # noqa: PLR2004
                runs.append(current)
            current = [nums[i]]
    if len(current) >= 2:  # noqa: PLR2004
        runs.append(current)
    return runs


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
