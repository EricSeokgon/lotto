"""데이터 접근 레이어 — 기존 lotto 모듈을 래핑하는 읽기 전용 함수들.

# @MX:ANCHOR: [AUTO] 웹 대시보드의 핵심 데이터 접근 게이트웨이
# @MX:REASON: pages.py, api.py, app.py 등 다수 모듈에서 호출됨
"""

from __future__ import annotations

import contextlib
import datetime
import itertools
import json
import logging
import math
import os
import tempfile

# SPEC-LOTTO-045: 명시적 재노출(redundant-alias). 테스트가 모듈 네임스페이스
# (lotto.web.data.time)로 time.time을 패치하므로 명시적 재노출로 처리한다 (런타임 동작 무관).
import time as time
import warnings
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

# SPEC-LOTTO-052 REQ-BT-008/011/014: 백테스트 결과 메모리 캐시 (n_past 별 키).
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_backtest_cache: dict[int, dict[str, Any]] = {}

# SPEC-LOTTO-053 REQ-CO-013/020: 동시 출현 행렬 메모리 캐시 (단일 엔트리).
# 요청당 1회만 행렬을 구성하고 top/partner는 이 행렬에서 파생한다(REQ-CO-019).
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_cooccurrence_cache: dict[tuple[int, int], int] | None = None

# SPEC-LOTTO-054 REQ-RW-015/023: 롤링 윈도우 빈도 결과 메모리 캐시.
# 요청 windows 튜플(정렬)을 키로 결과를 보관하여 동일 요청의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_rolling_cache: dict[tuple[int, ...], dict[int, dict[str, Any]]] = {}

# SPEC-LOTTO-055 REQ-LD-022: 끝자리 분포 결과 메모리 캐시 (단일 엔트리, 키 불필요).
# 전체 이력에 대한 끝자리 통계는 입력이 고정되므로 단일 결과만 보관한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_last_digit_cache: dict[int, dict[str, Any]] | None = None

# SPEC-LOTTO-056: 번호 간격 패턴 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_gap_cache: dict[str, Any] = {}

# SPEC-LOTTO-057: AC값(산술 복잡도) 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_ac_cache: dict[str, Any] = {}

# SPEC-LOTTO-058: 소수/합성수 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_prime_cache: dict[str, Any] = {}

# SPEC-LOTTO-059: 십의 자리 구간 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_decade_cache: dict[str, Any] = {}

# SPEC-LOTTO-060: 홀짝 비율 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_odd_even_cache: dict[str, Any] = {}

# SPEC-LOTTO-061: 고저 비율 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_high_low_cache: dict[str, Any] = {}

# SPEC-LOTTO-062: 연속 번호 패턴 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_consecutive_cache: dict[str, Any] = {}

# SPEC-LOTTO-063: 끝자리 합계 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_last_digit_sum_cache: dict[str, Any] = {}

# SPEC-LOTTO-064: 최솟값·최댓값 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_min_max_cache: dict[str, Any] = {}

# SPEC-LOTTO-065: 번호 표준편차(모표준편차) 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_std_cache: dict[str, Any] = {}

# SPEC-LOTTO-066: 소수합 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_prime_sum_cache: dict[str, Any] = {}

# SPEC-LOTTO-067: 번호 총합 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_total_sum_cache: dict[str, Any] = {}

# SPEC-LOTTO-068: 번호 구간별 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_range_dist_cache: dict[str, Any] = {}

# SPEC-LOTTO-069: 연속번호 패턴(연속 쌍) 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
# SPEC-062의 _consecutive_cache 와는 별개의 독립 네임스페이스다.
_consecutive_pairs_cache: dict[str, Any] = {}

# SPEC-LOTTO-069: 회차당 연속 쌍 개수를 분류하는 4개 고정 버킷.
# "3+" 는 3개 이상을 모두 합치는 오버플로 버킷이다.
_CONSECUTIVE_BUCKETS = ["0", "1", "2", "3+"]

# SPEC-LOTTO-070: AC값(산술 복잡도) 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_ac_value_cache: dict[str, Any] = {}

# SPEC-LOTTO-070: AC값 분포 키. "0".."14" 15개 고정.
# AC>=14 회차는 "14" 오버플로 버킷에 합산한다(min(ac, 14)).
_AC_KEYS = [str(i) for i in range(15)]

# SPEC-LOTTO-070: 고다양성(high diversity) 판정 임계값(AC>=9).
_AC_DIVERSITY_THRESHOLD = 9

# SPEC-LOTTO-071: 번호 중앙값(median) 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_median_cache: dict[str, Any] = {}

# SPEC-LOTTO-071: 중앙값 분포 키. "1-5".."41-45" 9개 고정.
# 경계값은 상위 버킷에 귀속한다(예: 5.5 → "6-10").
_MEDIAN_KEYS = [
    "1-5", "6-10", "11-15", "16-20", "21-25",
    "26-30", "31-35", "36-40", "41-45",
]

# SPEC-LOTTO-071: 저중앙값(low median) 판정 임계값(median < 23.0 strict).
_MEDIAN_CENTER = 23.0

# SPEC-LOTTO-072: 끝자리 유니크 수 분포 분석 결과 메모리 캐시.
# draws 길이(str)를 키로 결과를 보관하여 동일 입력의 재계산을 피한다.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_last_digit_unique_cache: dict[str, Any] = {}

# SPEC-LOTTO-072: 유니크 끝자리 개수 분포 키. "1".."6" 6개 고정.
# 한 회차 본번호 6개의 서로 다른 끝자리 개수(1~6)에 대응하며 미관측은 zero-fill.
_UNIQUE_DIGIT_KEYS = ["1", "2", "3", "4", "5", "6"]

# SPEC-LOTTO-073: 3의 배수 포함 개수 분포 캐시.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_mult3_cache: dict[str, Any] = {}

# SPEC-LOTTO-073: 3의 배수 포함 개수 분포 키. "0".."6" 7개 고정.
# 한 회차 본번호 6개 중 3으로 나누어 떨어지는 개수(0~6)에 대응하며 미관측은 zero-fill.
_MULT3_KEYS = ["0", "1", "2", "3", "4", "5", "6"]

# SPEC-LOTTO-074: 짝수 포함 개수 분포 캐시.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_even_count_cache: dict[str, Any] = {}

# SPEC-LOTTO-074: 짝수 포함 개수 분포 키. "0".."6" 7개 고정.
# 한 회차 본번호 6개 중 짝수(2의 배수) 개수(0~6)에 대응하며 미관측은 zero-fill.
_EVEN_COUNT_KEYS = ["0", "1", "2", "3", "4", "5", "6"]

# SPEC-LOTTO-075: 5의 배수 포함 개수 분포 캐시.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_mult5_cache: dict[str, Any] = {}

# SPEC-LOTTO-075: 5의 배수 포함 개수 분포 키. "0".."6" 7개 고정.
# 한 회차 본번호 6개 중 5의 배수(5,10,...,45) 개수(0~6)에 대응하며 미관측은 zero-fill.
_MULT5_KEYS = ["0", "1", "2", "3", "4", "5", "6"]

# SPEC-LOTTO-076: 4의 배수 포함 개수 분포 캐시.
# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_mult4_cache: dict[str, Any] = {}

# SPEC-LOTTO-076: 4의 배수 포함 개수 분포 키. "0".."6" 7개 고정.
# 한 회차 본번호 6개 중 4의 배수(4,8,...,44) 개수(0~6)에 대응하며 미관측은 zero-fill.
_MULT4_KEYS = ["0", "1", "2", "3", "4", "5", "6"]

# DB/디스크 영속화 없이 프로세스 수명 동안만 유지하며, invalidate_cache로 무효화된다.
_single_digit_cache: dict[str, Any] = {}

# SPEC-LOTTO-077: 1자리 포함 개수 분포 키. "0".."6" 7개 고정.
# 한 회차 본번호 6개 중 1자리 번호(1~9) 개수(0~6)에 대응하며 미관측은 zero-fill.
_SINGLE_DIGIT_KEYS = ["0", "1", "2", "3", "4", "5", "6"]

# SPEC-LOTTO-077: 1자리 번호 집합. 1~45 중 1자리는 {1,2,3,4,5,6,7,8,9} 9개.
_SINGLE_DIGIT_SET = {1, 2, 3, 4, 5, 6, 7, 8, 9}

# SPEC-LOTTO-078: 3연속 이상 묶음 수 분포 키. "0","1","2" 3개 고정.
# 한 회차 본번호 6개에서 3개 이상 연속한 묶음 수는 최대 2개(3+3=6)이며 미관측은 zero-fill.
_TRIPLE_RUN_KEYS = ["0", "1", "2"]

# SPEC-LOTTO-078: 3연속 묶음 분포 캐시. invalidate_cache로 무효화.
_triple_run_cache: dict[str, Any] = {}

# SPEC-LOTTO-079: 끝자리(일의 자리) 합계 구간 분포 키. 6개 고정 버킷.
# 한 회차 본번호 6개 끝자리 합(0~54)을 다음 6개 구간으로 분류하며 미관측은 zero-fill.
_DIGIT_SUM_KEYS = ["0-9", "10-14", "15-19", "20-24", "25-29", "30+"]

# SPEC-LOTTO-079: 끝자리 합계 구간 분포 캐시. invalidate_cache로 무효화.
_digit_sum_dist_cache: dict[str, Any] = {}

# SPEC-LOTTO-080: 번호 간격 최대값(max_gap) 구간 분포 키. 6개 고정 버킷.
# 한 회차 정렬 본번호 6개의 인접 차이 5개 중 최댓값을 다음 6개 구간으로 분류하며
# 미관측은 zero-fill.
_MAX_GAP_KEYS = ["1-5", "6-10", "11-15", "16-20", "21-30", "31+"]

# SPEC-LOTTO-080: 번호 간격 최대값 구간 분포 캐시. invalidate_cache로 무효화.
_max_gap_dist_cache: dict[str, Any] = {}

# SPEC-LOTTO-081: 짝수 연속 묶음(간격=2) 수 분포 키. 4개 고정.
# 본번호 6개가 모두 짝수일 때 최대 묶음 수는 3개이므로 "0"~"3" 4개 키.
_EVEN_RUN_KEYS = ["0", "1", "2", "3"]

# SPEC-LOTTO-081: 짝수 연속 포함 분포 캐시. invalidate_cache로 무효화.
_even_run_cache: dict[str, Any] = {}

# SPEC-LOTTO-082: 10단위 다양성 분포 캐시. invalidate_cache로 무효화.
_decade_div_cache: dict[str, Any] = {}

# SPEC-LOTTO-083: 홀수 연속 묶음(간격=2) 수 분포 키. 4개 고정.
# 본번호 6개가 모두 홀수일 때 최대 묶음 수는 3개이므로 "0"~"3" 4개 키.
_ODD_RUN_KEYS = ["0", "1", "2", "3"]

# SPEC-LOTTO-083: 홀수 연속 포함 분포 캐시. invalidate_cache로 무효화.
_odd_run_cache: dict[str, Any] = {}


def invalidate_cache() -> None:
    """get_draws/get_stats/백테스트/동시출현/롤링의 메모리 캐시를 비웁니다.

    SPEC-LOTTO-009 REQ-CACHE-003: 데이터 수집/분석/크롤링 완료 후 호출됩니다.
    SPEC-LOTTO-052 REQ-BT-011: 신규 추첨 데이터 적재 시 백테스트 캐시도 무효화한다.
    SPEC-LOTTO-053 REQ-CO-013: 신규 추첨 데이터 적재 시 동시출현 캐시도 무효화한다.
    SPEC-LOTTO-054 REQ-RW-015: 신규 추첨 데이터 적재 시 롤링 윈도우 캐시도 무효화한다.
    SPEC-LOTTO-055 REQ-LD-014: 신규 추첨 데이터 적재 시 끝자리 분포 캐시도 무효화한다.
    SPEC-LOTTO-056: 신규 추첨 데이터 적재 시 간격 패턴 캐시도 무효화한다.
    SPEC-LOTTO-057: 신규 추첨 데이터 적재 시 AC값 분석 캐시도 무효화한다.
    SPEC-LOTTO-058: 신규 추첨 데이터 적재 시 소수/합성수 분포 캐시도 무효화한다.
    SPEC-LOTTO-059: 신규 추첨 데이터 적재 시 십의 자리 구간 분포 캐시도 무효화한다.
    SPEC-LOTTO-060: 신규 추첨 데이터 적재 시 홀짝 비율 분석 캐시도 무효화한다.
    SPEC-LOTTO-061: 신규 추첨 데이터 적재 시 고저 비율 분석 캐시도 무효화한다.
    SPEC-LOTTO-062: 신규 추첨 데이터 적재 시 연속 번호 패턴 분석 캐시도 무효화한다.
    SPEC-LOTTO-063: 신규 추첨 데이터 적재 시 끝자리 합계 분석 캐시도 무효화한다.
    SPEC-LOTTO-064: 신규 추첨 데이터 적재 시 최솟값·최댓값 분석 캐시도 무효화한다.
    SPEC-LOTTO-065: 신규 추첨 데이터 적재 시 표준편차 분석 캐시도 무효화한다.
    SPEC-LOTTO-066: 신규 추첨 데이터 적재 시 소수합 분포 캐시도 무효화한다.
    SPEC-LOTTO-067: 신규 추첨 데이터 적재 시 번호 총합 분포 캐시도 무효화한다.
    SPEC-LOTTO-068: 신규 추첨 데이터 적재 시 번호 구간별 분포 캐시도 무효화한다.
    SPEC-LOTTO-069: 신규 추첨 데이터 적재 시 연속 쌍 분석 캐시도 무효화한다.
    SPEC-LOTTO-070: 신규 추첨 데이터 적재 시 AC값 분포 분석 캐시도 무효화한다.
    SPEC-LOTTO-071: 신규 추첨 데이터 적재 시 중앙값 분포 분석 캐시도 무효화한다.
    SPEC-LOTTO-072: 신규 추첨 데이터 적재 시 끝자리 유니크 수 분포 캐시도 무효화한다.
    SPEC-LOTTO-073: 신규 추첨 데이터 적재 시 3의 배수 포함 개수 분포 캐시도 무효화한다.
    SPEC-LOTTO-074: 신규 추첨 데이터 적재 시 짝수 포함 개수 분포 캐시도 무효화한다.
    SPEC-LOTTO-075: 신규 추첨 데이터 적재 시 5의 배수 포함 개수 분포 캐시도 무효화한다.
    SPEC-LOTTO-076: 신규 추첨 데이터 적재 시 4의 배수 포함 개수 분포 캐시도 무효화한다.
    SPEC-LOTTO-077: 신규 추첨 데이터 적재 시 1자리 포함 개수 분포 캐시도 무효화한다.
    SPEC-LOTTO-078: 신규 추첨 데이터 적재 시 3연속 묶음 분포 캐시도 무효화한다.
    SPEC-LOTTO-079: 신규 추첨 데이터 적재 시 끝자리 합계 분포 캐시도 무효화한다.
    SPEC-LOTTO-081: 신규 추첨 데이터 적재 시 짝수 연속 포함 분포 캐시도 무효화한다.
    SPEC-LOTTO-082: 신규 추첨 데이터 적재 시 10단위 다양성 분포 캐시도 무효화한다.
    SPEC-LOTTO-083: 신규 추첨 데이터 적재 시 홀수 연속 포함 분포 캐시도 무효화한다.
    """
    global _draws_cache, _stats_cache, _cooccurrence_cache, _last_digit_cache  # noqa: PLW0603 — 모듈 레벨 캐시는 의도된 전역 상태
    _draws_cache = None
    _stats_cache = None
    _cooccurrence_cache = None
    _last_digit_cache = None
    _backtest_cache.clear()
    _rolling_cache.clear()
    _gap_cache.clear()
    _ac_cache.clear()
    _prime_cache.clear()
    _decade_cache.clear()
    _odd_even_cache.clear()
    _high_low_cache.clear()
    _consecutive_cache.clear()
    _last_digit_sum_cache.clear()
    _min_max_cache.clear()
    _std_cache.clear()
    _prime_sum_cache.clear()
    _total_sum_cache.clear()
    _range_dist_cache.clear()
    _consecutive_pairs_cache.clear()
    _ac_value_cache.clear()
    _median_cache.clear()
    _last_digit_unique_cache.clear()
    _mult3_cache.clear()
    _even_count_cache.clear()
    _mult5_cache.clear()
    _mult4_cache.clear()
    _single_digit_cache.clear()
    _triple_run_cache.clear()
    _digit_sum_dist_cache.clear()
    _max_gap_dist_cache.clear()
    _even_run_cache.clear()
    _decade_div_cache.clear()
    _odd_run_cache.clear()


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


# ─── SPEC-LOTTO-051: 교차 전략 합의 오버레이 (cross-strategy consensus) ───────


# @MX:NOTE: [AUTO] SPEC-LOTTO-051 — 11개 전략을 1회 스캔하여 번호별 합의 카운트 산출
# @MX:SPEC: SPEC-LOTTO-051 REQ-CONS-001, REQ-CONS-002, REQ-CONS-011
def get_cross_strategy_consensus(
    recommender: Any,  # noqa: ANN401 — LottoRecommender 또는 동일 인터페이스 스파이를 허용
    target_numbers: list[int],
) -> dict[int, int]:
    """target_numbers 각 번호가 11개 전략 중 몇 개에서 추천되는지 집계합니다.

    SPEC-LOTTO-051 읽기 전용 합의 오버레이. recommender.recommend_by_strategy(label)를
    STRATEGY_LABELS마다 정확히 1회씩(총 11회) 호출하여, 각 전략이 추천한 6개 번호
    집합에 target_numbers의 번호가 포함되는지 카운트한다. recommender 내부 점수나
    원시 draws에는 접근하지 않는다 (레이어 분리).

    Args:
        recommender: recommend_by_strategy(label) -> Recommendation 인터페이스 객체.
        target_numbers: 합의를 계산할 번호 목록. 빈 리스트면 빈 매핑을 반환한다.

    Returns:
        {number: count} 매핑. target_numbers의 모든 번호를 키로 가지며, 값은 0~11.
        target_numbers에 없는 번호는 키에 포함되지 않는다.
    """
    from lotto.recommender import STRATEGY_LABELS

    # 빈 입력은 11회 스캔 없이 조기 반환 (불필요한 추천 호출 회피)
    if not target_numbers:
        return {}

    target_set = set(target_numbers)
    consensus: dict[int, int] = dict.fromkeys(target_numbers, 0)

    # 전략당 1회 호출 — 추천 6개 중 target에 속한 번호의 카운트를 누적
    for label in STRATEGY_LABELS:
        recommended = set(recommender.recommend_by_strategy(label).numbers)
        for n in target_set & recommended:
            consensus[n] += 1

    return consensus


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


# ─── SPEC-LOTTO-048: 시뮬레이션 결과 저장/비교 (sim_history) ──────────────────

# SPEC-LOTTO-048: 저장된 시뮬레이션 결과 경로 (favorites.json과 동일 패턴)
_SIM_HISTORY_PATH = settings.data_dir / "sim_history.json"
# SPEC-LOTTO-048: 최대 보관 건수 (오래된 것부터 제거)
_SIM_HISTORY_MAX = 50


def list_simulation_results() -> list[dict[str, Any]]:
    """저장된 시뮬레이션 결과를 최신순(newest-first)으로 반환합니다 (SPEC-LOTTO-048).

    파일이 없거나 손상되어 있으면 빈 리스트를 반환한다. 저장은 추가 순서로
    이루어지므로 최신 항목이 앞에 오도록 역순으로 반환한다.
    """
    if not _SIM_HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(_SIM_HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read sim_history.json: %s", exc, exc_info=True)
        return []
    if not isinstance(data, list):
        logger.warning("sim_history.json 최상위가 list 아님 — 빈 목록 반환")
        return []
    # 저장 순서의 역순(최신 우선)
    return list(reversed(data))


def _write_sim_history(results: list[dict[str, Any]]) -> None:
    """시뮬레이션 결과 목록을 원자적으로 저장합니다 (SPEC-LOTTO-048).

    임시 파일에 먼저 기록한 뒤 os.replace로 교체하여 쓰기 중단 시에도
    기존 파일이 손상되지 않도록 한다 (favorites/reservations와 동일 패턴).
    저장 순서(오래된 것 → 최신)로 보존한다.
    """
    _SIM_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".sim_history_", suffix=".json.tmp", dir=str(_SIM_HISTORY_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _SIM_HISTORY_PATH)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


# @MX:NOTE: [AUTO] SPEC-LOTTO-048 — 시뮬레이션 결과를 라벨과 함께 영속 저장
# @MX:SPEC: SPEC-LOTTO-048
def save_simulation_result(entry: dict[str, Any]) -> dict[str, Any]:
    """시뮬레이션 결과 1건을 라벨과 함께 저장하고 부여된 엔트리를 반환합니다.

    - id(8자리 hex)와 created_at(UTC ISO-8601)을 서버에서 부여한다.
    - 최근 _SIM_HISTORY_MAX 건만 유지하며 초과 시 오래된 것부터 제거한다.
    - 저장 순서(오래된 것 → 최신)로 디스크에 보존하되, 반환값은 입력 필드를
      포함한 저장 엔트리(dict)다.
    """
    import uuid

    saved: dict[str, Any] = dict(entry)
    saved["id"] = uuid.uuid4().hex[:8]
    # SPEC-LOTTO-048: UTC ISO-8601 (Python 3.9 호환)
    saved["created_at"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()  # noqa: UP017

    # 디스크는 저장 순서(오래된 것 → 최신)로 보관하므로 reversed로 되돌린다
    stored = list(reversed(list_simulation_results()))
    stored.append(saved)
    if len(stored) > _SIM_HISTORY_MAX:
        stored = stored[-_SIM_HISTORY_MAX:]
    _write_sim_history(stored)
    return saved


# @MX:NOTE: [AUTO] SPEC-LOTTO-048 — 저장된 시뮬레이션 결과 단건 조회
# @MX:SPEC: SPEC-LOTTO-048
def get_simulation_result(result_id: str) -> dict[str, Any] | None:
    """지정한 id의 저장된 시뮬레이션 결과를 반환합니다. 없으면 None."""
    for result in list_simulation_results():
        if result.get("id") == result_id:
            return result
    return None


# @MX:NOTE: [AUTO] SPEC-LOTTO-048 — 저장된 시뮬레이션 결과 삭제
# @MX:SPEC: SPEC-LOTTO-048
def delete_simulation_result(result_id: str) -> bool:
    """지정한 id의 저장된 시뮬레이션 결과를 삭제합니다.

    삭제에 성공하면 True, 해당 id가 없으면 False를 반환한다.
    """
    # 디스크 저장 순서(오래된 것 → 최신)로 다시 정렬
    stored = list(reversed(list_simulation_results()))
    remaining = [r for r in stored if r.get("id") != result_id]
    if len(remaining) == len(stored):
        return False
    _write_sim_history(remaining)
    return True


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


# ─── SPEC-LOTTO-044: 번호 궁합 추천기 (number_affinity) ──────────────────────

# SPEC-LOTTO-044: 추천 조합에 포함할 상위 파트너 수 (대상 + 최대 5 = 6개)
_AFFINITY_COMBO_PARTNERS = 5


def _empty_affinity(target: int, total_draws: int) -> dict[str, Any]:
    """번호 궁합 분석의 일관된 빈 구조를 생성합니다 (SPEC-LOTTO-044 REQ-AFFINITY-006).

    데이터 부재 / None / 대상 미출현 모든 경우에서 동일 구조를 보장한다.
    추천 조합은 대상 번호만 담는다(유효 대상일 때).
    """
    return {
        "target": target,
        "total_draws": total_draws,
        "target_appearances": 0,
        "partners": [],
        "recommended_combination": [target],
    }


# @MX:NOTE: [AUTO] SPEC-LOTTO-044 — 대상 번호와 동반 출현(co-occurrence)한 파트너 집계 + 추천 조합
# @MX:SPEC: SPEC-LOTTO-044 REQ-AFFINITY-001
def number_affinity(
    target: int,
    draws: list[DrawResult] | None = _UNSET,
    top_k: int = 10,
) -> dict[str, Any]:
    """대상 번호와 함께 출현한 다른 번호의 궁합(co-occurrence)을 집계합니다 (SPEC-LOTTO-044).

    대상이 본번호 6개(보너스 제외)에 포함된 회차만 순회하며, 같은 회차에 함께
    나온 다른 번호들의 동반 횟수를 집계한다. 가장 궁합이 좋은 파트너로 추천 조합을
    생성한다.

    Args:
        target: 궁합을 분석할 번호 (1~45, 검증은 API 레이어가 수행).
        draws:  분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
                명시적 None 전달 시 데이터 없음으로 처리한다.
        top_k:  반환할 상위 파트너 수 (기본 10).

    반환 구조:
        - target:                  분석 대상 번호
        - total_draws:             전체 분석 회차 수
        - target_appearances:      대상이 등장한 회차 수
        - partners:                [{number, count, rate}] 동반 횟수 내림차순,
                                   동률은 번호 오름차순, 최대 top_k개
                                   (rate = count / target_appearances, 소수 4자리)
        - recommended_combination: sorted([target] + 상위 5 파트너 번호)
                                   (파트너가 5개 미만이면 가용분만 포함)

    데이터 부재(None) / 빈 리스트 / 대상 미출현 시 예외 없이 일관된 빈 구조를
    반환한다 (target_appearances=0, partners=[], recommended_combination=[target]).
    """
    if draws is _UNSET:
        draws = get_draws()

    if not draws:
        return _empty_affinity(target, 0)

    total_draws = len(draws)
    target_appearances = 0
    co_counts: dict[int, int] = {}

    for draw in draws:
        draw_set = set(draw.numbers())  # 정렬된 본번호 6개 (보너스 제외)
        if target not in draw_set:
            continue
        target_appearances += 1
        for num in draw_set:
            if num == target:
                continue
            co_counts[num] = co_counts.get(num, 0) + 1

    if target_appearances == 0:
        return _empty_affinity(target, total_draws)

    # 파트너 정렬 — count 내림차순, 동률은 번호 오름차순
    ranked = sorted(co_counts.items(), key=lambda x: (-x[1], x[0]))
    partners = [
        {
            "number": num,
            "count": count,
            "rate": round(count / target_appearances, 4),
        }
        for num, count in ranked[:top_k]
    ]

    # 추천 조합 — 대상 + 상위 5 파트너 번호 (정렬 오름차순)
    top_partner_numbers = [num for num, _ in ranked[:_AFFINITY_COMBO_PARTNERS]]
    recommended_combination = sorted([target, *top_partner_numbers])

    return {
        "target": target,
        "total_draws": total_draws,
        "target_appearances": target_appearances,
        "partners": partners,
        "recommended_combination": recommended_combination,
    }


# ─── SPEC-LOTTO-046: 당첨금 연도별 비교 (yearly_prize_comparison) ────────────


# @MX:NOTE: [AUTO] SPEC-LOTTO-046 — 연도별 1등 당첨금 통계 집계 (단일 O(N) 패스)
# @MX:SPEC: SPEC-LOTTO-046
def yearly_prize_comparison(draws: list[DrawResult] | None = _UNSET) -> dict[str, Any]:
    """연도별 1등 당첨금 통계를 집계하여 비교용 구조로 반환합니다 (SPEC-LOTTO-046).

    각 연도(DrawResult.date.year)에 대해 prize1Amount가 있는 회차만 대상으로
    평균/최대/최소/당첨자 합계를 집계한다. total_draws는 prize 유무와 무관하게
    연도 내 전체 회차 수를 센다.

    Args:
        draws: 분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
               명시적 None 전달 시 데이터 없음으로 처리한다.

    반환 구조:
        - total_years:        prize/데이터가 있는 연도 수 (years 길이)
        - overall_avg_prize1: prize 보유 전체 회차 평균(floor, 없으면 0)
        - highest_avg_year:   avg_prize1 최대 연도 "YYYY" (prize 보유 연도 한정, 없으면 None)
        - lowest_avg_year:    avg_prize1 최소 연도 "YYYY" (prize 보유 연도 한정, 없으면 None)
        - years: [{year, total_draws, prize_draws, avg_prize1, max_prize1,
                   min_prize1, total_winners}] 연도 오름차순

    연도 내 prize 데이터가 없으면 avg/max/min=0, prize_draws=0으로 채운다.
    데이터 부재(None) 또는 빈 리스트인 경우 total_years=0, overall_avg_prize1=0,
    highest/lowest_avg_year=None, years=[] 의 빈 구조를 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    if not draws:
        return {
            "total_years": 0,
            "overall_avg_prize1": 0,
            "highest_avg_year": None,
            "lowest_avg_year": None,
            "years": [],
        }

    # 연도별 누적: year(str) → {합계, prize 회차 수, 전체 회차 수, max, min, 당첨자 합}
    yearly: dict[str, dict[str, int]] = {}
    overall_prize_sum = 0
    overall_prize_count = 0

    for draw in draws:
        year_key = str(draw.date.year)
        bucket = yearly.setdefault(
            year_key,
            {"sum": 0, "prize_draws": 0, "total_draws": 0, "max": 0, "min": 0, "winners": 0},
        )
        bucket["total_draws"] += 1

        amount = draw.prize1Amount
        if amount is not None:
            bucket["sum"] += amount
            bucket["winners"] += draw.prize1Winners or 0
            if bucket["prize_draws"] == 0:
                bucket["max"] = amount
                bucket["min"] = amount
            else:
                bucket["max"] = max(bucket["max"], amount)
                bucket["min"] = min(bucket["min"], amount)
            bucket["prize_draws"] += 1
            overall_prize_sum += amount
            overall_prize_count += 1

    years: list[dict[str, Any]] = []
    for year_key, bucket in sorted(yearly.items()):
        prize_draws = bucket["prize_draws"]
        avg = int(bucket["sum"] // prize_draws) if prize_draws else 0
        years.append({
            "year": year_key,
            "total_draws": bucket["total_draws"],
            "prize_draws": prize_draws,
            "avg_prize1": avg,
            "max_prize1": bucket["max"] if prize_draws else 0,
            "min_prize1": bucket["min"] if prize_draws else 0,
            "total_winners": bucket["winners"],
        })

    overall_avg = int(overall_prize_sum // overall_prize_count) if overall_prize_count else 0

    # highest/lowest는 prize 보유 연도만 대상 — 동률 시 낮은 연도 우선
    prize_years = [y for y in years if y["prize_draws"] > 0]
    if prize_years:
        highest = max(prize_years, key=lambda y: (y["avg_prize1"], -int(y["year"])))
        lowest = min(prize_years, key=lambda y: (y["avg_prize1"], int(y["year"])))
        highest_avg_year = highest["year"]
        lowest_avg_year = lowest["year"]
    else:
        highest_avg_year = None
        lowest_avg_year = None

    return {
        "total_years": len(years),
        "overall_avg_prize1": overall_avg,
        "highest_avg_year": highest_avg_year,
        "lowest_avg_year": lowest_avg_year,
        "years": years,
    }


# ─── SPEC-LOTTO-047: 번호별 당첨 주기 분석 (cycle_analysis) ──────────────────

# SPEC-LOTTO-047: most_overdue 반환 최대 개수
_CYCLE_OVERDUE_TOP_N = 5
# SPEC-LOTTO-047: normal 판정 허용 오차 (|current_gap - avg_cycle| <= 0.5)
_CYCLE_NORMAL_TOLERANCE = 0.5


def _cycle_status(appearances: int, current_gap: int, avg_cycle: float) -> str:
    """번호의 주기 상태를 분류합니다 (SPEC-LOTTO-047).

    - never:    출현 이력 없음 (appearances == 0)
    - normal:   |current_gap - avg_cycle| <= 0.5 (근사 일치, 최우선 판정)
    - overdue:  current_gap > avg_cycle (평균 주기보다 오래 미출현)
    - frequent: current_gap < avg_cycle (평균보다 자주 출현)
    """
    if appearances == 0:
        return "never"
    if abs(current_gap - avg_cycle) <= _CYCLE_NORMAL_TOLERANCE:
        return "normal"
    if current_gap > avg_cycle:
        return "overdue"
    return "frequent"


# @MX:NOTE: [AUTO] SPEC-LOTTO-047 — 번호별 평균 출현 주기 + 현재 간격 분석 (단일 O(N) 패스)
# @MX:SPEC: SPEC-LOTTO-047
def cycle_analysis(draws: list[DrawResult] | None = _UNSET) -> dict[str, Any]:
    """번호 1~45의 평균 출현 주기와 현재 간격을 분석합니다 (SPEC-LOTTO-047).

    전체 회차를 시간 오름차순으로 정렬한 뒤, 각 번호(본번호 6개 기준, 보너스 제외)에
    대해 출현 횟수·평균 주기·마지막 출현 회차·현재 간격을 산출하고 상태로 분류한다.

    정의:
        - avg_cycle:   total_draws / appearances (소수 2자리). appearances==0이면 0.0.
                       "평균적으로 몇 회차마다 한 번 출현하는가"의 단순 추정치이다.
        - current_gap: 마지막 출현 이후 최신 회차까지 경과한 회차 수.
                       최신 회차에 출현하면 0, 한 번도 출현하지 않으면 total_draws.
        - status:      _cycle_status 규칙 (never/normal/overdue/frequent).

    Args:
        draws: 분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
               명시적 None 전달 시 데이터 없음으로 처리한다.

    반환 구조:
        - total_draws:  전체 회차 수
        - numbers:      [{number, appearances, avg_cycle, last_appeared_drwNo,
                          current_gap, status}] 번호 1~45 오름차순 (항상 45개)
        - most_overdue: [{number, current_gap, avg_cycle}] overdue 번호 중
                        (current_gap - avg_cycle) 내림차순 상위 5개
        - summary:      {overdue, frequent, normal, never} 상태별 카운트 (합계 45)

    데이터 부재(None) 또는 빈 리스트인 경우 total_draws=0, 45개 번호 모두 never,
    most_overdue=[], summary는 never=45의 일관된 빈 구조를 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    if not draws:
        return {
            "total_draws": 0,
            "numbers": [
                {
                    "number": n,
                    "appearances": 0,
                    "avg_cycle": 0.0,
                    "last_appeared_drwNo": None,
                    "current_gap": 0,
                    "status": "never",
                }
                for n in range(1, 46)
            ],
            "most_overdue": [],
            "summary": {"overdue": 0, "frequent": 0, "normal": 0, "never": 45},
        }

    # 회차 오름차순 정렬 — 간격 계산은 시간순 전제
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    total_draws = len(sorted_draws)
    last_idx = total_draws - 1

    # 번호별 출현 횟수 / 마지막 출현 인덱스 + 회차 번호 (단일 패스)
    appearances: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    last_idx_by_num: dict[int, int] = {}
    last_drw_by_num: dict[int, int] = {}
    for idx, draw in enumerate(sorted_draws):
        for n in draw.numbers():  # 정렬된 본번호 6개 (보너스 제외)
            appearances[n] += 1
            last_idx_by_num[n] = idx
            last_drw_by_num[n] = draw.drwNo

    numbers: list[dict[str, Any]] = []
    summary: dict[str, int] = {"overdue": 0, "frequent": 0, "normal": 0, "never": 0}

    for n in range(1, 46):
        count = appearances[n]
        if count == 0:
            avg_cycle = 0.0
            last_appeared: int | None = None
            current_gap = total_draws
        else:
            avg_cycle = round(total_draws / count, 2)
            last_appeared = last_drw_by_num[n]
            current_gap = last_idx - last_idx_by_num[n]

        status = _cycle_status(count, current_gap, avg_cycle)
        summary[status] += 1

        numbers.append({
            "number": n,
            "appearances": count,
            "avg_cycle": avg_cycle,
            "last_appeared_drwNo": last_appeared,
            "current_gap": current_gap,
            "status": status,
        })

    # most_overdue — overdue 번호만, (current_gap - avg_cycle) 내림차순 상위 5
    overdue_items = [
        {
            "number": item["number"],
            "current_gap": item["current_gap"],
            "avg_cycle": item["avg_cycle"],
        }
        for item in numbers
        if item["status"] == "overdue"
    ]
    overdue_items.sort(
        key=lambda x: (x["current_gap"] - x["avg_cycle"], x["number"]),
        reverse=True,
    )
    most_overdue = overdue_items[:_CYCLE_OVERDUE_TOP_N]

    return {
        "total_draws": total_draws,
        "numbers": numbers,
        "most_overdue": most_overdue,
        "summary": summary,
    }


# ─── SPEC-LOTTO-049: 합계 범위 분석 (sum_range_analysis) ────────────────────

# @MX:NOTE: [AUTO] SPEC-LOTTO-049 — 합계 버킷 경계 (폭 20, 마지막 241-255는 폭 15)
# @MX:SPEC: SPEC-LOTTO-049
# 본번호 6개 합계 가능 범위: 최소 1+2+3+4+5+6=21, 최대 40+41+42+43+44+45=255
_SUM_BUCKET_EDGES: tuple[tuple[int, int], ...] = (
    (21, 40), (41, 60), (61, 80), (81, 100), (101, 120), (121, 140),
    (141, 160), (161, 180), (181, 200), (201, 220), (221, 240), (241, 255),
)


def _percentile_nearest_rank(sorted_sums: list[int], pct: int) -> int:
    """정렬된 합계 리스트에서 nearest-rank 백분위 값을 반환합니다 (SPEC-LOTTO-049).

    nearest-rank: rank = ceil(pct/100 * N), [1, N]로 클램프, sorted[rank-1].
    빈 리스트는 0을 반환한다.
    """
    n = len(sorted_sums)
    if n == 0:
        return 0
    rank = math.ceil(pct / 100 * n)
    rank = max(1, min(rank, n))
    return sorted_sums[rank - 1]


# @MX:NOTE: [AUTO] SPEC-LOTTO-049 — 회차 합계 분포/공통 영역 분석 공개 함수
# @MX:SPEC: SPEC-LOTTO-049
def sum_range_analysis(draws: list[DrawResult] | None = _UNSET) -> dict[str, Any]:
    """회차별 본번호 6개 합계의 분포와 공통 영역을 분석합니다 (SPEC-LOTTO-049).

    각 회차 합계를 폭 20 버킷(마지막 241-255는 폭 15)으로 분류하고, 평균/최소/최대
    합계, 최빈 구간, 공통 영역(관측 합계의 p10~p90)을 산출한다.

    정의:
        - avg_sum:           회차 합계 평균 (소수 2자리). 데이터 없으면 0.0.
        - most_common_range: count 최대 버킷 라벨. 동률이면 더 낮은 구간. 없으면 None.
        - common_zone:       관측 합계의 [p10, p90] nearest-rank 정수 경계.
                             데이터 없으면 {low:0, high:0}.

    Args:
        draws: 분석 대상 회차 리스트. 생략 시 get_draws()로 자동 로드한다.
               명시적 None 전달 시 데이터 없음으로 처리한다.

    반환 구조:
        - total_draws:       전체 회차 수
        - avg_sum/min_sum/max_sum: 합계 통계
        - most_common_range: 최빈 구간 라벨 또는 None
        - distribution:      [{range, low, high, count, ratio}] 12개 버킷 오름차순
                             (count 0 버킷 포함, ratio 4자리)
        - common_zone:       {low, high}

    데이터 부재(None) 또는 빈 리스트인 경우 total_draws=0, 통계 0,
    most_common_range=None, 12개 버킷 모두 count 0, common_zone {0,0}을 반환한다.
    """
    if draws is _UNSET:
        draws = get_draws()

    def _empty_distribution() -> list[dict[str, Any]]:
        return [
            {"range": f"{lo}-{hi}", "low": lo, "high": hi, "count": 0, "ratio": 0.0}
            for lo, hi in _SUM_BUCKET_EDGES
        ]

    if not draws:
        return {
            "total_draws": 0,
            "avg_sum": 0.0,
            "min_sum": 0,
            "max_sum": 0,
            "most_common_range": None,
            "distribution": _empty_distribution(),
            "common_zone": {"low": 0, "high": 0},
        }

    sums = sorted(sum(d.numbers()) for d in draws)
    total_draws = len(sums)

    # 버킷별 카운트 (경계 순회)
    counts: dict[str, int] = {f"{lo}-{hi}": 0 for lo, hi in _SUM_BUCKET_EDGES}
    for total in sums:
        for lo, hi in _SUM_BUCKET_EDGES:
            if lo <= total <= hi:
                counts[f"{lo}-{hi}"] += 1
                break

    distribution = [
        {
            "range": f"{lo}-{hi}",
            "low": lo,
            "high": hi,
            "count": counts[f"{lo}-{hi}"],
            "ratio": round(counts[f"{lo}-{hi}"] / total_draws, 4),
        }
        for lo, hi in _SUM_BUCKET_EDGES
    ]

    # 최빈 구간 — count 최대, 동률이면 더 낮은 구간 (edges가 오름차순이므로 첫 최대)
    most_common_range = ""
    best_count = -1
    for lo, hi in _SUM_BUCKET_EDGES:
        c = counts[f"{lo}-{hi}"]
        if c > best_count:
            best_count = c
            most_common_range = f"{lo}-{hi}"

    return {
        "total_draws": total_draws,
        "avg_sum": round(sum(sums) / total_draws, 2),
        "min_sum": sums[0],
        "max_sum": sums[-1],
        "most_common_range": most_common_range,
        "distribution": distribution,
        "common_zone": {
            "low": _percentile_nearest_rank(sums, 10),
            "high": _percentile_nearest_rank(sums, 90),
        },
    }


# @MX:NOTE: [AUTO] SPEC-LOTTO-049 — 임의 조합 합계의 공통 영역 진입 여부 체커
# @MX:SPEC: SPEC-LOTTO-049
def evaluate_sum(
    numbers: list[int], draws: list[DrawResult] | None = _UNSET
) -> dict[str, Any]:
    """입력 조합의 합계가 공통 영역에 드는지와 백분위를 반환합니다 (SPEC-LOTTO-049).

    데이터 계층은 관대하게 동작한다 — numbers 유효성(개수/범위/중복)은 검증하지 않고
    단순히 합산한다. 입력 검증은 API 계층의 책임이다.

    정의:
        - sum:            sum(numbers)
        - in_common_zone: common_zone.low <= sum <= common_zone.high
        - percentile:     입력 합계 이하인 과거 회차 비율 (0.0~1.0, 4자리)

    Args:
        numbers: 합산할 번호 리스트 (유효성 미검증).
        draws:   기준 회차 리스트. 생략 시 get_draws()로 자동 로드.

    데이터 부재 시 common_zone {0,0}, percentile 0.0, in_common_zone False.
    """
    if draws is _UNSET:
        draws = get_draws()

    total = sum(numbers)

    if not draws:
        return {
            "sum": total,
            "in_common_zone": False,
            "common_zone": {"low": 0, "high": 0},
            "percentile": 0.0,
        }

    sums = sorted(sum(d.numbers()) for d in draws)
    low = _percentile_nearest_rank(sums, 10)
    high = _percentile_nearest_rank(sums, 90)
    le_count = sum(1 for s in sums if s <= total)

    return {
        "sum": total,
        "in_common_zone": low <= total <= high,
        "common_zone": {"low": low, "high": high},
        "percentile": round(le_count / len(sums), 4),
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


# ---------------------------------------------------------------------------
# SPEC-LOTTO-052: 전략 백테스팅 분석기 (look-ahead bias 제거)
# ---------------------------------------------------------------------------

# REQ-BT-009: 백테스트 실행 최소 회차 임계값 (이 미만이면 에러 결과)
_BACKTEST_MIN_DRAWS = 20
# 회차별 통계 재구성에 필요한 최소 prior 회차 수 (analyzer 폴백 임계값과 정합)
_BACKTEST_MIN_PRIOR = 3
# REQ-BT-017: 페이지/API 기본 평가 윈도
_BACKTEST_DEFAULT_N = 50
# 고적중(3+ 매치) 가중치 — score는 평균 적중 + 고적중 빈도 가중의 단조 합
_BACKTEST_HIGH_MATCH_THRESHOLD = 3
_BACKTEST_HIGH_MATCH_WEIGHT = 2.0


# @MX:ANCHOR: [AUTO] run_backtest — 전략 백테스팅의 핵심 진입점 (look-ahead bias 제거)
# @MX:REASON: pages.py(/backtest), api.py(/api/backtest), 테스트에서 호출 (fan_in >= 3).
#             회차마다 prior_draws로 통계를 재구성하는 인과 안전성이 핵심 불변식.
def run_backtest(
    draws: list[DrawResult],
    n_past: int = _BACKTEST_DEFAULT_N,
) -> dict[str, Any]:
    """11개 전략을 최근 n_past 회차에 대해 백테스트하여 전략별 성능을 산출한다.

    각 평가 회차 #k에 대해 prior_draws(#1..#k-1)만으로 통계를 재구성하고
    (look-ahead bias 제거, REQ-BT-002/012), 그 recommender로 11개 전략을
    한 번에 추천한다(회차당 1회 재구성, REQ-BT-016). 추천 6개와 실제 당첨 6개의
    교집합 크기를 적중 개수로 집계한다(보너스 제외, REQ-BT-003/015).

    Args:
        draws:  전체 추첨 목록 (회차 오름차순 가정, 아니면 내부에서 정렬).
        n_past: 평가할 최근 회차 수 (기본 50). 가용 회차보다 크면 클램프된다.

    Returns:
        성공 시 STRATEGY_LABELS 11개 라벨 → BacktestResult 매핑.
        회차 부족(REQ-BT-009) 시 {"error": <메시지>} 형태의 에러 결과.
    """
    from lotto.analyzer import LottoAnalyzer
    from lotto.recommender import STRATEGY_LABELS, LottoRecommender

    # REQ-BT-008: 동일 n_past 결과가 캐시되어 있으면 재계산 없이 반환
    if n_past in _backtest_cache:
        return _backtest_cache[n_past]

    # REQ-BT-009: 최소 회차 미달이면 백테스트를 실행하지 않고 에러 결과 반환
    if not draws or len(draws) < _BACKTEST_MIN_DRAWS:
        return {
            "error": f"백테스트에는 최소 {_BACKTEST_MIN_DRAWS}회차가 필요합니다.",
        }

    # 회차 오름차순 정렬 보장 (#1..#N)
    ordered = sorted(draws, key=lambda d: d.drwNo)

    # 평가 가능 회차: prior가 최소 _BACKTEST_MIN_PRIOR개 존재하는 회차들
    # = 인덱스 _BACKTEST_MIN_PRIOR 이후의 회차 (앞쪽 회차는 prior 부족으로 제외)
    evaluable = ordered[_BACKTEST_MIN_PRIOR:]
    # REQ-BT-010: n_past가 평가 가능 회차보다 크면 가능한 최대로 클램프
    window = evaluable[-n_past:] if n_past < len(evaluable) else evaluable

    analyzer = LottoAnalyzer()

    # 전략별 누적 집계 초기화 (match_counts는 0~6 키를 모두 포함)
    agg: dict[str, dict[str, Any]] = {
        label: {
            "match_counts": dict.fromkeys(range(7), 0),
            "match_sum": 0,
            "best_matched": -1,
            "best_draw": {"round": 0, "matched": 0, "recommended": [], "actual": []},
        }
        for label in STRATEGY_LABELS
    }

    for target in window:
        # REQ-BT-002/012: 평가 대상 회차 직전까지(#1..#k-1)만으로 통계 재구성
        prior_draws = [d for d in ordered if d.drwNo < target.drwNo]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            stats = analyzer.analyze(prior_draws)
        # REQ-BT-016: 회차당 recommender 1회 생성 후 11개 전략에 재사용
        recommender = LottoRecommender(stats)
        actual = target.numbers()
        actual_set = set(actual)

        for label in STRATEGY_LABELS:
            rec = recommender.recommend_by_strategy(label)
            # REQ-BT-003/015: 추천 6개 ∩ 실제 6개 (보너스 제외)
            matched = len(set(rec.numbers) & actual_set)
            bucket = agg[label]
            bucket["match_counts"][matched] += 1
            bucket["match_sum"] += matched
            if matched > bucket["best_matched"]:
                bucket["best_matched"] = matched
                bucket["best_draw"] = {
                    "round": target.drwNo,
                    "matched": matched,
                    "recommended": list(rec.numbers),
                    "actual": list(actual),
                }

    evaluated = len(window)
    result: dict[str, Any] = {}
    for label in STRATEGY_LABELS:
        bucket = agg[label]
        mc: dict[int, int] = bucket["match_counts"]
        avg_match = bucket["match_sum"] / evaluated if evaluated else 0.0
        # REQ-BT-004/AC-13: composite score = 평균 적중 + 고적중(3+) 빈도 가중
        high_hits = sum(v for k, v in mc.items() if k >= _BACKTEST_HIGH_MATCH_THRESHOLD)
        high_rate = high_hits / evaluated if evaluated else 0.0
        score = avg_match + _BACKTEST_HIGH_MATCH_WEIGHT * high_rate
        result[label] = {
            "match_counts": mc,
            "avg_match": avg_match,
            "best_draw": bucket["best_draw"],
            "score": score,
        }

    # REQ-BT-008/011: 성공 결과만 n_past 별로 캐시 (에러는 즉시 재시도 허용)
    _backtest_cache[n_past] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-053: 번호 동시 출현 분석기 (number co-occurrence)
# ---------------------------------------------------------------------------

# SPEC-LOTTO-053: 상위 쌍 / 파트너 기본 반환 개수
_COOCCURRENCE_TOP_N = 20
_COOCCURRENCE_PARTNER_TOP_K = 10


# @MX:NOTE: [AUTO] SPEC-LOTTO-053 — 쌍별 동시 출현 행렬 (i<j 단일 집계, 보너스 제외) + 메모리 캐시
# @MX:SPEC: SPEC-LOTTO-053 REQ-CO-001, REQ-CO-002, REQ-CO-003
def get_cooccurrence_matrix(
    draws: list[DrawResult] | None,
) -> dict[tuple[int, int], int]:
    """전체 회차에서 번호 쌍 (i, j) (단 i<j)의 동시 출현 횟수를 집계합니다 (SPEC-LOTTO-053).

    각 회차의 정렬된 본번호 6개(보너스 제외)에서 i<j 순서로 C(6,2)=15개 쌍을
    정확히 한 번씩만 순회하여(이중 집계 금지) 함께 나온 회차 수를 누적한다.
    한 번이라도 함께 나온 쌍만 키로 포함하며 (j, i) 역순 키는 절대 생성하지 않는다.

    동일 프로세스 수명 동안 결과를 모듈 레벨 단일 엔트리 캐시에 보관하여
    (REQ-CO-020) 반복 요청 시 재계산을 피한다. invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 빈 행렬을 반환한다.

    Returns:
        {(i, j): count} 매핑 (i<j). 데이터 부재 시 빈 dict.
    """
    global _cooccurrence_cache  # noqa: PLW0603 — 의도된 모듈 캐시 상태

    if _cooccurrence_cache is not None:
        return _cooccurrence_cache

    matrix: dict[tuple[int, int], int] = {}
    if not draws:
        # 빈 데이터도 캐시 — 동일 입력에 대한 반복 호출을 일관되게 처리
        _cooccurrence_cache = matrix
        return matrix

    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        # i<j 순서로 각 쌍을 정확히 한 번만 순회 (이중 집계 금지)
        for a in range(len(nums)):
            for b in range(a + 1, len(nums)):
                pair = (nums[a], nums[b])
                matrix[pair] = matrix.get(pair, 0) + 1

    _cooccurrence_cache = matrix
    return matrix


def _cooccurrence_pct(count: int, total_draws: int) -> float:
    """동시 출현 백분율을 계산합니다 = count / total_draws * 100 (소수 2자리).

    total_draws가 0이면 0.0을 반환한다 (REQ-CO-006).
    """
    if total_draws <= 0:
        return 0.0
    return round(count / total_draws * 100, 2)


# @MX:NOTE: [AUTO] SPEC-LOTTO-053 — 동시 출현 상위 N개 쌍 (count 내림차순, 동률은 쌍 오름차순)
# @MX:SPEC: SPEC-LOTTO-053 REQ-CO-004, REQ-CO-006
def get_top_cooccurrences(
    draws: list[DrawResult] | None,
    n: int = _COOCCURRENCE_TOP_N,
) -> list[dict[str, Any]]:
    """동시 출현 횟수 상위 n개 쌍을 반환합니다 (SPEC-LOTTO-053).

    get_cooccurrence_matrix로 구성한 행렬에서 파생하며(요청당 행렬 1회 구성,
    REQ-CO-019) draws를 재스캔하지 않는다. count 내림차순으로 정렬하고
    동률은 쌍 (i, j) 오름차순으로 결정론적으로 정렬한다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 빈 목록을 반환한다.
        n:     반환할 상위 쌍 수 (기본 20).

    Returns:
        [{"pair": [i, j], "count": int, "pct": float}, ...] 최대 n개.
        pct는 count / total_draws * 100 (소수 2자리). 데이터 부재 시 빈 목록.
    """
    if not draws:
        return []

    matrix = get_cooccurrence_matrix(draws)
    total_draws = len(draws)

    # count 내림차순, 동률은 쌍 오름차순 (결정론적)
    ranked = sorted(matrix.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "pair": [pair[0], pair[1]],
            "count": count,
            "pct": _cooccurrence_pct(count, total_draws),
        }
        for pair, count in ranked[:n]
    ]


# @MX:NOTE: [AUTO] SPEC-LOTTO-053 — 번호별 동반 파트너 상위 top_k (count 내림차순)
# @MX:SPEC: SPEC-LOTTO-053 REQ-CO-005, REQ-CO-006
def get_number_partners(
    draws: list[DrawResult] | None,
    number: int,
    top_k: int = _COOCCURRENCE_PARTNER_TOP_K,
) -> list[dict[str, Any]]:
    """특정 번호와 함께 나온 동반 파트너를 상위 top_k개 반환합니다 (SPEC-LOTTO-053).

    get_cooccurrence_matrix로 구성한 행렬에서 number를 포함한 쌍만 추려
    파생하며(draws 재스캔 없음, REQ-CO-019), number 자신은 파트너에서 제외한다.
    count 내림차순으로 정렬하고 동률은 파트너 번호 오름차순으로 정렬한다.

    Args:
        draws:  분석 대상 회차 리스트. 빈 리스트/None이면 빈 목록을 반환한다.
        number: 동반 파트너를 조회할 번호 (1~45, 검증은 API 레이어가 수행).
        top_k:  반환할 상위 파트너 수 (기본 10).

    Returns:
        [{"number": int, "count": int, "pct": float}, ...] 최대 top_k개.
        pct는 count / total_draws * 100 (소수 2자리). 데이터 부재 시 빈 목록.
    """
    if not draws:
        return []

    matrix = get_cooccurrence_matrix(draws)
    total_draws = len(draws)

    # number를 포함한 쌍에서 상대 파트너 번호의 동반 횟수를 추출
    partner_counts: dict[int, int] = {}
    for (i, j), count in matrix.items():
        if i == number:
            partner_counts[j] = count
        elif j == number:
            partner_counts[i] = count

    # count 내림차순, 동률은 번호 오름차순
    ranked = sorted(partner_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "number": partner,
            "count": count,
            "pct": _cooccurrence_pct(count, total_draws),
        }
        for partner, count in ranked[:top_k]
    ]


# SPEC-LOTTO-054: 롤링 윈도우 빈도 분석 ----------------------------------------

# REQ-RW-001: 기본 윈도우 집합 (최근 10/20/50/100 회차).
_ROLLING_DEFAULT_WINDOWS = (10, 20, 50, 100)
# REQ-RW-005/017: 추세 분류 임계값 — 하드코딩 상수 (설정/쿼리 노출 금지).
_ROLLING_TREND_THRESHOLD = 0.02
# REQ-RW-006: 최고 상승/하락 목록 크기.
_ROLLING_TOP_N = 5


def _classify_trend(delta: float) -> str:
    """추세 델타를 '상승'/'하락'/'보합'으로 분류합니다 (SPEC-LOTTO-054).

    REQ-RW-005: 엄격 부등호를 사용한다. 경계값 정확히 ±0.02는 '보합'으로 본다.

    Args:
        delta: 회차당 정규화된 빈도 차이.

    Returns:
        delta > +0.02 → "상승", delta < -0.02 → "하락", 그 외 → "보합".
    """
    if delta > _ROLLING_TREND_THRESHOLD:
        return "상승"
    if delta < -_ROLLING_TREND_THRESHOLD:
        return "하락"
    return "보합"


def _count_main_numbers(draws: list[DrawResult]) -> dict[int, int]:
    """주어진 회차들에서 번호 1~45 각각의 출현 회차 수를 집계합니다 (보너스 제외).

    REQ-RW-003: DrawResult.numbers()의 본번호 6개만 사용하며 보너스는 제외한다.
    """
    freq = dict.fromkeys(range(1, 46), 0)
    for draw in draws:
        for n in draw.numbers():
            freq[n] += 1
    return freq


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-054 — 롤링 윈도우 빈도/델타/추세 분석 진입점
# @MX:REASON: pages.py(/stats/rolling), api.py(/api/stats/rolling)에서 호출되는 공개 게이트웨이
# @MX:SPEC: SPEC-LOTTO-054 REQ-RW-001~007, REQ-RW-022/023
def get_rolling_frequency(
    draws: list[DrawResult] | None,
    windows: tuple[int, ...] = _ROLLING_DEFAULT_WINDOWS,
) -> dict[int, dict[str, Any]]:
    """여러 롤링 윈도우의 번호 빈도/델타/추세를 산출합니다 (SPEC-LOTTO-054).

    각 윈도우 W에 대해 최근 W회차(drwNo 기준 내림차순) 내 본번호 1~45의 출현
    빈도를 세고, 전체 이력 대비 정규화한 추세 델타로 비교한다. 번호별로
    상승/하락/보합을 분류하고 윈도우별 최고 상승·하락 상위 5개를 산출한다.

    전체 빈도(freq_total)는 요청당 1회만 계산하여 모든 윈도우가 재사용한다
    (REQ-RW-022). 결과는 windows 튜플(정렬)을 키로 모듈 캐시에 보관하며
    (REQ-RW-023), invalidate_cache()로 무효화된다.

    Args:
        draws:   분석 대상 회차 리스트. 빈 리스트/None이면 빈 dict를 반환한다.
        windows: 비교할 윈도우 크기 튜플 (기본 10/20/50/100).

    Returns:
        {W: RollingResult} 매핑. RollingResult는
        {"window": int, "freq": dict[int,int], "delta": dict[int,float],
        "trend": dict[int,str], "rising": list[int], "falling": list[int]}.
        가용 회차보다 큰 윈도우는 예외 없이 생략된다 (REQ-RW-012).
    """
    if not draws:
        return {}

    cache_key = tuple(sorted(windows))
    cached = _rolling_cache.get(cache_key)
    if cached is not None:
        return cached

    # drwNo 내림차순으로 정렬하여 최근 회차가 앞에 오게 한다 (REQ-RW-002).
    ordered = sorted(draws, key=lambda d: d.drwNo, reverse=True)
    total_draws = len(ordered)

    # 전체 빈도는 1회만 계산하여 모든 윈도우가 재사용 (REQ-RW-022).
    freq_total = _count_main_numbers(ordered)

    result: dict[int, dict[str, Any]] = {}
    for w in windows:
        if w > total_draws:
            continue  # REQ-RW-012: 가용 회차보다 큰 윈도우는 조용히 스킵

        recent = ordered[:w]
        freq_window = _count_main_numbers(recent)

        delta = {
            n: freq_window[n] / w - freq_total[n] / total_draws
            for n in range(1, 46)
        }
        trend = {n: _classify_trend(delta[n]) for n in range(1, 46)}

        # 델타 내림차순(동률은 번호 오름차순) → 상위 5개가 rising
        by_delta_desc = sorted(range(1, 46), key=lambda n: (-delta[n], n))
        rising = by_delta_desc[:_ROLLING_TOP_N]
        # 델타 오름차순(동률은 번호 오름차순) → 하위 5개가 falling
        by_delta_asc = sorted(range(1, 46), key=lambda n: (delta[n], n))
        falling = by_delta_asc[:_ROLLING_TOP_N]

        result[w] = {
            "window": w,
            "freq": freq_window,
            "delta": delta,
            "trend": trend,
            "rising": rising,
            "falling": falling,
        }

    _rolling_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-055: 끝자리 분포 분석 (last digit distribution)
# ---------------------------------------------------------------------------

# REQ-LD-003: 끝자리 d(0~9)별 번호 그룹 — n % 10 == d 인 1~45 번호 오름차순.
# 0:{10,20,30,40}, 1~5:{각 5개}, 6~9:{각 4개}. 모듈 로드 시 1회 산출하여 재사용한다.
_LAST_DIGIT_GROUPS: dict[int, list[int]] = {
    d: [n for n in range(1, 46) if n % 10 == d] for d in range(10)
}


# @MX:NOTE: [AUTO] SPEC-LOTTO-055 — 끝자리(1의 자리)별 출현 분포 분석 + 균등 기대치 대비 편차
# @MX:SPEC: SPEC-LOTTO-055 REQ-LD-001~009, REQ-LD-021/022
def get_last_digit_stats(
    draws: list[DrawResult] | None,
) -> dict[int, dict[str, Any]]:
    """끝자리(units digit) 0~9별 당첨 본번호 출현 분포를 분석합니다 (SPEC-LOTTO-055).

    각 끝자리 d에 대해 해당 그룹(n % 10 == d) 번호들이 본번호 6개로 출현한 총
    횟수를 집계하고, 비율·균등 기대치·편차를 산출한다. 보너스 번호는 제외한다
    (REQ-LD-005). 결과는 항상 10개 끝자리(0~9)를 모두 포함한다 (REQ-LD-009).

    번호별 빈도를 1회 집계한 뒤 끝자리로 묶어 재스캔을 피한다 (REQ-LD-021).
    결과는 모듈 레벨 단일 엔트리 캐시에 보관하여 반복 요청 시 재계산을 피하며
    (REQ-LD-022), invalidate_cache()로 무효화된다 (REQ-LD-014).

    정의:
        - count:        끝자리 그룹 번호들의 본번호 출현 총 횟수 (한 회차 중복 포함).
        - pct:          count / (total_draws * 6) * 100 (소수 2자리). total 0이면 0.0.
        - avg_expected: (len(numbers) / 45) * 6 * total_draws (균등 분포 기대 횟수).
        - deviation:    count - avg_expected (양수=과대표, 음수=과소표).

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 모든 끝자리 count 0,
               pct/avg_expected/deviation 0.0 의 일관된 구조를 반환한다.

    Returns:
        {d: LastDigitStat} 매핑 (d ∈ 0~9). LastDigitStat은
        {"digit", "count", "pct", "numbers", "avg_expected", "deviation"}.
    """
    global _last_digit_cache  # noqa: PLW0603 — 의도된 모듈 캐시 상태

    if _last_digit_cache is not None:
        return _last_digit_cache

    total_draws = len(draws) if draws else 0

    # 번호 1~45 출현 빈도를 1회 집계 (보너스 제외, REQ-LD-021)
    freq: dict[int, int] = dict.fromkeys(range(1, 46), 0)
    if draws:
        for draw in draws:
            for n in draw.numbers():  # 정렬된 본번호 6개 (보너스 제외)
                freq[n] += 1

    total_slots = total_draws * 6
    result: dict[int, dict[str, Any]] = {}
    for d in range(10):
        numbers = _LAST_DIGIT_GROUPS[d]
        count = sum(freq[n] for n in numbers)
        pct = round(count / total_slots * 100, 2) if total_slots else 0.0
        avg_expected = (len(numbers) / 45) * 6 * total_draws
        result[d] = {
            "digit": d,
            "count": count,
            "pct": pct,
            "numbers": numbers,
            "avg_expected": avg_expected,
            "deviation": count - avg_expected,
        }

    _last_digit_cache = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-056: 번호 간격 패턴 분석 (gap pattern analysis)
# ---------------------------------------------------------------------------

# SPEC-LOTTO-056: 간격 크기 분류 경계 (소: 1~5, 중: 6~10, 대: 11+)
_GAP_SMALL_MAX = 5
_GAP_MEDIUM_MAX = 10
# SPEC-LOTTO-056: most_common_gaps 반환 최대 개수
_GAP_TOP_N = 10


# @MX:NOTE: [AUTO] SPEC-LOTTO-056 — 정렬된 본번호 6개의 인접 간격 5개 분포 분석 + 메모리 캐시
# @MX:SPEC: SPEC-LOTTO-056
def get_gap_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 정렬된 본번호 6개의 인접 간격 패턴을 분석합니다 (SPEC-LOTTO-056).

    각 회차의 정렬된 본번호 6개(보너스 제외)에서 인접한 두 번호 차이 5개를
    구하고, 전체 회차에 걸쳐 평균/분류/위치별 평균/최빈 간격을 집계한다.

    정의:
        - 간격(gap): 정렬된 본번호의 인접 차이. 회차당 정확히 5개 (sorted[i+1]-sorted[i]).
        - small/medium/large: 1~5 / 6~10 / 11+ 로 분류한 간격 총 개수.
        - position i: sorted[i+1] - sorted[i] (i=0..4)의 회차 평균.

    번호별 간격을 1회 집계한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 모든 수치 0,
               빈 리스트의 일관된 구조를 반환한다.

    Returns:
        {total_draws, avg_gap, small_count, medium_count, large_count,
        small_pct, medium_pct, large_pct, most_common_gaps, avg_min_gap,
        avg_max_gap, position_avg} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _gap_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_gap": 0.0,
            "small_count": 0,
            "medium_count": 0,
            "large_count": 0,
            "small_pct": 0.0,
            "medium_pct": 0.0,
            "large_pct": 0.0,
            "most_common_gaps": [],
            "avg_min_gap": 0.0,
            "avg_max_gap": 0.0,
            "position_avg": [0.0, 0.0, 0.0, 0.0, 0.0],
        }
        _gap_cache[cache_key] = result
        return result

    total_draws = len(draws)
    small_count = 0
    medium_count = 0
    large_count = 0
    gap_value_counts: dict[int, int] = {}
    # 위치별 간격 합계 (5개 위치) — 회차 평균 산출용
    position_sums = [0, 0, 0, 0, 0]
    min_gap_sum = 0
    max_gap_sum = 0

    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        # 인접 쌍의 차이 5개 (zip으로 인접 쌍 생성)
        gaps = [b - a for a, b in zip(nums, nums[1:])]  # noqa: B905 — Python 3.9 호환

        for i, gap in enumerate(gaps):
            position_sums[i] += gap
            gap_value_counts[gap] = gap_value_counts.get(gap, 0) + 1
            if gap <= _GAP_SMALL_MAX:
                small_count += 1
            elif gap <= _GAP_MEDIUM_MAX:
                medium_count += 1
            else:
                large_count += 1

        min_gap_sum += min(gaps)
        max_gap_sum += max(gaps)

    total_gaps = small_count + medium_count + large_count
    avg_gap = round(
        sum(gap * cnt for gap, cnt in gap_value_counts.items()) / total_gaps, 2
    )

    # 최빈 간격 — count 내림차순, 동률은 간격 오름차순, 상위 10개
    ranked = sorted(gap_value_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    most_common_gaps = [
        {"gap": gap, "count": count} for gap, count in ranked[:_GAP_TOP_N]
    ]

    return _cache_gap_result(
        cache_key,
        total_draws=total_draws,
        avg_gap=avg_gap,
        small_count=small_count,
        medium_count=medium_count,
        large_count=large_count,
        total_gaps=total_gaps,
        most_common_gaps=most_common_gaps,
        min_gap_sum=min_gap_sum,
        max_gap_sum=max_gap_sum,
        position_sums=position_sums,
    )


def _cache_gap_result(
    cache_key: str,
    *,
    total_draws: int,
    avg_gap: float,
    small_count: int,
    medium_count: int,
    large_count: int,
    total_gaps: int,
    most_common_gaps: list[dict[str, int]],
    min_gap_sum: int,
    max_gap_sum: int,
    position_sums: list[int],
) -> dict[str, Any]:
    """집계 결과를 백분율/평균으로 마무리하여 캐시에 보관합니다 (SPEC-LOTTO-056)."""
    result: dict[str, Any] = {
        "total_draws": total_draws,
        "avg_gap": avg_gap,
        "small_count": small_count,
        "medium_count": medium_count,
        "large_count": large_count,
        "small_pct": round(small_count / total_gaps * 100, 2),
        "medium_pct": round(medium_count / total_gaps * 100, 2),
        "large_pct": round(large_count / total_gaps * 100, 2),
        "most_common_gaps": most_common_gaps,
        "avg_min_gap": round(min_gap_sum / total_draws, 2),
        "avg_max_gap": round(max_gap_sum / total_draws, 2),
        "position_avg": [round(s / total_draws, 2) for s in position_sums],
    }
    _gap_cache[cache_key] = result
    return result


# SPEC-LOTTO-057: AC값 산술 복잡도 분석 상수.
_AC_HIGH_MIN = 7  # AC >= 7 → 고복잡도
_AC_LOW_MAX = 3  # AC <= 3 → 저복잡도
_AC_MIN = 0  # AC 가능 최솟값
_AC_MAX = 10  # AC 가능 최댓값 (C(6,2)=15개 차이 전부 고유: 15-5)


def _ac_value(numbers: list[int]) -> int:
    """정렬된 본번호 6개의 AC(산술 복잡도)를 계산합니다 (SPEC-LOTTO-057).

    C(6,2)=15개 쌍의 차이 중 서로 다른 값의 개수 U를 구하고 AC = U - 5.
    """
    diffs = {b - a for a, b in itertools.combinations(numbers, 2)}
    return len(diffs) - 5


def get_ac_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 AC값(산술 복잡도) 분포를 분석합니다 (SPEC-LOTTO-057).

    각 회차의 정렬된 본번호 6개(보너스 제외)에서 모든 C(6,2)=15개 쌍의
    차이를 구하고, 서로 다른 차이 개수 U로부터 AC = U - 5 (범위 0..10)를
    산출한다. 전체 회차에 걸쳐 평균/분포/최빈/고저복잡도 비율을 집계한다.

    정의:
        - AC(arithmetic complexity): 고유 쌍차이 개수 U에서 5를 뺀 값 (0..10).
        - high: AC >= 7 인 회차 (고복잡도).
        - low: AC <= 3 인 회차 (저복잡도).
        - most_common_ac: 최빈 AC. 동률 시 더 작은 AC를 선택한다.

    회차별 AC를 1회 집계한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 모든 수치 0,
               빈 dict의 일관된 구조를 반환한다.

    Returns:
        {total_draws, avg_ac, ac_distribution, ac_distribution_pct,
        most_common_ac, high_ac_count, high_ac_pct, low_ac_count,
        low_ac_pct} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _ac_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_ac": 0.0,
            "ac_distribution": {},
            "ac_distribution_pct": {},
            "most_common_ac": 0,
            "high_ac_count": 0,
            "high_ac_pct": 0.0,
            "low_ac_count": 0,
            "low_ac_pct": 0.0,
        }
        _ac_cache[cache_key] = result
        return result

    total_draws = len(draws)
    # 0..10 모든 AC 값을 키로 미리 초기화 (count 0이어도 존재 보장)
    distribution: dict[int, int] = dict.fromkeys(range(_AC_MIN, _AC_MAX + 1), 0)
    ac_sum = 0
    high_ac_count = 0
    low_ac_count = 0

    for draw in draws:
        ac = _ac_value(draw.numbers())  # 본번호 6개만 사용 (보너스 제외)
        distribution[ac] += 1
        ac_sum += ac
        if ac >= _AC_HIGH_MIN:
            high_ac_count += 1
        if ac <= _AC_LOW_MAX:
            low_ac_count += 1

    avg_ac = round(ac_sum / total_draws, 2)
    distribution_pct = {
        ac: round(cnt / total_draws * 100, 2) for ac, cnt in distribution.items()
    }
    # 최빈 AC — count 내림차순, 동률은 AC 오름차순으로 가장 작은 값 선택
    most_common_ac = max(distribution, key=lambda ac: (distribution[ac], -ac))

    result = {
        "total_draws": total_draws,
        "avg_ac": avg_ac,
        "ac_distribution": distribution,
        "ac_distribution_pct": distribution_pct,
        "most_common_ac": most_common_ac,
        "high_ac_count": high_ac_count,
        "high_ac_pct": round(high_ac_count / total_draws * 100, 2),
        "low_ac_count": low_ac_count,
        "low_ac_pct": round(low_ac_count / total_draws * 100, 2),
    }
    _ac_cache[cache_key] = result
    return result


# SPEC-LOTTO-058: 1~45 범위의 소수 14개. 본번호 분류에 사용한다.
_PRIMES_1_45: frozenset[int] = frozenset(
    {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43}
)
_PRIME_COUNT_MIN = 0  # 회차당 소수/합성수 가능 최솟값
_PRIME_COUNT_MAX = 6  # 회차당 소수/합성수 가능 최댓값 (본번호 6개)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-058 소수/합성수 분포 분석 — 페이지/API 라우트의 공통 진입점
# @MX:SPEC: SPEC-LOTTO-058
# @MX:REASON: pages/api 라우트와 캐시 무효화 경로에서 호출되는 데이터 계층 단일 진입점
def get_prime_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개를 소수/합성수/1로 분류한 분포를 분석합니다 (SPEC-LOTTO-058).

    각 회차의 본번호 6개(보너스 제외)를 다음 기준으로 분류한다.
        - 1: one (소수도 합성수도 아님)
        - 1~45 소수 14개: prime
        - 그 외(1과 소수 제외 30개): composite

    전체 회차에 걸쳐 평균 소수/합성수 개수, 소수 개수(0~6) 분포, 최빈 소수 개수,
    합성수 개수(0~6) 분포, 숫자 1 출현 회차 수/비율을 집계한다.

    회차별 분류를 1회 집계한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 모든 수치 0,
               빈 dict의 일관된 구조를 반환한다.

    Returns:
        {total_draws, avg_prime, avg_composite, prime_distribution,
        prime_distribution_pct, most_common_prime_count, composite_distribution,
        one_appeared_count, one_appeared_pct} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _prime_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_prime": 0.0,
            "avg_composite": 0.0,
            "prime_distribution": {},
            "prime_distribution_pct": {},
            "most_common_prime_count": 0,
            "composite_distribution": {},
            "one_appeared_count": 0,
            "one_appeared_pct": 0.0,
        }
        _prime_cache[cache_key] = result
        return result

    total_draws = len(draws)
    # 0..6 모든 개수를 키로 미리 초기화 (count 0이어도 존재 보장)
    prime_dist: dict[int, int] = dict.fromkeys(
        range(_PRIME_COUNT_MIN, _PRIME_COUNT_MAX + 1), 0
    )
    composite_dist: dict[int, int] = dict.fromkeys(
        range(_PRIME_COUNT_MIN, _PRIME_COUNT_MAX + 1), 0
    )
    prime_sum = 0
    composite_sum = 0
    one_appeared_count = 0

    for draw in draws:
        prime_count = 0
        composite_count = 0
        one_count = 0
        for n in draw.numbers():  # 본번호 6개만 사용 (보너스 제외)
            if n == 1:
                one_count += 1
            elif n in _PRIMES_1_45:
                prime_count += 1
            else:
                composite_count += 1

        prime_dist[prime_count] += 1
        composite_dist[composite_count] += 1
        prime_sum += prime_count
        composite_sum += composite_count
        if one_count > 0:
            one_appeared_count += 1

    avg_prime = round(prime_sum / total_draws, 2)
    avg_composite = round(composite_sum / total_draws, 2)
    prime_dist_pct = {
        k: round(cnt / total_draws * 100, 2) for k, cnt in prime_dist.items()
    }
    # 최빈 소수 개수 — count 내림차순, 동률은 개수 오름차순으로 가장 작은 값 선택
    most_common_prime_count = max(
        prime_dist, key=lambda k: (prime_dist[k], -k)
    )

    result = {
        "total_draws": total_draws,
        "avg_prime": avg_prime,
        "avg_composite": avg_composite,
        "prime_distribution": prime_dist,
        "prime_distribution_pct": prime_dist_pct,
        "most_common_prime_count": most_common_prime_count,
        "composite_distribution": composite_dist,
        "one_appeared_count": one_appeared_count,
        "one_appeared_pct": round(one_appeared_count / total_draws * 100, 2),
    }
    _prime_cache[cache_key] = result
    return result


# SPEC-LOTTO-059: 십의 자리 구간 정의 (label, low, high, size).
# 명시적 범위 비교로 분류한다. n // 10 사용 시 1~9가 'decade 0'으로 잘못
# 묶이고 40~45가 두 그룹(40~49, 미존재)으로 흩어지므로 사용하지 않는다.
_DECADE_GROUPS: list[tuple[str, int, int, int]] = [
    ("01-09", 1, 9, 9),
    ("10-19", 10, 19, 10),
    ("20-29", 20, 29, 10),
    ("30-39", 30, 39, 10),
    ("40-45", 40, 45, 6),
]

_DECADE_COUNT_MIN = 0  # 회차당 한 구간의 가능 최솟값
_DECADE_COUNT_MAX = 6  # 회차당 한 구간의 가능 최댓값 (본번호 6개)
_DECADE_TOTAL_NUMBERS = 45  # 전체 번호 풀
_DECADE_PICK = 6  # 회차당 본번호 개수


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-059 십의 자리 구간 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-059
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_decade_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개를 5개 십의 자리 구간으로 분류한 분포를 분석합니다 (SPEC-LOTTO-059).

    각 회차의 본번호 6개(보너스 제외)를 다음 5개 구간으로 분류한다.
        - "01-09": 1~9 (크기 9)
        - "10-19": 10~19 (크기 10)
        - "20-29": 20~29 (크기 10)
        - "30-39": 30~39 (크기 10)
        - "40-45": 40~45 (크기 6)

    구간 분류는 n // 10 이 아니라 명시적 범위 비교(low <= n <= high)로 수행한다.

    각 구간에 대해 회차당 평균 출현 개수, 기대 평균((size/45)*6),
    편차(평균-기대), 출현 개수(0~6) 분포를 집계하고,
    전체에서 평균 출현이 가장 많은/적은 구간을 식별한다.

    회차별 분류를 1회 집계한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               각 구간 avg_count=0.0, expected_avg 계산값, deviation=0-expected,
               빈 distribution을 반환한다.

    Returns:
        {total_draws, groups[{label, size, avg_count, expected_avg, deviation,
        distribution}], most_frequent_group, least_frequent_group} 매핑.
        groups는 고정 순서(01-09 먼저, 40-45 마지막)이다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _decade_cache.get(cache_key)
    if cached is not None:
        return cached

    total_draws = len(draws) if draws else 0

    if total_draws == 0:
        groups: list[dict[str, Any]] = []
        for label, _low, _high, size in _DECADE_GROUPS:
            expected_avg = round(size / _DECADE_TOTAL_NUMBERS * _DECADE_PICK, 2)
            groups.append(
                {
                    "label": label,
                    "size": size,
                    "avg_count": 0.0,
                    "expected_avg": expected_avg,
                    "deviation": round(0.0 - expected_avg, 2),
                    "distribution": {},
                }
            )
        result: dict[str, Any] = {
            "total_draws": 0,
            "groups": groups,
            # 빈 데이터에서도 일관된 라벨을 제공 (고정 순서 첫 구간)
            "most_frequent_group": _DECADE_GROUPS[0][0],
            "least_frequent_group": _DECADE_GROUPS[0][0],
        }
        _decade_cache[cache_key] = result
        return result

    # 구간별 합계와 0~6 출현 개수 분포를 초기화
    sums: dict[str, int] = {g[0]: 0 for g in _DECADE_GROUPS}
    dists: dict[str, dict[int, int]] = {
        g[0]: dict.fromkeys(
            range(_DECADE_COUNT_MIN, _DECADE_COUNT_MAX + 1), 0
        )
        for g in _DECADE_GROUPS
    }

    assert draws is not None  # total_draws > 0 이므로 보장됨
    for draw in draws:
        per_group: dict[str, int] = {g[0]: 0 for g in _DECADE_GROUPS}
        for n in draw.numbers():  # 본번호 6개만 사용 (보너스 제외)
            for label, low, high, _size in _DECADE_GROUPS:
                if low <= n <= high:
                    per_group[label] += 1
                    break
        for label, count in per_group.items():
            sums[label] += count
            dists[label][count] += 1

    groups = []
    for label, _low, _high, size in _DECADE_GROUPS:
        avg_count = round(sums[label] / total_draws, 2)
        expected_avg = round(size / _DECADE_TOTAL_NUMBERS * _DECADE_PICK, 2)
        groups.append(
            {
                "label": label,
                "size": size,
                "avg_count": avg_count,
                "expected_avg": expected_avg,
                "deviation": round(avg_count - expected_avg, 2),
                "distribution": dists[label],
            }
        )

    # 최빈/최소 구간 — avg_count 기준, 동률은 고정 순서(_DECADE_GROUPS) 첫 번째 선택.
    # enumerate 인덱스를 보조 키로 사용하여 동률 시 앞선 구간을 우선한다.
    most_frequent_group = max(
        enumerate(groups), key=lambda iv: (iv[1]["avg_count"], -iv[0])
    )[1]["label"]
    least_frequent_group = min(
        enumerate(groups), key=lambda iv: (iv[1]["avg_count"], iv[0])
    )[1]["label"]

    result = {
        "total_draws": total_draws,
        "groups": groups,
        "most_frequent_group": most_frequent_group,
        "least_frequent_group": least_frequent_group,
    }
    _decade_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-060: 홀짝 비율 분석 (odd/even ratio analysis)
# ---------------------------------------------------------------------------

_ODD_EVEN_MIN = 0  # 회차당 홀수/짝수 가능 최솟값
_ODD_EVEN_MAX = 6  # 회차당 홀수/짝수 가능 최댓값 (본번호 6개)
_ODD_EVEN_PICK = 6  # 회차당 본번호 개수
_ODD_EVEN_BALANCED = 3  # 균형 회차 기준 (홀 3 / 짝 3)


def _empty_odd_even_distribution() -> dict[int, int]:
    """0..6 모든 키를 0으로 채운 분포를 생성합니다 (SPEC-LOTTO-060)."""
    return dict.fromkeys(range(_ODD_EVEN_MIN, _ODD_EVEN_MAX + 1), 0)


def _empty_odd_even_distribution_pct() -> dict[int, float]:
    """0..6 모든 키를 0.0으로 채운 비율 분포를 생성합니다 (SPEC-LOTTO-060)."""
    return dict.fromkeys(range(_ODD_EVEN_MIN, _ODD_EVEN_MAX + 1), 0.0)


def _most_common_smallest(distribution: dict[int, int]) -> int:
    """분포에서 가장 빈도 높은 키를 반환합니다. 동률 시 더 작은 키를 택합니다.

    SPEC-LOTTO-060 REQ-OE-007: count 내림차순, 동률은 키 오름차순으로
    가장 작은 값을 선택한다. 오름차순으로 순회하며 엄격 초과(>)일 때만 갱신해
    동률 시 먼저 만난(더 작은) 키가 유지되도록 한다.
    """
    best_key = _ODD_EVEN_MIN
    best_count = -1
    for k in range(_ODD_EVEN_MIN, _ODD_EVEN_MAX + 1):
        if distribution[k] > best_count:
            best_count = distribution[k]
            best_key = k
    return best_key


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-060 홀짝 비율 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-060
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_odd_even_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 홀짝 비율 분포를 분석합니다 (SPEC-LOTTO-060).

    각 회차의 본번호 6개(보너스 제외)에서 홀수 개수(odd_count, 0~6)를 세고,
    짝수 개수는 even_count = 6 - odd_count로 파생한다(독립 분류 금지, 합 불변식
    보장, REQ-OE-012). 전체 회차에 걸친 평균/분포/비율/최빈 개수/균형 회차를
    집계한다.

    정의:
        - odd_count:   한 회차 본번호 중 홀수(n % 2 == 1) 개수 (0~6).
        - even_count:  6 - odd_count.
        - avg_odd/avg_even: 회차 평균 (소수 2자리).
        - odd_distribution/even_distribution: 개수(0~6) → 회차 수 (모든 키 존재).
        - *_distribution_pct: count / total_draws * 100 (소수 2자리, 모든 키 존재).
        - most_common_*_count: 최빈 개수. 동률 시 더 작은 개수 선택 (REQ-OE-007).
        - balanced_count/balanced_pct: odd==even(즉 3:3)인 회차 수와 비율(2자리).

    본번호가 6개 미만인 회차는 집계에서 제외한다(REQ-OE-015). 회차별 분류를
    1회 집계한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다. 캐시 키는
    str(len(draws))이며 invalidate_cache()로 무효화된다(REQ-OE-016).

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               avg_odd/avg_even=0, 모든 분포 키 0, most_common=0,
               balanced_count/pct=0 의 일관된 빈 구조를 반환한다(REQ-OE-013).

    Returns:
        {total_draws, avg_odd, avg_even, odd_distribution, even_distribution,
        odd_distribution_pct, even_distribution_pct, most_common_odd_count,
        most_common_even_count, balanced_count, balanced_pct} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _odd_even_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_odd": 0,
            "avg_even": 0,
            "odd_distribution": _empty_odd_even_distribution(),
            "even_distribution": _empty_odd_even_distribution(),
            "odd_distribution_pct": _empty_odd_even_distribution_pct(),
            "even_distribution_pct": _empty_odd_even_distribution_pct(),
            "most_common_odd_count": 0,
            "most_common_even_count": 0,
            "balanced_count": 0,
            "balanced_pct": 0,
        }
        _odd_even_cache[cache_key] = result
        return result

    odd_distribution = _empty_odd_even_distribution()
    even_distribution = _empty_odd_even_distribution()
    odd_sum = 0
    even_sum = 0
    balanced_count = 0
    counted_draws = 0

    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        # REQ-OE-015: 본번호가 6개 미만이면 집계에서 제외
        if len(nums) < _ODD_EVEN_PICK:
            continue

        odd_count = sum(1 for n in nums if n % 2 == 1)
        # REQ-OE-012: even은 독립 분류가 아니라 6 - odd로 파생 (합 불변식 보장)
        even_count = _ODD_EVEN_PICK - odd_count

        odd_distribution[odd_count] += 1
        even_distribution[even_count] += 1
        odd_sum += odd_count
        even_sum += even_count
        if odd_count == _ODD_EVEN_BALANCED:
            balanced_count += 1
        counted_draws += 1

    total_draws = counted_draws

    if total_draws == 0:
        # 유효 회차가 하나도 없으면 빈 구조 (키 일관성 유지)
        result = {
            "total_draws": 0,
            "avg_odd": 0,
            "avg_even": 0,
            "odd_distribution": _empty_odd_even_distribution(),
            "even_distribution": _empty_odd_even_distribution(),
            "odd_distribution_pct": _empty_odd_even_distribution_pct(),
            "even_distribution_pct": _empty_odd_even_distribution_pct(),
            "most_common_odd_count": 0,
            "most_common_even_count": 0,
            "balanced_count": 0,
            "balanced_pct": 0,
        }
        _odd_even_cache[cache_key] = result
        return result

    odd_distribution_pct = {
        k: round(cnt / total_draws * 100, 2) for k, cnt in odd_distribution.items()
    }
    even_distribution_pct = {
        k: round(cnt / total_draws * 100, 2) for k, cnt in even_distribution.items()
    }

    result = {
        "total_draws": total_draws,
        "avg_odd": round(odd_sum / total_draws, 2),
        "avg_even": round(even_sum / total_draws, 2),
        "odd_distribution": odd_distribution,
        "even_distribution": even_distribution,
        "odd_distribution_pct": odd_distribution_pct,
        "even_distribution_pct": even_distribution_pct,
        "most_common_odd_count": _most_common_smallest(odd_distribution),
        "most_common_even_count": _most_common_smallest(even_distribution),
        "balanced_count": balanced_count,
        "balanced_pct": round(balanced_count / total_draws * 100, 2),
    }
    _odd_even_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-061: 고저 비율 분석 (high/low ratio analysis)
# ---------------------------------------------------------------------------

_HIGH_LOW_MIN = 0  # 회차당 저/고 가능 최솟값
_HIGH_LOW_MAX = 6  # 회차당 저/고 가능 최댓값 (본번호 6개)
_HIGH_LOW_PICK = 6  # 회차당 본번호 개수
_HIGH_LOW_BALANCED = 3  # 균형 회차 기준 (저 3 / 고 3)
_HIGH_LOW_BOUNDARY = 22  # 저(low) 상한 — n <= 22 저, n >= 23 고


def _empty_high_low_distribution() -> dict[int, int]:
    """0..6 모든 키를 0으로 채운 분포를 생성합니다 (SPEC-LOTTO-061)."""
    return dict.fromkeys(range(_HIGH_LOW_MIN, _HIGH_LOW_MAX + 1), 0)


def _empty_high_low_distribution_pct() -> dict[int, float]:
    """0..6 모든 키를 0.0으로 채운 비율 분포를 생성합니다 (SPEC-LOTTO-061)."""
    return dict.fromkeys(range(_HIGH_LOW_MIN, _HIGH_LOW_MAX + 1), 0.0)


def _most_common_high_low_smallest(distribution: dict[int, int]) -> int:
    """분포에서 가장 빈도 높은 키를 반환합니다. 동률 시 더 작은 키를 택합니다.

    SPEC-LOTTO-061: count 내림차순, 동률은 키 오름차순으로 가장 작은 값을 선택한다.
    오름차순으로 순회하며 엄격 초과(>)일 때만 갱신해 동률 시 먼저 만난(더 작은)
    키가 유지되도록 한다.
    """
    best_key = _HIGH_LOW_MIN
    best_count = -1
    for k in range(_HIGH_LOW_MIN, _HIGH_LOW_MAX + 1):
        if distribution[k] > best_count:
            best_count = distribution[k]
            best_key = k
    return best_key


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-061 고저 비율 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-061
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_high_low_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 고저 비율 분포를 분석합니다 (SPEC-LOTTO-061).

    각 회차의 본번호 6개(보너스 제외)에서 저(low) 개수(low_count, 0~6)를 세고,
    고(high) 개수는 high_count = 6 - low_count로 파생한다(독립 분류 금지, 합 불변식
    보장). 전체 회차에 걸친 평균/분포/비율/최빈 개수/균형 회차를 집계한다.

    분류:
        - 저(low):  1~22 (n <= 22, 경계 22는 저).
        - 고(high): 23~45 (n >= 23, 경계 23은 고).

    정의:
        - low_count:   한 회차 본번호 중 저(n <= 22) 개수 (0~6).
        - high_count:  6 - low_count.
        - avg_low/avg_high: 회차 평균 (소수 2자리).
        - low_distribution/high_distribution: 개수(0~6) → 회차 수 (모든 키 존재).
        - *_distribution_pct: count / total_draws * 100 (소수 2자리, 모든 키 존재).
        - most_common_*_count: 최빈 개수. 동률 시 더 작은 개수 선택.
        - balanced_count/balanced_pct: low==high(즉 3:3)인 회차 수와 비율(2자리).

    본번호가 6개 미만인 회차는 집계에서 제외한다. 회차별 분류를 1회 집계한 뒤
    캐시에 보관하여 반복 요청 시 재계산을 피한다. 캐시 키는 str(len(draws))이며
    invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               avg_low/avg_high=0.0, 모든 분포 키 0, most_common=0,
               balanced_count=0/balanced_pct=0.0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_low, avg_high, low_distribution, high_distribution,
        low_distribution_pct, high_distribution_pct, most_common_low_count,
        most_common_high_count, balanced_count, balanced_pct} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _high_low_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_low": 0.0,
            "avg_high": 0.0,
            "low_distribution": _empty_high_low_distribution(),
            "high_distribution": _empty_high_low_distribution(),
            "low_distribution_pct": _empty_high_low_distribution_pct(),
            "high_distribution_pct": _empty_high_low_distribution_pct(),
            "most_common_low_count": 0,
            "most_common_high_count": 0,
            "balanced_count": 0,
            "balanced_pct": 0.0,
        }
        _high_low_cache[cache_key] = result
        return result

    low_distribution = _empty_high_low_distribution()
    high_distribution = _empty_high_low_distribution()
    low_sum = 0
    high_sum = 0
    balanced_count = 0
    counted_draws = 0

    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        # 본번호가 6개 미만이면 집계에서 제외
        if len(nums) < _HIGH_LOW_PICK:
            continue

        low_count = sum(1 for n in nums if n <= _HIGH_LOW_BOUNDARY)
        # high는 독립 분류가 아니라 6 - low로 파생 (합 불변식 보장)
        high_count = _HIGH_LOW_PICK - low_count

        low_distribution[low_count] += 1
        high_distribution[high_count] += 1
        low_sum += low_count
        high_sum += high_count
        if low_count == _HIGH_LOW_BALANCED:
            balanced_count += 1
        counted_draws += 1

    total_draws = counted_draws

    if total_draws == 0:
        # 유효 회차가 하나도 없으면 빈 구조 (키 일관성 유지)
        result = {
            "total_draws": 0,
            "avg_low": 0.0,
            "avg_high": 0.0,
            "low_distribution": _empty_high_low_distribution(),
            "high_distribution": _empty_high_low_distribution(),
            "low_distribution_pct": _empty_high_low_distribution_pct(),
            "high_distribution_pct": _empty_high_low_distribution_pct(),
            "most_common_low_count": 0,
            "most_common_high_count": 0,
            "balanced_count": 0,
            "balanced_pct": 0.0,
        }
        _high_low_cache[cache_key] = result
        return result

    low_distribution_pct = {
        k: round(cnt / total_draws * 100, 2) for k, cnt in low_distribution.items()
    }
    high_distribution_pct = {
        k: round(cnt / total_draws * 100, 2) for k, cnt in high_distribution.items()
    }

    result = {
        "total_draws": total_draws,
        "avg_low": round(low_sum / total_draws, 2),
        "avg_high": round(high_sum / total_draws, 2),
        "low_distribution": low_distribution,
        "high_distribution": high_distribution,
        "low_distribution_pct": low_distribution_pct,
        "high_distribution_pct": high_distribution_pct,
        "most_common_low_count": _most_common_high_low_smallest(low_distribution),
        "most_common_high_count": _most_common_high_low_smallest(high_distribution),
        "balanced_count": balanced_count,
        "balanced_pct": round(balanced_count / total_draws * 100, 2),
    }
    _high_low_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-062: 연속 번호 패턴 분석 (consecutive number pattern analysis)
# ---------------------------------------------------------------------------

_CONSEC_PAT_MIN = 0  # 회차당 연속 쌍 가능 최솟값
_CONSEC_PAT_MAX = 5  # 회차당 연속 쌍 가능 최댓값 (본번호 6개 → 최대 5쌍)
_CONSEC_PAT_PICK = 6  # 회차당 본번호 개수
_CONSEC_TRIPLE_MIN = 3  # 연속 트리플(3연속) 판정 최소 런 길이


def _consecutive_pair_count(nums: list[int]) -> int:
    """정렬된 본번호의 인접 차이가 1인 연속 쌍 개수를 반환합니다 (SPEC-LOTTO-062).

    예) [5,6,7] → (5,6),(6,7) 2쌍 / [1,2,4,5,7,8] → 3쌍.
    """
    sorted_nums = sorted(nums)
    return sum(
        1
        for i in range(len(sorted_nums) - 1)
        if sorted_nums[i + 1] - sorted_nums[i] == 1
    )


def _has_consecutive_triple(nums: list[int]) -> bool:
    """정렬된 번호 중 3개 이상 연속(차이 1) 런이 있으면 True를 반환합니다 (SPEC-LOTTO-062).

    예) [5,6,7,...] → True / [1,2,4,5,...] → False (최장 런 길이 2).
    """
    sorted_nums = sorted(nums)
    run = 1
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] - sorted_nums[i - 1] == 1:
            run += 1
            if run >= _CONSEC_TRIPLE_MIN:
                return True
        else:
            run = 1
    return False


def _empty_consecutive_pattern_stats() -> dict[str, Any]:
    """연속 번호 패턴 분석의 일관된 빈 구조를 생성합니다 (SPEC-LOTTO-062).

    빈 데이터 / None 모든 경우에서 pair_distribution 0..5 키가 모두 존재하도록 보장한다.
    """
    return {
        "total_draws": 0,
        "avg_consecutive_pairs": 0.0,
        "pair_distribution": dict.fromkeys(
            range(_CONSEC_PAT_MIN, _CONSEC_PAT_MAX + 1), 0
        ),
        "pair_distribution_pct": dict.fromkeys(
            range(_CONSEC_PAT_MIN, _CONSEC_PAT_MAX + 1), 0.0
        ),
        "most_common_pair_count": 0,
        "no_consecutive_count": 0,
        "no_consecutive_pct": 0.0,
        "has_triple_count": 0,
        "has_triple_pct": 0.0,
        "max_consecutive_count": 0,
    }


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-062 연속 번호 패턴 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-062
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_consecutive_pattern_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 연속 번호 패턴 분포를 분석합니다 (SPEC-LOTTO-062).

    각 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이가 1인 연속 쌍의 개수
    (pair_count, 0~5)를 세고, 3개 이상 연속(트리플)이 존재하는지(has_triple)를
    판정한다. SPEC-LOTTO-043의 consecutive_pattern과는 독립적으로 구현된다.

    정의:
        - pair_count:   회차당 연속 쌍 개수. 예) [5,6,7]→2, [1,2,4,5,7,8]→3.
        - has_triple:   정렬 번호 중 3개 이상 연속 런이 있으면 True.
        - avg_consecutive_pairs: 회차 평균 연속 쌍 (소수 2자리).
        - pair_distribution: 쌍 개수(0~5) → 회차 수 (모든 키 존재).
        - pair_distribution_pct: count / total_draws * 100 (소수 2자리, 모든 키 존재).
        - most_common_pair_count: 최빈 쌍 개수. 동률 시 더 작은 개수 선택.
        - no_consecutive_count/pct: 연속 쌍이 0인 회차 수와 비율(2자리).
        - has_triple_count/pct: 트리플을 포함한 회차 수와 비율(2자리).
        - max_consecutive_count: 관측된 최대 연속 쌍 개수.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               모든 수치 0, pair_distribution 0..5 키 0의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_consecutive_pairs, pair_distribution,
        pair_distribution_pct, most_common_pair_count, no_consecutive_count,
        no_consecutive_pct, has_triple_count, has_triple_pct,
        max_consecutive_count} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _consecutive_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result = _empty_consecutive_pattern_stats()
        _consecutive_cache[cache_key] = result
        return result

    total_draws = len(draws)
    distribution: dict[int, int] = dict.fromkeys(
        range(_CONSEC_PAT_MIN, _CONSEC_PAT_MAX + 1), 0
    )
    pair_sum = 0
    no_consecutive_count = 0
    has_triple_count = 0
    max_consecutive_count = 0

    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        pair_count = _consecutive_pair_count(nums)

        distribution[pair_count] += 1
        pair_sum += pair_count
        max_consecutive_count = max(max_consecutive_count, pair_count)
        if pair_count == 0:
            no_consecutive_count += 1
        if _has_consecutive_triple(nums):
            has_triple_count += 1

    distribution_pct = {
        k: round(cnt / total_draws * 100, 2) for k, cnt in distribution.items()
    }
    # 최빈 쌍 개수 — count 내림차순, 동률은 개수 오름차순으로 가장 작은 값 선택.
    # 오름차순으로 순회하며 엄격 초과(>)일 때만 갱신해 동률 시 작은 키를 유지한다.
    most_common_pair_count = _CONSEC_PAT_MIN
    best_count = -1
    for k in range(_CONSEC_PAT_MIN, _CONSEC_PAT_MAX + 1):
        if distribution[k] > best_count:
            best_count = distribution[k]
            most_common_pair_count = k

    result = {
        "total_draws": total_draws,
        "avg_consecutive_pairs": round(pair_sum / total_draws, 2),
        "pair_distribution": distribution,
        "pair_distribution_pct": distribution_pct,
        "most_common_pair_count": most_common_pair_count,
        "no_consecutive_count": no_consecutive_count,
        "no_consecutive_pct": round(no_consecutive_count / total_draws * 100, 2),
        "has_triple_count": has_triple_count,
        "has_triple_pct": round(has_triple_count / total_draws * 100, 2),
        "max_consecutive_count": max_consecutive_count,
    }
    _consecutive_cache[cache_key] = result
    return result


# SPEC-LOTTO-063: 끝자리 합계 카테고리 경계.
# low:  합계 < 15
# mid:  15 <= 합계 <= 29
# high: 합계 >= 30
_LDS_LOW_MAX = 15  # low/mid 경계 (미만이 low)
_LDS_HIGH_MIN = 30  # mid/high 경계 (이상이 high)


def _last_digit_sum(nums: list[int]) -> int:
    """본번호 6개의 끝자리(n % 10) 합을 반환합니다 (SPEC-LOTTO-063)."""
    return sum(n % 10 for n in nums)


def _empty_last_digit_sum_stats() -> dict[str, Any]:
    """끝자리 합계 분석의 일관된 빈 구조를 생성합니다 (SPEC-LOTTO-063).

    빈 데이터 / None 모든 경우에서 sum_distribution은 빈 dict이며
    (다른 분석과 달리 0 채움을 하지 않는다) 모든 수치는 0이다.
    """
    return {
        "total_draws": 0,
        "avg_sum": 0.0,
        "min_sum": 0,
        "max_sum": 0,
        "sum_distribution": {},
        "most_common_sum": 0,
        "low_sum_count": 0,
        "mid_sum_count": 0,
        "high_sum_count": 0,
        "low_sum_pct": 0.0,
        "mid_sum_pct": 0.0,
        "high_sum_pct": 0.0,
    }


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-063 끝자리 합계 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-063
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_last_digit_sum_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 끝자리 합계 분포를 분석합니다 (SPEC-LOTTO-063).

    각 회차의 본번호 6개(보너스 제외)에서 끝자리(n % 10) 합을 구한다.
    이론상 범위는 0~54(6 x 9)이며, 합계를 다음 3개 카테고리로 분류한다.
        - low:  합계 < 15
        - mid:  15 <= 합계 <= 29
        - high: 합계 >= 30

    정의:
        - avg_sum:           회차 평균 끝자리 합 (소수 2자리).
        - min_sum/max_sum:   관측된 최소/최대 끝자리 합.
        - sum_distribution:  끝자리 합 → 회차 수. 다른 분석과 달리 실제로
                             관측된 합계 값만 키로 포함한다(미관측 값 0 채움 없음).
        - most_common_sum:   최빈 끝자리 합. 동률 시 더 작은 값을 선택한다.
        - low/mid/high_sum_count: 각 카테고리에 속한 회차 수.
        - low/mid/high_sum_pct:   count / total_draws * 100 (소수 2자리).

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.
    SPEC-LOTTO-055의 get_last_digit_stats(끝자리별 분포)와는 완전히 독립적이다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               모든 수치 0, sum_distribution={} 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_sum, min_sum, max_sum, sum_distribution,
        most_common_sum, low_sum_count, mid_sum_count, high_sum_count,
        low_sum_pct, mid_sum_pct, high_sum_pct} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _last_digit_sum_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result = _empty_last_digit_sum_stats()
        _last_digit_sum_cache[cache_key] = result
        return result

    total_draws = len(draws)
    distribution: dict[int, int] = {}
    sum_total = 0
    low_count = 0
    mid_count = 0
    high_count = 0
    min_sum = None
    max_sum = 0

    for draw in draws:
        s = _last_digit_sum(draw.numbers())  # 본번호 6개 끝자리 합 (보너스 제외)
        distribution[s] = distribution.get(s, 0) + 1
        sum_total += s
        max_sum = max(max_sum, s)
        min_sum = s if min_sum is None else min(min_sum, s)
        if s < _LDS_LOW_MAX:
            low_count += 1
        elif s >= _LDS_HIGH_MIN:
            high_count += 1
        else:
            mid_count += 1

    # 최빈 합계 — count 내림차순, 동률은 합계 오름차순으로 가장 작은 값 선택.
    # 관측된 키만 오름차순 순회하며 엄격 초과(>)일 때만 갱신해 동률 시 작은 키를 유지한다.
    most_common_sum = 0
    best_count = -1
    for s in sorted(distribution):
        if distribution[s] > best_count:
            best_count = distribution[s]
            most_common_sum = s

    result = {
        "total_draws": total_draws,
        "avg_sum": round(sum_total / total_draws, 2),
        "min_sum": min_sum if min_sum is not None else 0,
        "max_sum": max_sum,
        "sum_distribution": distribution,
        "most_common_sum": most_common_sum,
        "low_sum_count": low_count,
        "mid_sum_count": mid_count,
        "high_sum_count": high_count,
        "low_sum_pct": round(low_count / total_draws * 100, 2),
        "mid_sum_pct": round(mid_count / total_draws * 100, 2),
        "high_sum_pct": round(high_count / total_draws * 100, 2),
    }
    _last_digit_sum_cache[cache_key] = result
    return result


# SPEC-LOTTO-064: small/large range 경계 (미만이 small, 이상이 large)
_RANGE_LARGE_MIN = 30


def _most_common_seen(distribution: dict[int, int]) -> int:
    """희소 분포(관측된 키만 포함)에서 최빈값을 반환한다. 동률 시 더 작은 값을 선택한다.

    SPEC-LOTTO-064: 0 채움 없는 분포를 대상으로 한다. 관측된 키만 오름차순
    순회하며 엄격 초과(>)일 때만 갱신해 동률 시 더 작은 키를 유지한다.
    빈 분포면 0을 반환한다. (range 순회형 _most_common_smallest와 구분됨)
    """
    best_value = 0
    best_count = -1
    for v in sorted(distribution):
        if distribution[v] > best_count:
            best_count = distribution[v]
            best_value = v
    return best_value


def _empty_min_max_stats() -> dict[str, Any]:
    """최솟값·최댓값 분석의 일관된 빈 구조를 생성합니다 (SPEC-LOTTO-064).

    빈 데이터 / None 모든 경우에서 세 분포는 빈 dict이며
    (다른 분석과 달리 0 채움을 하지 않는다) 모든 수치는 0이다.
    """
    return {
        "total_draws": 0,
        "avg_min": 0.0,
        "avg_max": 0.0,
        "avg_range": 0.0,
        "min_distribution": {},
        "max_distribution": {},
        "range_distribution": {},
        "most_common_min": 0,
        "most_common_max": 0,
        "most_common_range": 0,
        "small_range_count": 0,
        "large_range_count": 0,
        "small_range_pct": 0.0,
        "large_range_pct": 0.0,
    }


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-064 최솟값·최댓값 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-064
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_min_max_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 최솟값·최댓값·범위 분포를 분석합니다 (SPEC-LOTTO-064).

    각 회차의 본번호 6개(보너스 제외)에서 다음을 구한다.
        - min_num:   6개의 최솟값.
        - max_num:   6개의 최댓값.
        - range_val: max_num - min_num.
    범위를 다음 2개 카테고리로 분류한다.
        - small: range_val < 30
        - large: range_val >= 30

    정의:
        - avg_min/avg_max/avg_range: 회차 평균 (소수 2자리).
        - min/max/range_distribution: 값 → 회차 수. 다른 분석과 달리 실제로
          관측된 값만 키로 포함한다(미관측 값 0 채움 없음).
        - most_common_min/max/range: 각 분포의 최빈값. 동률 시 더 작은 값을 선택한다.
        - small/large_range_count: 각 카테고리에 속한 회차 수.
        - small/large_range_pct:   count / total_draws * 100 (소수 2자리).

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               모든 수치 0, 세 분포 {} 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_min, avg_max, avg_range, min_distribution,
        max_distribution, range_distribution, most_common_min, most_common_max,
        most_common_range, small_range_count, large_range_count,
        small_range_pct, large_range_pct} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _min_max_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result = _empty_min_max_stats()
        _min_max_cache[cache_key] = result
        return result

    total_draws = len(draws)
    min_dist: dict[int, int] = {}
    max_dist: dict[int, int] = {}
    range_dist: dict[int, int] = {}
    min_total = 0
    max_total = 0
    range_total = 0
    small_count = 0
    large_count = 0

    for draw in draws:
        nums = draw.numbers()  # 본번호 6개 (보너스 제외)
        min_num = min(nums)
        max_num = max(nums)
        range_val = max_num - min_num

        min_dist[min_num] = min_dist.get(min_num, 0) + 1
        max_dist[max_num] = max_dist.get(max_num, 0) + 1
        range_dist[range_val] = range_dist.get(range_val, 0) + 1

        min_total += min_num
        max_total += max_num
        range_total += range_val

        if range_val >= _RANGE_LARGE_MIN:
            large_count += 1
        else:
            small_count += 1

    result = {
        "total_draws": total_draws,
        "avg_min": round(min_total / total_draws, 2),
        "avg_max": round(max_total / total_draws, 2),
        "avg_range": round(range_total / total_draws, 2),
        "min_distribution": min_dist,
        "max_distribution": max_dist,
        "range_distribution": range_dist,
        "most_common_min": _most_common_seen(min_dist),
        "most_common_max": _most_common_seen(max_dist),
        "most_common_range": _most_common_seen(range_dist),
        "small_range_count": small_count,
        "large_range_count": large_count,
        "small_range_pct": round(small_count / total_draws * 100, 2),
        "large_range_pct": round(large_count / total_draws * 100, 2),
    }
    _min_max_cache[cache_key] = result
    return result


# SPEC-LOTTO-065: 표준편차 분포 bucket 라벨(정의 순서). 항상 6개 키를 유지한다.
# 경계: "0-4"=[0,4), "4-8"=[4,8), "8-12"=[8,12), "12-16"=[12,16),
#       "16-20"=[16,20), "20+"=[20,∞)
_STD_BUCKET_BOUNDS: tuple[tuple[str, float], ...] = (
    ("0-4", 4.0),
    ("4-8", 8.0),
    ("8-12", 12.0),
    ("12-16", 16.0),
    ("16-20", 20.0),
    ("20+", float("inf")),
)
# SPEC-LOTTO-065: 저/중 편차 카테고리 경계. low<10.0, 10.0<=mid<14.0, high>=14.0.
_STD_LOW_MAX = 10.0
_STD_MID_MAX = 14.0


def _std_bucket_label(std: float) -> str:
    """표준편차 값을 6개 고정 bucket 라벨 중 하나로 매핑합니다 (SPEC-LOTTO-065).

    a-b bucket 은 a <= std < b, 마지막 "20+" 은 std >= 20 을 포함한다.
    """
    for label, upper in _STD_BUCKET_BOUNDS:
        if std < upper:
            return label
    return _STD_BUCKET_BOUNDS[-1][0]  # pragma: no cover — inf 상한으로 도달 불가


def _empty_std_stats() -> dict[str, Any]:
    """표준편차 분석의 일관된 빈 구조를 생성합니다 (SPEC-LOTTO-065).

    빈 데이터 / None 모든 경우에서 모든 수치는 0이며 std_distribution 은
    6개 bucket 키를 모두 0으로 채우고 most_common_bucket 은 첫 라벨 "0-4" 이다.
    """
    return {
        "total_draws": 0,
        "avg_std": 0.0,
        "min_std": 0.0,
        "max_std": 0.0,
        "low_std_count": 0,
        "mid_std_count": 0,
        "high_std_count": 0,
        "low_std_pct": 0.0,
        "mid_std_pct": 0.0,
        "high_std_pct": 0.0,
        "std_distribution": {label: 0 for label, _ in _STD_BUCKET_BOUNDS},
        "most_common_bucket": _STD_BUCKET_BOUNDS[0][0],
    }


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-065 표준편차 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-065
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_std_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 모표준편차 분포를 분석합니다 (SPEC-LOTTO-065).

    각 회차의 본번호 6개(보너스 제외)에서 다음을 구한다.
        - mean     = sum(nums) / 6
        - variance = sum((n - mean)**2) / 6  (모분산, n=6으로 나눔; 표본분산 아님)
        - std      = round(variance ** 0.5, 2)  (회차당 소수 둘째 자리 반올림)
    표준편차 크기로 3개 카테고리로 분류한다.
        - low:  std < 10.0
        - mid:  10.0 <= std < 14.0
        - high: std >= 14.0

    정의:
        - avg_std: 모든 회차 per-draw std 의 평균 (소수 2자리).
        - min_std/max_std: 관측된 per-draw std 의 최소/최대 (소수 2자리).
        - low/mid/high_std_count: 각 카테고리 회차 수 (합은 total_draws).
        - low/mid/high_std_pct:   count / total_draws * 100 (소수 2자리).
        - std_distribution: bucket 라벨 → 회차 수. 6개 고정 키
          ("0-4","4-8","8-12","12-16","16-20","20+")를 항상 정의 순서로 포함하며
          미관측 bucket 도 0 으로 유지한다.
        - most_common_bucket: 최다 count bucket 라벨. 동률 시 정의 순서상 앞선 라벨.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               모든 수치 0, std_distribution 6키 전부 0, most_common_bucket="0-4"
               의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_std, min_std, max_std, low_std_count, mid_std_count,
        high_std_count, low_std_pct, mid_std_pct, high_std_pct, std_distribution,
        most_common_bucket} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _std_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result = _empty_std_stats()
        _std_cache[cache_key] = result
        return result

    distribution: dict[str, int] = {label: 0 for label, _ in _STD_BUCKET_BOUNDS}
    std_total = 0.0
    min_std: float | None = None
    max_std: float | None = None
    low_count = 0
    mid_count = 0
    high_count = 0
    counted = 0

    for draw in draws:
        nums = draw.numbers()  # 본번호 6개 (보너스 제외)
        if len(nums) < 6:  # REQ-SD-015: 6개 미만이면 집계에서 제외
            continue
        mean = sum(nums) / 6
        variance = sum((n - mean) ** 2 for n in nums) / 6  # 모분산 (n=6)
        std = round(variance**0.5, 2)

        counted += 1
        std_total += std
        min_std = std if min_std is None else min(min_std, std)
        max_std = std if max_std is None else max(max_std, std)

        if std < _STD_LOW_MAX:
            low_count += 1
        elif std < _STD_MID_MAX:
            mid_count += 1
        else:
            high_count += 1

        distribution[_std_bucket_label(std)] += 1

    if counted == 0:  # 모든 회차가 6개 미만이었던 예외적 경우
        result = _empty_std_stats()
        _std_cache[cache_key] = result
        return result

    # 동률 시 정의 순서상 앞선 라벨이 이기도록 라벨 순서대로 최댓값을 찾는다.
    most_common_bucket = max(
        (label for label, _ in _STD_BUCKET_BOUNDS),
        key=lambda label: distribution[label],
    )

    result = {
        "total_draws": counted,
        "avg_std": round(std_total / counted, 2),
        "min_std": round(min_std if min_std is not None else 0.0, 2),
        "max_std": round(max_std if max_std is not None else 0.0, 2),
        "low_std_count": low_count,
        "mid_std_count": mid_count,
        "high_std_count": high_count,
        "low_std_pct": round(low_count / counted * 100, 2),
        "mid_std_pct": round(mid_count / counted * 100, 2),
        "high_std_pct": round(high_count / counted * 100, 2),
        "std_distribution": distribution,
        "most_common_bucket": most_common_bucket,
    }
    _std_cache[cache_key] = result
    return result


# SPEC-LOTTO-066: 소수합 분포 bucket 정의 (라벨, 상한 배타).
# 6개 고정 bucket 을 정의 순서대로 유지하며, 마지막 "150+" 는 상한이 없다(이론 최댓값 204).
_PRIME_SUM_BUCKETS: list[str] = ["0-30", "30-60", "60-90", "90-120", "120-150", "150+"]
# 소수합 3단계 분류 경계.
_PRIME_SUM_LOW_MAX = 40   # prime_sum < 40 → low
_PRIME_SUM_MID_MAX = 80   # 40 <= prime_sum <= 80 → mid, prime_sum > 80 → high


def _prime_sum_bucket(s: int) -> str:
    """소수합 정수값을 6개 고정 bucket 라벨로 분류합니다(상한 배타)."""
    if s < 30:
        return "0-30"
    if s < 60:
        return "30-60"
    if s < 90:
        return "60-90"
    if s < 120:
        return "90-120"
    if s < 150:
        return "120-150"
    return "150+"


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-066 소수합 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-066
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_prime_sum_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개 중 소수 번호들의 합(소수합) 분포를 분석합니다 (SPEC-LOTTO-066).

    각 회차의 본번호 6개(보너스 제외)에서 소수(_PRIMES_1_45)에 해당하는 값만 더한
    소수합(prime_sum)을 구한다. 이론적 범위는 0(소수 없음)~204(43+41+37+31+29+23)이다.
    SPEC-058 이 회차별 소수 *개수* 분포라면, 본 함수는 소수 번호들의 *합계* 분포를 다룬다.

    소수합 크기로 3개 카테고리로 분류한다.
        - low:  prime_sum < 40
        - mid:  40 <= prime_sum <= 80
        - high: prime_sum > 80

    정의:
        - avg_prime_sum: 모든 회차 per-draw 소수합의 평균 (소수 2자리).
        - min_prime_sum/max_prime_sum: 관측된 per-draw 소수합의 최소/최대 (정수).
        - low/mid/high_count: 각 카테고리 회차 수 (합은 total_draws).
        - low/mid/high_pct:   count / total_draws * 100 (소수 2자리).
        - prime_sum_distribution: bucket 라벨 → 회차 수. 6개 고정 키
          ("0-30","30-60","60-90","90-120","120-150","150+")를 항상 정의 순서로
          포함하며 미관측 bucket 도 0 으로 유지한다.
        - most_common_bucket: 최다 count bucket 라벨. 동률 시 정의 순서상 앞선 라벨.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               모든 수치 0, prime_sum_distribution 6키 전부 0,
               most_common_bucket="" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_prime_sum, min_prime_sum, max_prime_sum,
        most_common_bucket, prime_sum_distribution, low_count, mid_count,
        high_count, low_pct, mid_pct, high_pct} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _prime_sum_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_prime_sum": 0.0,
            "min_prime_sum": 0,
            "max_prime_sum": 0,
            "most_common_bucket": "",
            "prime_sum_distribution": dict.fromkeys(_PRIME_SUM_BUCKETS, 0),
            "low_count": 0,
            "mid_count": 0,
            "high_count": 0,
            "low_pct": 0.0,
            "mid_pct": 0.0,
            "high_pct": 0.0,
        }
        _prime_sum_cache[cache_key] = result
        return result

    distribution: dict[str, int] = dict.fromkeys(_PRIME_SUM_BUCKETS, 0)
    sum_total = 0
    min_ps: int | None = None
    max_ps: int | None = None
    low_count = 0
    mid_count = 0
    high_count = 0

    for draw in draws:
        prime_sum = sum(
            n for n in draw.numbers() if n in _PRIMES_1_45
        )  # 본번호 6개만 (보너스 제외)

        sum_total += prime_sum
        min_ps = prime_sum if min_ps is None else min(min_ps, prime_sum)
        max_ps = prime_sum if max_ps is None else max(max_ps, prime_sum)

        if prime_sum < _PRIME_SUM_LOW_MAX:
            low_count += 1
        elif prime_sum <= _PRIME_SUM_MID_MAX:
            mid_count += 1
        else:
            high_count += 1

        distribution[_prime_sum_bucket(prime_sum)] += 1

    total = len(draws)
    # 동률 시 정의 순서상 앞선 라벨이 이기도록 라벨 순서대로 최댓값을 찾는다.
    most_common_bucket = max(
        _PRIME_SUM_BUCKETS,
        key=lambda label: distribution[label],
    )

    result = {
        "total_draws": total,
        "avg_prime_sum": round(sum_total / total, 2),
        "min_prime_sum": min_ps if min_ps is not None else 0,
        "max_prime_sum": max_ps if max_ps is not None else 0,
        "most_common_bucket": most_common_bucket,
        "prime_sum_distribution": distribution,
        "low_count": low_count,
        "mid_count": mid_count,
        "high_count": high_count,
        "low_pct": round(low_count / total * 100, 2),
        "mid_pct": round(mid_count / total * 100, 2),
        "high_pct": round(high_count / total * 100, 2),
    }
    _prime_sum_cache[cache_key] = result
    return result


# SPEC-LOTTO-067: 번호 총합 분포 6개 고정 bucket 라벨(상한 포함).
_TOTAL_SUM_BUCKETS: list[str] = [
    "21-80", "81-110", "111-130", "131-150", "151-170", "171-255",
]
# 총합 3단계 분류 경계.
_TOTAL_SUM_LOW_MAX = 110   # total_sum < 110 → low
_TOTAL_SUM_HIGH_MIN = 171  # total_sum > 170 (>= 171) → high, 그 사이는 mid


def _total_sum_bucket(s: int) -> str:
    """총합 정수값을 6개 고정 bucket 라벨로 분류합니다(상한 포함)."""
    if s <= 80:
        return "21-80"
    if s <= 110:
        return "81-110"
    if s <= 130:
        return "111-130"
    if s <= 150:
        return "131-150"
    if s <= 170:
        return "151-170"
    return "171-255"


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-067 번호 총합 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-067
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_total_sum_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 총합(total_sum) 분포를 분석합니다 (SPEC-LOTTO-067).

    각 회차의 본번호 6개(보너스 제외)의 합(total_sum)을 구한다.
    이론적 범위는 21([1,2,3,4,5,6])~255([40,41,42,43,44,45])이며 평균은 약 138,
    표준편차는 약 30이다.

    총합 크기로 3개 카테고리로 분류한다.
        - low:  total_sum < 110
        - mid:  110 <= total_sum <= 170
        - high: total_sum > 170

    정의:
        - avg_total_sum: 모든 회차 per-draw 총합의 평균 (소수 2자리).
        - min_total_sum/max_total_sum: 관측된 per-draw 총합의 최소/최대 (정수).
        - low/mid/high_count: 각 카테고리 회차 수 (합은 total_draws).
        - low/mid/high_pct:   count / total_draws * 100 (소수 2자리).
        - total_sum_distribution: bucket 라벨 → 회차 수. 6개 고정 키
          ("21-80","81-110","111-130","131-150","151-170","171-255")를 항상
          정의 순서로 포함하며 미관측 bucket 도 0 으로 유지한다.
        - most_common_bucket: 최다 count bucket 라벨. 동률 시 정의 순서상 앞선 라벨.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               모든 수치 0, total_sum_distribution 6키 전부 0,
               most_common_bucket="" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_total_sum, min_total_sum, max_total_sum,
        most_common_bucket, total_sum_distribution, low_count, mid_count,
        high_count, low_pct, mid_pct, high_pct} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _total_sum_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_total_sum": 0.0,
            "min_total_sum": 0,
            "max_total_sum": 0,
            "most_common_bucket": "",
            "total_sum_distribution": dict.fromkeys(_TOTAL_SUM_BUCKETS, 0),
            "low_count": 0,
            "mid_count": 0,
            "high_count": 0,
            "low_pct": 0.0,
            "mid_pct": 0.0,
            "high_pct": 0.0,
        }
        _total_sum_cache[cache_key] = result
        return result

    distribution: dict[str, int] = dict.fromkeys(_TOTAL_SUM_BUCKETS, 0)
    sum_total = 0
    min_ts: int | None = None
    max_ts: int | None = None
    low_count = 0
    mid_count = 0
    high_count = 0

    for draw in draws:
        total_sum = sum(draw.numbers())  # 본번호 6개만 (보너스 제외)

        sum_total += total_sum
        min_ts = total_sum if min_ts is None else min(min_ts, total_sum)
        max_ts = total_sum if max_ts is None else max(max_ts, total_sum)

        if total_sum < _TOTAL_SUM_LOW_MAX:
            low_count += 1
        elif total_sum < _TOTAL_SUM_HIGH_MIN:
            mid_count += 1
        else:
            high_count += 1

        distribution[_total_sum_bucket(total_sum)] += 1

    total = len(draws)
    # 동률 시 정의 순서상 앞선 라벨이 이기도록 라벨 순서대로 최댓값을 찾는다.
    most_common_bucket = max(
        _TOTAL_SUM_BUCKETS,
        key=lambda label: distribution[label],
    )

    result = {
        "total_draws": total,
        "avg_total_sum": round(sum_total / total, 2),
        "min_total_sum": min_ts if min_ts is not None else 0,
        "max_total_sum": max_ts if max_ts is not None else 0,
        "most_common_bucket": most_common_bucket,
        "total_sum_distribution": distribution,
        "low_count": low_count,
        "mid_count": mid_count,
        "high_count": high_count,
        "low_pct": round(low_count / total * 100, 2),
        "mid_pct": round(mid_count / total * 100, 2),
        "high_pct": round(high_count / total * 100, 2),
    }
    _total_sum_cache[cache_key] = result
    return result


# SPEC-LOTTO-068: 5개 고정 숫자 구간 (정의 순서가 most_covered_range 동점 우선순위).
_RANGES = ["1-9", "10-19", "20-29", "30-39", "40-45"]


def _number_range(n: int) -> str:
    """번호(1~45)를 5개 고정 구간 키 중 정확히 하나로 분류합니다."""
    if n <= 9:
        return "1-9"
    if n <= 19:
        return "10-19"
    if n <= 29:
        return "20-29"
    if n <= 39:
        return "30-39"
    return "40-45"


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-068 번호 구간별 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-068
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_range_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 구간별 분포를 분석합니다 (SPEC-LOTTO-068).

    각 회차의 본번호 6개(보너스 제외)를 5개 고정 구간
    ("1-9","10-19","20-29","30-39","40-45")으로 분류한다. 총합·소수합 분석과
    달리 한 회차가 여러 구간에 동시에 기여하므로 응답은 중첩 딕셔너리
    (range_stats)이다.

    각 구간(5개)마다 다음 5개 지표를 산출한다.
        - total_count:    모든 회차 전체에서 해당 구간에 속한 번호의 누적 개수.
        - draw_count:     해당 구간 번호를 1개 이상 포함하는 회차 수.
        - avg_per_draw:   total_count / total_draws (소수 2자리).
        - pct_of_numbers: total_count / (total_draws * 6) * 100 (소수 2자리).
        - draw_pct:       draw_count / total_draws * 100 (소수 2자리).

    most_covered_range 는 draw_count 최댓값 구간이며, 동률 시 _RANGES 정의 순서상
    앞선 구간이 이긴다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               5개 구간 전부 0, most_covered_range="" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, most_covered_range, range_stats} 매핑.
        range_stats 는 5개 구간 키를 항상 정의 순서로 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _range_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "most_covered_range": "",
            "range_stats": {
                r: {
                    "total_count": 0,
                    "draw_count": 0,
                    "avg_per_draw": 0.0,
                    "pct_of_numbers": 0.0,
                    "draw_pct": 0.0,
                }
                for r in _RANGES
            },
        }
        _range_dist_cache[cache_key] = result
        return result

    total_count: dict[str, int] = dict.fromkeys(_RANGES, 0)
    draw_count: dict[str, int] = dict.fromkeys(_RANGES, 0)

    for draw in draws:
        seen_ranges: set[str] = set()
        for num in draw.numbers():  # 본번호 6개만 (보너스 제외)
            r = _number_range(num)
            total_count[r] += 1
            seen_ranges.add(r)
        # 회차당 구간 중복 카운트 방지(draw_count 정확성).
        for r in seen_ranges:
            draw_count[r] += 1

    total = len(draws)
    total_numbers = total * 6
    # 동률 시 정의 순서상 앞선 구간이 이기도록 _RANGES 순서대로 최댓값을 찾는다.
    most_covered = max(_RANGES, key=lambda r: draw_count[r])

    range_stats = {
        r: {
            "total_count": total_count[r],
            "draw_count": draw_count[r],
            "avg_per_draw": round(total_count[r] / total, 2),
            "pct_of_numbers": round(total_count[r] / total_numbers * 100, 2),
            "draw_pct": round(draw_count[r] / total * 100, 2),
        }
        for r in _RANGES
    }

    result = {
        "total_draws": total,
        "most_covered_range": most_covered,
        "range_stats": range_stats,
    }
    _range_dist_cache[cache_key] = result
    return result


def count_consecutive_pairs(numbers: list[int]) -> int:
    """본번호 목록에서 연속 쌍 (n, n+1) 의 개수를 센다 (SPEC-LOTTO-069).

    같은 목록에 n 과 n+1 이 모두 존재하면 1개의 연속 쌍으로 센다. 입력은 정렬되어
    있지 않아도 되며, 길이 k 의 연속 런은 k-1 개의 연속 쌍을 만든다
    (예: 14,15,16 → (14,15),(15,16) 2개). wrap-around(45→1)는 세지 않는다.

    Args:
        numbers: 본번호 목록(보너스 제외). 호출 측에서 6개를 전달한다.

    Returns:
        연속 쌍의 개수(정수).
    """
    num_set = set(numbers)
    return sum(1 for n in numbers if n + 1 in num_set)


def _consecutive_bucket(count: int) -> str:
    """연속 쌍 개수를 4개 고정 버킷("0","1","2","3+") 중 하나로 분류한다."""
    if count == 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    return "3+"


def get_consecutive_pairs_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 연속 쌍 개수의 4버킷 분포를 분석합니다 (SPEC-LOTTO-069).

    각 회차의 본번호 6개(보너스 제외)에서 연속 쌍 (n, n+1) 개수를 센 뒤, 전체
    회차를 4개 고정 버킷("0","1","2","3+")으로 분류한다. "3+" 는 3개 이상을
    합치는 오버플로 버킷이다.

    most_common_bucket 은 count 최댓값 버킷이며, 동률 시 _CONSECUTIVE_BUCKETS
    정의 순서상 앞선 버킷이 이긴다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    SPEC-062(get_consecutive_pattern_stats, _consecutive_cache)와는 별개의 독립
    기능이며 해당 코드를 수정/병합하지 않는다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               4개 버킷 전부 0, most_common_bucket="" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_consecutive_pairs, most_common_bucket,
        no_consecutive_pct, has_consecutive_pct, consecutive_distribution} 매핑.
        consecutive_distribution 은 4개 버킷 키를 항상 정의 순서로 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _consecutive_pairs_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_consecutive_pairs": 0.0,
            "most_common_bucket": "",
            "no_consecutive_pct": 0.0,
            "has_consecutive_pct": 0.0,
            "consecutive_distribution": {
                b: {"count": 0, "pct": 0.0} for b in _CONSECUTIVE_BUCKETS
            },
        }
        _consecutive_pairs_cache[cache_key] = result
        return result

    n = len(draws)
    counts = [count_consecutive_pairs(list(d.numbers())) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_CONSECUTIVE_BUCKETS, 0)
    for c in counts:
        dist_counts[_consecutive_bucket(c)] += 1

    total_pairs = sum(counts)
    no_consec = dist_counts["0"]
    # 동률 시 정의 순서상 앞선 버킷이 이기도록 _CONSECUTIVE_BUCKETS 순서대로 최댓값을 찾는다.
    most_common = max(_CONSECUTIVE_BUCKETS, key=lambda b: dist_counts[b])

    result = {
        "total_draws": n,
        "avg_consecutive_pairs": round(total_pairs / n, 2),
        "most_common_bucket": most_common,
        "no_consecutive_pct": round(no_consec / n * 100, 2),
        "has_consecutive_pct": round((n - no_consec) / n * 100, 2),
        "consecutive_distribution": {
            b: {
                "count": dist_counts[b],
                "pct": round(dist_counts[b] / n * 100, 2),
            }
            for b in _CONSECUTIVE_BUCKETS
        },
    }
    _consecutive_pairs_cache[cache_key] = result
    return result


def compute_ac_value(numbers: list[int]) -> int:
    """6개 번호의 모든 쌍에 대한 절대 차이 중 distinct 값의 개수를 반환합니다 (SPEC-LOTTO-070).

    AC값(Arithmetic Complexity)은 한 회차 번호 조합이 얼마나 "다양한 간격"으로
    구성되어 있는지를 나타내는 지표다. C(6,2)=15개 쌍의 절대 차이를 집합으로 모은 뒤
    그 원소 개수를 센다. 정렬 여부·입력 순서와 무관하다.

    예: [1,2,3,10,11,12] → distinct 차이 {1,2,7,8,9,10,11} → 7.

    Args:
        numbers: 본번호 리스트(보너스 제외). 일반적으로 6개.

    Returns:
        서로 다른 절대 차이의 개수(int). 1~45 범위 6개 조합에서 최대 15까지 가능.
    """
    nums = list(numbers)
    diffs = {abs(a - b) for i, a in enumerate(nums) for b in nums[i + 1:]}
    return len(diffs)


def get_ac_value_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 AC값(산술 복잡도)의 0~14 전 구간 분포를 분석합니다 (SPEC-LOTTO-070).

    각 회차의 본번호 6개(보너스 제외)에 대해 compute_ac_value로 AC값을 산출한 뒤,
    전체 회차를 "0".."14" 15개 고정 키로 분류한다. AC값이 14 이상인 회차는 마지막
    키 "14" 오버플로 버킷에 합산한다(min(ac, 14)). 단 avg_ac_value 와
    high_diversity_pct(AC>=9 판정)는 clamp 이전 원본 AC값으로 계산한다.

    most_common_ac 는 count 최댓값 AC값(정수)이며, 동률 시 _AC_KEYS 정의 순서상
    앞선(=더 작은) AC값이 이긴다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               15개 키 전부 0, most_common_ac=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_ac_value, most_common_ac, high_diversity_pct,
        ac_distribution} 매핑. ac_distribution 은 "0".."14" 15개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _ac_value_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_ac_value": 0.0,
            "most_common_ac": 0,
            "high_diversity_pct": 0.0,
            "ac_distribution": {k: {"count": 0, "pct": 0.0} for k in _AC_KEYS},
        }
        _ac_value_cache[cache_key] = result
        return result

    n = len(draws)
    ac_values = [compute_ac_value(list(d.numbers())) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_AC_KEYS, 0)
    for ac in ac_values:
        # 오버플로 클램프: AC>=14 회차는 "14" 버킷에 합산한다(KeyError 방지).
        dist_counts[str(min(ac, 14))] += 1

    # avg / high-diversity 는 clamp 이전 원본 AC값을 사용한다(REQ-AC-007, REQ-AC-008).
    total_ac = sum(ac_values)
    high_diversity = sum(1 for ac in ac_values if ac >= _AC_DIVERSITY_THRESHOLD)
    # 동률 시 정의 순서상 앞선(=더 작은) AC값이 이기도록 _AC_KEYS 순서대로 최댓값을 찾는다.
    most_common = max(_AC_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_ac_value": round(total_ac / n, 2),
        "most_common_ac": int(most_common),
        "high_diversity_pct": round(high_diversity / n * 100, 2),
        "ac_distribution": {
            k: {"count": dist_counts[k], "pct": round(dist_counts[k] / n * 100, 2)}
            for k in _AC_KEYS
        },
    }
    _ac_value_cache[cache_key] = result
    return result


def _compute_median(nums: list[int]) -> float:
    """본번호 6개의 중앙값을 반환합니다 (SPEC-LOTTO-071).

    오름차순 정렬 후 3번째·4번째 값의 산술 평균 (c+d)/2.0 을 산출한다.
    입력 순서와 무관하며 항상 6개 원소를 가정한다(본번호 6개).

    Args:
        nums: 본번호 6개 정수 리스트(보너스 제외).

    Returns:
        정렬된 [a,b,c,d,e,f]의 (c+d)/2.0 (float).
    """
    sorted_nums = sorted(nums)
    return (sorted_nums[2] + sorted_nums[3]) / 2.0


def _median_bucket(median: float) -> str:
    """중앙값을 9개 고정 버킷 키 중 하나로 분류합니다 (SPEC-LOTTO-071).

    경계값은 상위 버킷에 귀속한다(예: 5.5 → "6-10", 40.5 → "41-45").

    Args:
        median: 회차 중앙값.

    Returns:
        "1-5".."41-45" 9개 키 중 해당 구간 키.
    """
    if median < 5.5:
        return "1-5"
    if median < 10.5:
        return "6-10"
    if median < 15.5:
        return "11-15"
    if median < 20.5:
        return "16-20"
    if median < 25.5:
        return "21-25"
    if median < 30.5:
        return "26-30"
    if median < 35.5:
        return "31-35"
    if median < 40.5:
        return "36-40"
    return "41-45"


def get_median_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 중앙값(median)의 9개 구간 분포를 분석합니다 (SPEC-LOTTO-071).

    각 회차의 본번호 6개(보너스 제외)를 정렬한 [a,b,c,d,e,f]의 (c+d)/2.0 을
    중앙값으로 산출한 뒤, 전체 회차를 "1-5".."41-45" 9개 고정 키로 분류한다.
    경계값은 상위 버킷에 귀속한다(예: 5.5 → "6-10").

    avg_median 은 회차별 중앙값의 산술 평균(소수 2자리 반올림)이다.
    most_common_range 는 count 최댓값 구간 키이며, 동률 시 _MEDIAN_KEYS 정의
    순서상 앞선(=하한이 더 작은) 구간이 이긴다.
    low_median_pct 는 중앙값 < 23.0(strict)인 회차 비율(%)이다(median==23.0 제외).

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               9개 키 전부 0, most_common_range="1-5" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_median, most_common_range, low_median_pct,
        median_distribution} 매핑. median_distribution 은 9개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _median_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        result: dict[str, Any] = {
            "total_draws": 0,
            "avg_median": 0.0,
            "most_common_range": "1-5",
            "low_median_pct": 0.0,
            "median_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _MEDIAN_KEYS
            },
        }
        _median_cache[cache_key] = result
        return result

    n = len(draws)
    medians = [_compute_median(list(d.numbers())) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_MEDIAN_KEYS, 0)
    for m in medians:
        dist_counts[_median_bucket(m)] += 1

    low_count = sum(1 for m in medians if m < _MEDIAN_CENTER)
    # 동률 시 정의 순서상 앞선(=하한이 더 작은) 구간이 이기도록 _MEDIAN_KEYS 순서대로 찾는다.
    most_common = max(_MEDIAN_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_median": round(sum(medians) / n, 2),
        "most_common_range": most_common,
        "low_median_pct": round(low_count / n * 100, 2),
        "median_distribution": {
            k: {"count": dist_counts[k], "pct": round(dist_counts[k] / n * 100, 2)}
            for k in _MEDIAN_KEYS
        },
    }
    _median_cache[cache_key] = result
    return result


def get_last_digit_unique_stats(
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    """회차별 본번호 6개의 유니크 끝자리 개수(1~6) 분포를 분석합니다 (SPEC-LOTTO-072).

    각 회차의 본번호 6개(보너스 제외)에서 서로 다른 끝자리(n % 10) 값이 몇 종류나
    나타나는지를 센다(`len(set(n % 10 ...))`). 값의 범위는 1(모두 같은 끝자리)부터
    6(모두 다른 끝자리)이며, 전체 회차를 "1".."6" 6개 고정 키로 분류한다.

    avg_unique_count 는 회차별 유니크 개수의 산술 평균(소수 2자리 반올림)이다.
    most_common_count 는 count 최댓값 개수이며, 동률 시 _UNIQUE_DIGIT_KEYS 정의
    순서상 앞선(=더 작은) 개수가 이긴다.
    all_different_pct 는 유니크 개수가 정확히 6인 회차 비율(%)이다.

    SPEC-055(끝자리별 출현 빈도)·SPEC-063(끝자리 합계)과는 계산 대상이 다른 별개 기능.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 0, most_common_count=1 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_unique_count, most_common_count, all_different_pct,
        unique_distribution} 매핑. unique_distribution 은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _last_digit_unique_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_unique_count": 0.0,
            "most_common_count": 1,
            "all_different_pct": 0.0,
            "unique_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _UNIQUE_DIGIT_KEYS
            },
        }
        _last_digit_unique_cache[cache_key] = empty_result
        return empty_result

    n = len(draws)
    unique_counts = [len({num % 10 for num in d.numbers()}) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_UNIQUE_DIGIT_KEYS, 0)
    for c in unique_counts:
        dist_counts[str(c)] += 1

    all_diff_count = sum(1 for c in unique_counts if c == 6)
    # 동률 시 정의 순서상 앞선(=더 작은) 개수가 이기도록 _UNIQUE_DIGIT_KEYS 순서대로 찾는다.
    most_common_key = max(_UNIQUE_DIGIT_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_unique_count": round(sum(unique_counts) / n, 2),
        "most_common_count": int(most_common_key),
        "all_different_pct": round(all_diff_count / n * 100, 2),
        "unique_distribution": {
            k: {
                "count": dist_counts[k],
                "pct": round(dist_counts[k] / n * 100, 2),
            }
            for k in _UNIQUE_DIGIT_KEYS
        },
    }
    _last_digit_unique_cache[cache_key] = result
    return result


def get_mult3_stats(
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    """회차별 본번호 6개 중 3의 배수 포함 개수(0~6) 분포를 분석합니다 (SPEC-LOTTO-073).

    각 회차의 본번호 6개(보너스 제외)에서 3으로 나누어 떨어지는 번호의 개수를 센다.
    1~45 중 3의 배수는 {3,6,...,45} 15개이며 회차별 개수의 범위는 0(없음)~6(전부)이다.
    전체 회차를 "0".."6" 7개 고정 키로 분류한다.

    avg_mult3_count 는 회차별 3배수 개수의 산술 평균(소수 2자리 반올림)이다.
    most_common_count 는 count 최댓값 개수이며, 동률 시 _MULT3_KEYS 정의 순서상
    앞선(=더 작은) 개수가 이긴다.
    high_mult3_pct 는 3배수 개수가 3 이상인 회차 비율(%, 소수 2자리 반올림)이다.

    SPEC-058(소수/합성수 분포)·SPEC-066(소수합)과는 계산 대상이 다른 별개 기능.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               7개 키 전부 0, most_common_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_mult3_count, most_common_count, high_mult3_pct,
        mult3_distribution} 매핑. mult3_distribution 은 7개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _mult3_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_mult3_count": 0.0,
            "most_common_count": 0,
            "high_mult3_pct": 0.0,
            "mult3_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _MULT3_KEYS
            },
        }
        _mult3_cache[cache_key] = empty_result
        return empty_result

    n = len(draws)
    mult3_counts = [sum(1 for num in d.numbers() if num % 3 == 0) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_MULT3_KEYS, 0)
    for c in mult3_counts:
        dist_counts[str(c)] += 1

    high_count = sum(1 for c in mult3_counts if c >= 3)
    # 동률 시 정의 순서상 앞선(=더 작은) 개수가 이기도록 _MULT3_KEYS 순서대로 찾는다.
    most_common_key = max(_MULT3_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_mult3_count": round(sum(mult3_counts) / n, 2),
        "most_common_count": int(most_common_key),
        "high_mult3_pct": round(high_count / n * 100, 2),
        "mult3_distribution": {
            k: {
                "count": dist_counts[k],
                "pct": round(dist_counts[k] / n * 100, 2),
            }
            for k in _MULT3_KEYS
        },
    }
    _mult3_cache[cache_key] = result
    return result


def get_even_count_stats(
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    """회차별 본번호 6개 중 짝수 포함 개수(0~6) 분포를 분석합니다 (SPEC-LOTTO-074).

    각 회차의 본번호 6개(보너스 제외)에서 짝수(2로 나누어 떨어지는)의 개수를 센다.
    1~45 중 짝수는 {2,4,...,44} 22개이며 회차별 개수의 범위는 0(없음)~6(전부)이다.
    전체 회차를 "0".."6" 7개 고정 키로 분류한다.

    avg_even_count 는 회차별 짝수 개수의 산술 평균(소수 2자리 반올림)이다.
    most_common_count 는 count 최댓값 개수이며, 동률 시 _EVEN_COUNT_KEYS 정의 순서상
    앞선(=더 작은) 개수가 이긴다.
    high_even_pct 는 짝수 개수가 3 이상인 회차 비율(%, 소수 2자리 반올림)이다.

    SPEC-061(홀짝 비율; get_odd_even_stats)과는 계산·반환 구조가 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               7개 키 전부 0, most_common_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_even_count, most_common_count, high_even_pct,
        even_count_distribution} 매핑. even_count_distribution 은 7개 키를
        항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _even_count_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_even_count": 0.0,
            "most_common_count": 0,
            "high_even_pct": 0.0,
            "even_count_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _EVEN_COUNT_KEYS
            },
        }
        _even_count_cache[cache_key] = empty_result
        return empty_result

    n = len(draws)
    even_counts = [sum(1 for num in d.numbers() if num % 2 == 0) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_EVEN_COUNT_KEYS, 0)
    for c in even_counts:
        dist_counts[str(c)] += 1

    high_count = sum(1 for c in even_counts if c >= 3)
    # 동률 시 정의 순서상 앞선(=더 작은) 개수가 이기도록 _EVEN_COUNT_KEYS 순서대로 찾는다.
    most_common_key = max(_EVEN_COUNT_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_even_count": round(sum(even_counts) / n, 2),
        "most_common_count": int(most_common_key),
        "high_even_pct": round(high_count / n * 100, 2),
        "even_count_distribution": {
            k: {
                "count": dist_counts[k],
                "pct": round(dist_counts[k] / n * 100, 2),
            }
            for k in _EVEN_COUNT_KEYS
        },
    }
    _even_count_cache[cache_key] = result
    return result


def get_mult5_stats(
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    """회차별 본번호 6개 중 5의 배수 포함 개수(0~6) 분포를 분석합니다 (SPEC-LOTTO-075).

    각 회차의 본번호 6개(보너스 제외)에서 5로 나누어 떨어지는 번호의 개수를 센다.
    1~45 중 5의 배수는 {5,10,...,45} 9개이며 회차별 개수의 범위는 0(없음)~6(전부)이다.
    전체 회차를 "0".."6" 7개 고정 키로 분류한다.

    avg_mult5_count 는 회차별 5배수 개수의 산술 평균(소수 2자리 반올림)이다.
    most_common_count 는 count 최댓값 개수이며, 동률 시 _MULT5_KEYS 정의 순서상
    앞선(=더 작은) 개수가 이긴다.
    high_mult5_pct 는 5배수 개수가 3 이상인 회차 비율(%, 소수 2자리 반올림)이다.

    SPEC-073(3의 배수 개수)·SPEC-074(짝수 개수)와는 계산 대상이 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               7개 키 전부 0, most_common_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_mult5_count, most_common_count, high_mult5_pct,
        mult5_distribution} 매핑. mult5_distribution 은 7개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _mult5_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_mult5_count": 0.0,
            "most_common_count": 0,
            "high_mult5_pct": 0.0,
            "mult5_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _MULT5_KEYS
            },
        }
        _mult5_cache[cache_key] = empty_result
        return empty_result

    n = len(draws)
    mult5_counts = [sum(1 for num in d.numbers() if num % 5 == 0) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_MULT5_KEYS, 0)
    for c in mult5_counts:
        dist_counts[str(c)] += 1

    high_count = sum(1 for c in mult5_counts if c >= 3)
    # 동률 시 정의 순서상 앞선(=더 작은) 개수가 이기도록 _MULT5_KEYS 순서대로 찾는다.
    most_common_key = max(_MULT5_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_mult5_count": round(sum(mult5_counts) / n, 2),
        "most_common_count": int(most_common_key),
        "high_mult5_pct": round(high_count / n * 100, 2),
        "mult5_distribution": {
            k: {
                "count": dist_counts[k],
                "pct": round(dist_counts[k] / n * 100, 2),
            }
            for k in _MULT5_KEYS
        },
    }
    _mult5_cache[cache_key] = result
    return result


def get_mult4_stats(
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    """회차별 본번호 6개 중 4의 배수 포함 개수(0~6) 분포를 분석합니다 (SPEC-LOTTO-076).

    각 회차의 본번호 6개(보너스 제외)에서 4로 나누어 떨어지는 번호의 개수를 센다.
    1~45 중 4의 배수는 {4,8,12,...,44} 11개이며 회차별 개수의 범위는 0(없음)~6(전부)이다.
    전체 회차를 "0".."6" 7개 고정 키로 분류한다.

    avg_mult4_count 는 회차별 4배수 개수의 산술 평균(소수 2자리 반올림)이다.
    most_common_count 는 count 최댓값 개수이며, 동률 시 _MULT4_KEYS 정의 순서상
    앞선(=더 작은) 개수가 이긴다.
    high_mult4_pct 는 4배수 개수가 3 이상인 회차 비율(%, 소수 2자리 반올림)이다.

    SPEC-073(3의 배수)·SPEC-074(짝수)·SPEC-075(5의 배수)와는 계산 대상이 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               7개 키 전부 0, most_common_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_mult4_count, most_common_count, high_mult4_pct,
        mult4_distribution} 매핑. mult4_distribution 은 7개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _mult4_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_mult4_count": 0.0,
            "most_common_count": 0,
            "high_mult4_pct": 0.0,
            "mult4_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _MULT4_KEYS
            },
        }
        _mult4_cache[cache_key] = empty_result
        return empty_result

    n = len(draws)
    mult4_counts = [sum(1 for num in d.numbers() if num % 4 == 0) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_MULT4_KEYS, 0)
    for c in mult4_counts:
        dist_counts[str(c)] += 1

    high_count = sum(1 for c in mult4_counts if c >= 3)
    # 동률 시 정의 순서상 앞선(=더 작은) 개수가 이기도록 _MULT4_KEYS 순서대로 찾는다.
    most_common_key = max(_MULT4_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_mult4_count": round(sum(mult4_counts) / n, 2),
        "most_common_count": int(most_common_key),
        "high_mult4_pct": round(high_count / n * 100, 2),
        "mult4_distribution": {
            k: {
                "count": dist_counts[k],
                "pct": round(dist_counts[k] / n * 100, 2),
            }
            for k in _MULT4_KEYS
        },
    }
    _mult4_cache[cache_key] = result
    return result


def get_single_digit_stats(
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    """회차별 본번호 6개 중 1자리 번호(1~9) 포함 개수(0~6) 분포를 분석합니다 (SPEC-LOTTO-077).

    각 회차의 본번호 6개(보너스 제외)에서 1자리 번호의 개수를 센다.
    1~45 중 1자리 번호는 {1,2,3,4,5,6,7,8,9} 9개이며 회차별 개수의 범위는
    0(없음)~6(전부)이다. 전체 회차를 "0".."6" 7개 고정 키로 분류한다.

    avg_single_count 는 회차별 1자리 개수의 산술 평균(소수 2자리 반올림)이다.
    most_common_count 는 count 최댓값 개수이며, 동률 시 _SINGLE_DIGIT_KEYS 정의 순서상
    앞선(=더 작은) 개수가 이긴다.
    high_single_pct 는 1자리 개수가 3 이상인 회차 비율(%, 소수 2자리 반올림)이다.

    SPEC-073(3의 배수)·SPEC-074(짝수)·SPEC-075(5의 배수)·SPEC-076(4의 배수)와는
    계산 대상이 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               7개 키 전부 0, most_common_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_single_count, most_common_count, high_single_pct,
        single_distribution} 매핑. single_distribution 은 7개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _single_digit_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_single_count": 0.0,
            "most_common_count": 0,
            "high_single_pct": 0.0,
            "single_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _SINGLE_DIGIT_KEYS
            },
        }
        _single_digit_cache[cache_key] = empty_result
        return empty_result

    n = len(draws)
    single_counts = [
        sum(1 for num in d.numbers() if num in _SINGLE_DIGIT_SET) for d in draws
    ]

    dist_counts: dict[str, int] = dict.fromkeys(_SINGLE_DIGIT_KEYS, 0)
    for c in single_counts:
        dist_counts[str(c)] += 1

    high_count = sum(1 for c in single_counts if c >= 3)
    # 동률 시 정의 순서상 앞선(=더 작은) 개수가 이기도록 _SINGLE_DIGIT_KEYS 순서대로 찾는다.
    most_common_key = max(_SINGLE_DIGIT_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_single_count": round(sum(single_counts) / n, 2),
        "most_common_count": int(most_common_key),
        "high_single_pct": round(high_count / n * 100, 2),
        "single_distribution": {
            k: {
                "count": dist_counts[k],
                "pct": round(dist_counts[k] / n * 100, 2),
            }
            for k in _SINGLE_DIGIT_KEYS
        },
    }
    _single_digit_cache[cache_key] = result
    return result


def _count_triple_runs(numbers: list) -> int:
    """본번호에서 3개 이상 연속한 묶음(triple run)의 개수를 센다 (SPEC-LOTTO-078).

    정렬 후 인접 값 차이가 1이면 연속으로 누적하고, 끊기는 시점에 누적 길이가
    3 이상이면 묶음 1개로 계수한다. 마지막 묶음도 동일하게 처리한다.

    예: [1,2,3,7,8,9] → {1,2,3},{7,8,9} 2개. [3,4,...] → {3,4}는 2연속이라 0개.
    """
    sorted_nums = sorted(numbers)
    groups = 0
    run_len = 1
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] == sorted_nums[i - 1] + 1:
            run_len += 1
        else:
            if run_len >= 3:
                groups += 1
            run_len = 1
    if run_len >= 3:
        groups += 1
    return groups


def _max_run_length(numbers: list) -> int:
    """본번호에서 가장 긴 연속 구간의 길이를 반환한다 (SPEC-LOTTO-078).

    정렬 후 인접 값 차이가 1인 동안 길이를 누적하며 최댓값을 추적한다.
    모두 고립이면 1을 반환한다(단일 번호도 길이 1로 간주).
    """
    sorted_nums = sorted(numbers)
    max_run = 1
    run = 1
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] == sorted_nums[i - 1] + 1:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    return max_run


def get_triple_run_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개 중 3연속 이상 묶음 수(0~2) 분포를 분석합니다 (SPEC-LOTTO-078).

    각 회차의 본번호 6개(보너스 제외)에서 3개 이상 연속한 묶음(triple run) 수를 센다.
    6개 번호이므로 묶음 수의 범위는 0~2(예: 3+3=6)이며, 전체 회차를 "0","1","2"
    3개 고정 키로 분류한다.

    has_triple_pct 는 묶음 수가 1 이상인 회차 비율(%, 소수 2자리 반올림)이다.
    most_common_group_count 는 count 최댓값 묶음 수이며, 동률 시 _TRIPLE_RUN_KEYS
    정의 순서상 앞선(=더 작은) 값이 이긴다.
    avg_max_run 는 회차별 최대 연속 길이의 산술 평균(소수 2자리 반올림)이다.

    SPEC-062(연속 패턴)·SPEC-069(연속 쌍)와는 계산 대상이 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               3개 키 전부 0, most_common_group_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, has_triple_pct, most_common_group_count, avg_max_run,
        triple_distribution} 매핑. triple_distribution 은 3개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _triple_run_cache.get(cache_key)
    if cached is not None:
        return cached

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "has_triple_pct": 0.0,
            "most_common_group_count": 0,
            "avg_max_run": 0.0,
            "triple_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _TRIPLE_RUN_KEYS
            },
        }
        _triple_run_cache[cache_key] = empty_result
        return empty_result

    n = len(draws)
    group_counts = [_count_triple_runs(d.numbers()) for d in draws]
    max_runs = [_max_run_length(d.numbers()) for d in draws]

    dist_counts: dict[str, int] = dict.fromkeys(_TRIPLE_RUN_KEYS, 0)
    for g in group_counts:
        dist_counts[str(g)] += 1

    has_triple = sum(1 for g in group_counts if g >= 1)
    # 동률 시 정의 순서상 앞선(=더 작은) 묶음 수가 이기도록 _TRIPLE_RUN_KEYS 순서대로 찾는다.
    most_common_key = max(_TRIPLE_RUN_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "has_triple_pct": round(has_triple / n * 100, 2),
        "most_common_group_count": int(most_common_key),
        "avg_max_run": round(sum(max_runs) / n, 2),
        "triple_distribution": {
            k: {
                "count": dist_counts[k],
                "pct": round(dist_counts[k] / n * 100, 2),
            }
            for k in _TRIPLE_RUN_KEYS
        },
    }
    _triple_run_cache[cache_key] = result
    return result


# @MX:NOTE: [AUTO] SPEC-LOTTO-079 — 끝자리 합을 6개 고정 구간 버킷으로 분류
# @MX:SPEC: SPEC-LOTTO-079 REQ-DSD-001
def _digit_sum_bucket(s: int) -> str:
    """끝자리 합 s를 6개 고정 구간 버킷 라벨로 변환한다 (SPEC-LOTTO-079).

    경계: <=9→"0-9", <=14→"10-14", <=19→"15-19", <=24→"20-24",
          <=29→"25-29", 그 외(>=30)→"30+".
    """
    if s <= 9:
        return "0-9"
    elif s <= 14:
        return "10-14"
    elif s <= 19:
        return "15-19"
    elif s <= 24:
        return "20-24"
    elif s <= 29:
        return "25-29"
    else:
        return "30+"


def get_digit_sum_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개 끝자리 합계의 구간별 분포를 분석합니다 (SPEC-LOTTO-079).

    각 회차의 본번호 6개(보너스 제외) 끝자리(n % 10) 합을 구한 뒤,
    6개 고정 구간 버킷("0-9","10-14","15-19","20-24","25-29","30+")으로 분류한다.

    정의:
        - avg_digit_sum:    회차 평균 끝자리 합 (소수 2자리).
        - most_common_range: 최빈 구간. 동률 시 _DIGIT_SUM_KEYS 정의 순서상
                             앞선(=더 작은) 구간을 선택한다.
        - high_digit_sum_pct: 끝자리 합이 25 이상인 회차 비율(%, 소수 2자리).
        - digit_sum_distribution: 6개 고정 키를 항상 포함(미관측 0 채움).

    SPEC-LOTTO-063의 get_last_digit_sum_stats(low/mid/high 3카테고리, 관측값 only)와는
    출력 구조가 완전히 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 0, most_common_range="0-9" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_digit_sum, most_common_range, high_digit_sum_pct,
        digit_sum_distribution} 매핑. digit_sum_distribution 은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _digit_sum_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _DIGIT_SUM_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_digit_sum": 0.0,
            "most_common_range": "0-9",
            "high_digit_sum_pct": 0.0,
            "digit_sum_distribution": dist,
        }
        _digit_sum_dist_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    digit_sums: list[int] = []
    for draw in draws:
        s = sum(n % 10 for n in draw.numbers())  # 본번호 6개 끝자리 합 (보너스 제외)
        digit_sums.append(s)
        dist[_digit_sum_bucket(s)]["count"] += 1

    for k in _DIGIT_SUM_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    avg = round(sum(digit_sums) / total, 2)
    # 동률 시 정의 순서상 앞선(=더 작은) 구간이 이기도록 _DIGIT_SUM_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _DIGIT_SUM_KEYS)
    most_common = next(k for k in _DIGIT_SUM_KEYS if dist[k]["count"] == max_cnt)
    high = sum(1 for s in digit_sums if s >= 25)

    result = {
        "total_draws": total,
        "avg_digit_sum": avg,
        "most_common_range": most_common,
        "high_digit_sum_pct": round(high / total * 100, 2),
        "digit_sum_distribution": dist,
    }
    _digit_sum_dist_cache[cache_key] = result
    return result


# @MX:NOTE: [AUTO] SPEC-LOTTO-080 — max_gap을 6개 고정 구간 버킷으로 분류
# @MX:SPEC: SPEC-LOTTO-080 REQ-MGD-002
def _max_gap_bucket(g: int) -> str:
    """번호 간격 최대값 g를 6개 고정 구간 버킷 라벨로 변환한다 (SPEC-LOTTO-080).

    경계: <=5→"1-5", <=10→"6-10", <=15→"11-15", <=20→"16-20",
          <=30→"21-30", 그 외(>=31)→"31+".
    """
    if g <= 5:
        return "1-5"
    elif g <= 10:
        return "6-10"
    elif g <= 15:
        return "11-15"
    elif g <= 20:
        return "16-20"
    elif g <= 30:
        return "21-30"
    else:
        return "31+"


def get_max_gap_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 인접 간격 최댓값(max_gap) 구간 분포를 분석합니다 (SPEC-LOTTO-080).

    각 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이 5개의 최댓값(max_gap)을
    구한 뒤, 6개 고정 구간 버킷("1-5","6-10","11-15","16-20","21-30","31+")으로
    분류한다.

    정의:
        - max_gap:           정렬 본번호 인접 차이 중 최댓값 (회차당 1개).
        - avg_max_gap:       회차 평균 max_gap (소수 2자리).
        - most_common_range: 최빈 구간. 동률 시 _MAX_GAP_KEYS 정의 순서상
                             앞선(=더 작은) 구간을 선택한다.
        - high_gap_pct:      max_gap이 21 이상인 회차 비율(%, 소수 2자리).
        - max_gap_distribution: 6개 고정 키를 항상 포함(미관측 0 채움).

    SPEC-LOTTO-056의 get_gap_stats(small/medium/large 분류 + avg_max_gap 단일 수치)와는
    출력 구조가 완전히 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 0, most_common_range="1-5" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_max_gap, most_common_range, high_gap_pct,
        max_gap_distribution} 매핑. max_gap_distribution 은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _max_gap_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _MAX_GAP_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_max_gap": 0.0,
            "most_common_range": "1-5",
            "high_gap_pct": 0.0,
            "max_gap_distribution": dist,
        }
        _max_gap_dist_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    max_gaps: list[int] = []
    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        # 인접 쌍의 차이 5개 중 최댓값
        g = max(b - a for a, b in zip(nums, nums[1:]))  # noqa: B905 — Python 3.9 호환
        max_gaps.append(g)
        dist[_max_gap_bucket(g)]["count"] += 1

    for k in _MAX_GAP_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    avg = round(sum(max_gaps) / total, 2)
    # 동률 시 정의 순서상 앞선(=더 작은) 구간이 이기도록 _MAX_GAP_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _MAX_GAP_KEYS)
    most_common = next(k for k in _MAX_GAP_KEYS if dist[k]["count"] == max_cnt)
    high = sum(1 for g in max_gaps if g >= 21)

    result = {
        "total_draws": total,
        "avg_max_gap": avg,
        "most_common_range": most_common,
        "high_gap_pct": round(high / total * 100, 2),
        "max_gap_distribution": dist,
    }
    _max_gap_dist_cache[cache_key] = result
    return result


def _count_even_runs(numbers: list[int]) -> int:
    """본번호 중 간격이 정확히 2인 연속 짝수 묶음(길이>=2)의 수를 센다 (SPEC-LOTTO-081).

    짝수만 추출해 정렬한 뒤, 인접 차이가 2인 구간(길이>=2)의 수를 산출한다.
    예) [2,4,6,10,20,30] → {2,4,6} 1개, [2,4,10,12,20,30] → {2,4},{10,12} 2개.
    간격이 4 이상인 짝수(예: 2,6)는 연속 짝수가 아니며, 단일 짝수(길이1)는 제외한다.

    Args:
        numbers: 한 회차 본번호 6개(보너스 제외). 정렬 여부 무관.

    Returns:
        간격 2 짝수 연속 묶음의 수(0~3).
    """
    evens = sorted(n for n in numbers if n % 2 == 0)
    if len(evens) < 2:
        return 0
    groups = 0
    run_len = 1
    for i in range(1, len(evens)):
        if evens[i] == evens[i - 1] + 2:
            run_len += 1
        else:
            if run_len >= 2:
                groups += 1
            run_len = 1
    if run_len >= 2:
        groups += 1
    return groups


def get_even_run_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 짝수 연속 묶음(간격=2) 수의 분포를 분석합니다 (SPEC-LOTTO-081).

    각 회차의 본번호 6개(보너스 제외) 중 짝수만 추출하여, 간격이 정확히 2인
    연속 짝수 묶음(길이>=2)의 수를 산출한 뒤 4개 고정 키("0","1","2","3")로
    분류한다. 6개 모두 짝수일 때 최대 묶음 수는 3개이다.

    정의:
        - even_run:                간격 2 짝수 연속 묶음(회차당 0~3개).
        - has_even_run_pct:        묶음>=1 회차 비율(%, 소수 2자리).
        - most_common_group_count: 최빈 묶음 수. 동률 시 _EVEN_RUN_KEYS
                                   정의 순서상 앞선(=더 작은) 값을 선택한다.
        - avg_even_run_count:      회차당 평균 묶음 수(소수 2자리).
        - even_run_distribution:   4개 고정 키를 항상 포함(미관측 0 채움).

    SPEC-074(짝수 총 개수)·SPEC-069(연속 쌍, 간격1)와는 출력 구조와 정의가
    완전히 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               4개 키 전부 0, most_common_group_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, has_even_run_pct, most_common_group_count,
        avg_even_run_count, even_run_distribution} 매핑.
        even_run_distribution 은 4개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _even_run_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _EVEN_RUN_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "has_even_run_pct": 0.0,
            "most_common_group_count": 0,
            "avg_even_run_count": 0.0,
            "even_run_distribution": dist,
        }
        _even_run_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    run_counts: list[int] = []
    for draw in draws:
        c = _count_even_runs(draw.numbers())  # 본번호 6개 (보너스 제외)
        run_counts.append(c)
        dist[str(c)]["count"] += 1

    for k in _EVEN_RUN_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    has = sum(1 for c in run_counts if c >= 1)
    # 동률 시 정의 순서상 앞선(=더 작은) 키가 이기도록 _EVEN_RUN_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _EVEN_RUN_KEYS)
    most_common = int(next(k for k in _EVEN_RUN_KEYS if dist[k]["count"] == max_cnt))

    result = {
        "total_draws": total,
        "has_even_run_pct": round(has / total * 100, 2),
        "most_common_group_count": most_common,
        "avg_even_run_count": round(sum(run_counts) / total, 2),
        "even_run_distribution": dist,
    }
    _even_run_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-082: 10단위 다양성 분포 분석 (decade diversity)
# ---------------------------------------------------------------------------

# 10단위 그룹 다양성 분포의 고정 키. 한 회차가 커버하는 서로 다른 구간 수(1~5).
_DECADE_DIV_KEYS = ["1", "2", "3", "4", "5"]


# SPEC-082: 번호를 5개 10단위 그룹(1~5)으로 매핑한다.
# 명시적 범위 비교로 분류한다. n // 10 사용 시 1~9가 0으로,
# 40~45가 4로 흩어져 5개 그룹 정의와 어긋나므로 사용하지 않는다.
def _decade_of(n: int) -> int:
    """번호 n을 10단위 그룹 번호(1~5)로 변환합니다 (SPEC-LOTTO-082).

    - 1~9   → 1 (1자리)
    - 10~19 → 2
    - 20~29 → 3
    - 30~39 → 4
    - 40~45 → 5
    """
    if n <= 9:
        return 1
    elif n <= 19:
        return 2
    elif n <= 29:
        return 3
    elif n <= 39:
        return 4
    else:
        return 5


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-082 10단위 다양성 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-082
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_decade_diversity_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개가 커버하는 서로 다른 10단위 그룹 수의 분포를 분석합니다 (SPEC-LOTTO-082).

    각 회차의 본번호 6개(보너스 제외)를 5개 10단위 그룹(1~9, 10~19, 20~29,
    30~39, 40~45)으로 매핑한 뒤, 커버하는 서로 다른 그룹의 수(decade_count, 1~5)를
    산출한다. 그룹 매핑은 _decade_of(n)으로 수행한다.

    회차별 decade_count(1~5)를 5개 고정 키("1".."5")로 분류(zero-fill)하고,
    회차당 평균 커버 수, 최빈 커버 수(동률 시 작은 키), 전 구간 커버 비율
    (decade_count==5 비율)을 집계한다.

    SPEC-059(get_decade_stats)는 각 구간별로 6개 중 몇 개가 들어가는지
    (구간당 출현 개수 0~6)를 집계하는 별개 함수이며 본 함수와 정의가 다르다.

    회차별 분류를 1회 집계한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               avg_decade_count=0.0, most_common_count=1, full_coverage_pct=0.0,
               5개 키가 모두 0인 분포를 반환한다.

    Returns:
        {total_draws, avg_decade_count, most_common_count, full_coverage_pct,
        decade_diversity_distribution} 매핑.
        decade_diversity_distribution 은 5개 키("1".."5")를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _decade_div_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _DECADE_DIV_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_decade_count": 0.0,
            "most_common_count": 1,
            "full_coverage_pct": 0.0,
            "decade_diversity_distribution": dist,
        }
        _decade_div_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    decade_counts: list[int] = []
    for draw in draws:
        dc = len({_decade_of(n) for n in draw.numbers()})  # 본번호 6개 (보너스 제외)
        decade_counts.append(dc)
        dist[str(dc)]["count"] += 1

    for k in _DECADE_DIV_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    avg = round(sum(decade_counts) / total, 2)

    # 최빈 커버 수 — count 최대, 동률 시 작은 키(_DECADE_DIV_KEYS 정의 순서) 우선.
    max_cnt = max(dist[k]["count"] for k in _DECADE_DIV_KEYS)
    most_common = int(
        next(k for k in _DECADE_DIV_KEYS if dist[k]["count"] == max_cnt)
    )

    full = sum(1 for c in decade_counts if c == 5)
    full_pct = round(full / total * 100, 2)

    result: dict[str, Any] = {
        "total_draws": total,
        "avg_decade_count": avg,
        "most_common_count": most_common,
        "full_coverage_pct": full_pct,
        "decade_diversity_distribution": dist,
    }
    _decade_div_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-083: 홀수 연속 포함 분포 분석 (odd consecutive run)
# ---------------------------------------------------------------------------


def _count_odd_runs(numbers: list[int]) -> int:
    """본번호 중 간격이 정확히 2인 연속 홀수 묶음(길이>=2)의 수를 센다 (SPEC-LOTTO-083).

    홀수만 추출해 정렬한 뒤, 인접 차이가 2인 구간(길이>=2)의 수를 산출한다.
    예) [1,3,5,7,9,11] → {1,3,5,7,9,11} 1개, [1,3,9,11,...] → {1,3},{9,11} 2개.
    간격이 4 이상인 홀수(예: 1,5)는 연속 홀수가 아니며, 단일 홀수(길이1)는 제외한다.
    SPEC-081(짝수 연속)의 홀수 대응이며, 산출 묶음 수가 3을 넘으면 3으로 캡한다.

    Args:
        numbers: 한 회차 본번호 6개(보너스 제외). 정렬 여부 무관.

    Returns:
        간격 2 홀수 연속 묶음의 수(0~3).
    """
    odds = sorted(n for n in numbers if n % 2 == 1)
    if len(odds) < 2:
        return 0
    groups = 0
    run_len = 1
    for i in range(1, len(odds)):
        if odds[i] == odds[i - 1] + 2:
            run_len += 1
        else:
            if run_len >= 2:
                groups += 1
            run_len = 1
    if run_len >= 2:
        groups += 1
    return min(groups, 3)  # 3 이상은 3으로 캡


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-083 홀수 연속 포함 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-083
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_odd_run_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 홀수 연속 묶음(간격=2) 수의 분포를 분석합니다 (SPEC-LOTTO-083).

    각 회차의 본번호 6개(보너스 제외) 중 홀수만 추출하여, 간격이 정확히 2인
    연속 홀수 묶음(길이>=2)의 수를 산출한 뒤 4개 고정 키("0","1","2","3")로
    분류한다. 6개 모두 홀수일 때 최대 묶음 수는 3개이며, 초과 시 3으로 캡한다.

    정의:
        - odd_run:                간격 2 홀수 연속 묶음(회차당 0~3개).
        - has_odd_run_pct:        묶음>=1 회차 비율(%, 소수 2자리).
        - most_common_group_count: 최빈 묶음 수. 동률 시 _ODD_RUN_KEYS
                                   정의 순서상 앞선(=더 작은) 값을 선택한다.
        - avg_odd_run_count:      회차당 평균 묶음 수(소수 2자리).
        - odd_run_distribution:   4개 고정 키를 항상 포함(미관측 0 채움).

    SPEC-081(짝수 연속)의 홀수 대응이며, SPEC-060(홀짝 개수)·SPEC-069(연속 쌍,
    간격1)와는 출력 구조와 정의가 완전히 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               4개 키 전부 0, most_common_group_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, has_odd_run_pct, most_common_group_count,
        avg_odd_run_count, odd_run_distribution} 매핑.
        odd_run_distribution 은 4개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _odd_run_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _ODD_RUN_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "has_odd_run_pct": 0.0,
            "most_common_group_count": 0,
            "avg_odd_run_count": 0.0,
            "odd_run_distribution": dist,
        }
        _odd_run_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    run_counts: list[int] = []
    for draw in draws:
        c = _count_odd_runs(draw.numbers())  # 본번호 6개 (보너스 제외)
        run_counts.append(c)
        dist[str(c)]["count"] += 1

    for k in _ODD_RUN_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    has = sum(1 for c in run_counts if c >= 1)
    # 동률 시 정의 순서상 앞선(=더 작은) 키가 이기도록 _ODD_RUN_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _ODD_RUN_KEYS)
    most_common = int(next(k for k in _ODD_RUN_KEYS if dist[k]["count"] == max_cnt))

    result = {
        "total_draws": total,
        "has_odd_run_pct": round(has / total * 100, 2),
        "most_common_group_count": most_common,
        "avg_odd_run_count": round(sum(run_counts) / total, 2),
        "odd_run_distribution": dist,
    }
    _odd_run_cache[cache_key] = result
    return result
