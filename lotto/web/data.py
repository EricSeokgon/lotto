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
import random
import statistics
import tempfile

# SPEC-LOTTO-045: 명시적 재노출(redundant-alias). 테스트가 모듈 네임스페이스
# (lotto.web.data.time)로 time.time을 패치하므로 명시적 재노출로 처리한다 (런타임 동작 무관).
import time as time
import warnings
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any  # noqa: UP045 — Python 3.9 런타임 호환

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

# SPEC-LOTTO-084: 홀짝 전환 횟수 분포 키. 6개 고정.
# 6개 번호는 인접 쌍 5개이므로 전환 횟수는 0~5 → "0"~"5" 6개 키.
_PARITY_TRANS_KEYS = ["0", "1", "2", "3", "4", "5"]

# SPEC-LOTTO-084: 홀짝 전환 횟수 분포 캐시. invalidate_cache로 무효화.
_parity_trans_cache: dict[str, Any] = {}

# SPEC-LOTTO-085: 일의 자리 중복 분포 키. 4개 고정.
# 6개 번호와 10개 일의 자리상 2개 이상 공유 그룹 수의 현실적 최댓값은 3 → "0"~"3".
_LAST_DIGIT_PAIR_KEYS = ["0", "1", "2", "3"]

# SPEC-LOTTO-085: 일의 자리 중복 분포 캐시. invalidate_cache로 무효화.
_last_digit_pair_cache: dict[str, Any] = {}

# SPEC-LOTTO-086: 번호 합계 10단위 세분화 구간 키. 6개 고정(비균등).
# 중앙 구간(101-160)을 130/131에서 분할하여 정상 분포 중심을 포착한다.
_SUM_RANGE_KEYS = ["21-60", "61-100", "101-130", "131-160", "161-200", "201-255"]

# SPEC-LOTTO-086: 합계 구간 세분화 분포 캐시. invalidate_cache로 무효화.
_sum_range_cache: dict[str, Any] = {}

# SPEC-LOTTO-087: 번호 중앙값(3·4번째 평균) 10단위 구간 분포 캐시. invalidate_cache로 무효화.
_median_range_cache: dict[str, Any] = {}

# SPEC-LOTTO-087: 중앙값 구간 5개 고정 키(정의 순서가 동률 시 우선순위).
_MEDIAN_RANGE_KEYS = ["1-9", "10-19", "20-29", "30-39", "40-45"]

# SPEC-LOTTO-088: 번호 간격 분산(균등도) 구간 분포 캐시. invalidate_cache로 무효화.
_gap_var_cache: dict[str, Any] = {}

# SPEC-LOTTO-088: 간격 분산 구간 5개 고정 키(정의 순서가 동률 시 우선순위).
_GAP_VAR_KEYS = ["0-10", "10-30", "30-60", "60-100", "100+"]

# SPEC-LOTTO-089: 저·고 번호 균형 조합 분포 캐시. invalidate_cache로 무효화.
_low_high_cache: dict[str, Any] = {}

# SPEC-LOTTO-089: 저/고 개수 조합 7개 고정 키(정의 순서가 동률 시 우선순위).
_LOW_HIGH_KEYS = ["0저6고", "1저5고", "2저4고", "3저3고", "4저2고", "5저1고", "6저0고"]

# SPEC-LOTTO-089: 저(low) 상한 — n <= 22 저, n >= 23 고.
_LOW_HIGH_COMBO_BOUNDARY = 22

# SPEC-LOTTO-089: 회차당 본번호 개수 / 균형(3저3고) 기준.
_LOW_HIGH_COMBO_PICK = 6
_LOW_HIGH_BALANCED_KEY = "3저3고"

# SPEC-LOTTO-090: 합계 일의 자리 분포 캐시. invalidate_cache로 무효화.
_sum_last_digit_cache: dict[str, Any] = {}

# SPEC-LOTTO-090: 합계 일의 자리 10개 고정 키("0"~"9", 정의 순서가 동률 시 우선순위).
_SUM_LAST_DIGIT_KEYS = [str(d) for d in range(10)]

# SPEC-LOTTO-090: 짝수 끝자리 집합(even_digit_pct 산출 기준).
_SUM_LAST_DIGIT_EVEN_KEYS = ["0", "2", "4", "6", "8"]

# SPEC-LOTTO-091: 소수 이웃 포함 개수 분포 캐시. invalidate_cache로 무효화.
_prime_neighbor_cache: dict[str, Any] = {}

# SPEC-LOTTO-091: 소수 이웃 개수 7개 고정 키("0"~"6", 정의 순서가 동률 시 우선순위).
_PRIME_NEIGHBOR_KEYS = [str(i) for i in range(7)]

# SPEC-LOTTO-091: 소수 이웃 집합(1~45). n이 소수이거나 소수±1(1~45)이면 이웃이다.
# 1~45 소수: 2,3,5,7,11,13,17,19,23,29,31,37,41,43.
# 비이웃(11개): 9,15,21,25,26,27,33,34,35,39,45.
_PRIME_NEIGHBOR_SET = frozenset([
    1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20,
    22, 23, 24, 28, 29, 30, 31, 32, 36, 37, 38, 40, 41, 42, 43, 44,
])

# SPEC-LOTTO-092: 군집 수 분포 캐시. invalidate_cache로 무효화.
_cluster_cache: dict[str, Any] = {}

# SPEC-LOTTO-092: 군집 수 4개 고정 키("0"~"3", "3"은 3개 이상; 정의 순서가 동률 시 우선순위).
_CLUSTER_KEYS = ["0", "1", "2", "3"]

# SPEC-LOTTO-093: 첫·마지막 번호 구간 조합 분포 캐시. invalidate_cache로 무효화.
_first_last_zone_cache: dict[str, Any] = {}

# SPEC-LOTTO-094: 홀짝 교차 패턴 분포 캐시. invalidate_cache로 무효화.
_alternation_cache: dict[str, Any] = {}

# SPEC-LOTTO-094: 교차 단계 6개 고정 키("교차0"~"교차5"; 정의 순서가 동률 시 우선순위).
_ALTERNATION_KEYS = ["교차0", "교차1", "교차2", "교차3", "교차4", "교차5"]

# SPEC-LOTTO-095: 번호 스팬(max-min) 분포 캐시. invalidate_cache로 무효화.
_span_cache: dict[str, Any] = {}

# SPEC-LOTTO-095: 스팬 버킷 7개 고정 키(정의 순서가 동률 시 우선순위).
_SPAN_KEYS = [
    "10 이하",
    "11-20",
    "21-25",
    "26-30",
    "31-35",
    "36-40",
    "41 이상",
]

# SPEC-LOTTO-093: 첫·마지막 구간 조합 6개 고정 키(min ≤ max → BA/CA/CB 불가능;
# 정의 순서가 동률 시 우선순위).
_FIRST_LAST_ZONE_KEYS = ["AA", "AB", "AC", "BB", "BC", "CC"]

# SPEC-LOTTO-096: 번호 간격 최솟값 구간 분포 캐시. invalidate_cache로 무효화.
_min_gap_dist_cache: dict[str, Any] = {}

# SPEC-LOTTO-096: 최솟값 간격 버킷 6개 고정 키(정의 순서가 동률 시 우선순위).
_MIN_GAP_KEYS = ["1", "2", "3", "4-5", "6-10", "11+"]

# SPEC-LOTTO-097: 번호 간격 중앙값 구간 분포 캐시. invalidate_cache로 무효화.
_gap_median_dist_cache: dict[str, Any] = {}

# SPEC-LOTTO-097: 간격 중앙값 버킷 6개 고정 키(정의 순서가 동률 시 우선순위).
_GAP_MEDIAN_KEYS = ["1-2", "3-4", "5-6", "7-8", "9-10", "11+"]

# SPEC-LOTTO-098: 구간별 번호 선택 분포 캐시. invalidate_cache로 무효화.
_zone_coverage_cache: dict[str, Any] = {}

# SPEC-LOTTO-098: 커버 구간 수 버킷 6개 고정 키(정의 순서가 동률 시 우선순위).
_ZONE_COV_KEYS = ["1", "2", "3", "4", "5", "6"]

# SPEC-LOTTO-099: 번호 사분위 분포 캐시. invalidate_cache로 무효화.
_quartile_dist_cache: dict[str, Any] = {}

# SPEC-LOTTO-105: 번호 위치별 분포 캐시. 키는 f"{len(draws)}:{top_n}".
# top_n에 따라 top_numbers가 달라지므로 캐시 키에 top_n을 포함한다.
_position_cache: dict[str, Any] = {}

# SPEC-LOTTO-106: 홀짝·고저 조합 매트릭스 캐시. 키는 f"{len(draws)}:{top_n}".
# top_n에 따라 top_combinations 개수가 달라지므로 캐시 키에 top_n을 포함한다.
_cross_pattern_cache: dict[str, Any] = {}

# SPEC-LOTTO-107: 기간별 번호 빈도 추이 캐시. 키는 f"{len(draws)}:{top_n}".
# top_n에 따라 top_rising/top_falling 개수가 달라지므로 캐시 키에 top_n을 포함한다.
_period_trend_cache: dict[str, Any] = {}

# SPEC-LOTTO-108: 월별 출현 분포 캐시. 키는 f"{len(draws)}:{top_n}".
# top_n에 따라 top_numbers_by_month 각 월 리스트 길이가 달라지므로 키에 top_n을 포함한다.
_monthly_dist_cache: dict[str, Any] = {}

# SPEC-LOTTO-109: 번호 출현 간격 상세 분포 캐시. top_n 파라미터가 없으므로
# 키는 회차 수만 사용한다(항상 45개 번호 전부 반환).
_gap_dist_cache: dict[str, Any] = {}

# SPEC-LOTTO-110: 번호 연도별 출현 분포 캐시. 키는 f"{len(draws)}:{top_n}".
# top_n에 따라 top_numbers_by_year 각 연도 리스트 길이가 달라지므로 키에 top_n을 포함한다.
_yearly_dist_cache: dict[str, Any] = {}


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
    SPEC-LOTTO-084: 신규 추첨 데이터 적재 시 홀짝 전환 횟수 분포 캐시도 무효화한다.
    SPEC-LOTTO-085: 신규 추첨 데이터 적재 시 일의 자리 중복 분포 캐시도 무효화한다.
    SPEC-LOTTO-086: 신규 추첨 데이터 적재 시 합계 구간 세분화 분포 캐시도 무효화한다.
    SPEC-LOTTO-087: 신규 추첨 데이터 적재 시 중앙값 구간 분포 캐시도 무효화한다.
    SPEC-LOTTO-088: 신규 추첨 데이터 적재 시 간격 분산 구간 분포 캐시도 무효화한다.
    SPEC-LOTTO-089: 신규 추첨 데이터 적재 시 저·고 균형 조합 분포 캐시도 무효화한다.
    SPEC-LOTTO-090: 신규 추첨 데이터 적재 시 합계 일의 자리 분포 캐시도 무효화한다.
    SPEC-LOTTO-091: 신규 추첨 데이터 적재 시 소수 이웃 포함 개수 분포 캐시도 무효화한다.
    SPEC-LOTTO-092: 신규 추첨 데이터 적재 시 군집 수 분포 캐시도 무효화한다.
    SPEC-LOTTO-093: 신규 추첨 데이터 적재 시 첫·마지막 구간 조합 분포 캐시도 무효화한다.
    SPEC-LOTTO-094: 신규 추첨 데이터 적재 시 홀짝 교차 패턴 분포 캐시도 무효화한다.
    SPEC-LOTTO-095: 신규 추첨 데이터 적재 시 번호 스팬 분포 캐시도 무효화한다.
    SPEC-LOTTO-096: 신규 추첨 데이터 적재 시 최소 간격 구간 분포 캐시도 무효화한다.
    SPEC-LOTTO-097: 신규 추첨 데이터 적재 시 간격 중앙값 구간 분포 캐시도 무효화한다.
    SPEC-LOTTO-098: 신규 추첨 데이터 적재 시 구간별 번호 선택 분포 캐시도 무효화한다.
    SPEC-LOTTO-099: 신규 추첨 데이터 적재 시 번호 사분위 분포 캐시도 무효화한다.
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
    _parity_trans_cache.clear()
    _last_digit_pair_cache.clear()
    _sum_range_cache.clear()
    _median_range_cache.clear()
    _gap_var_cache.clear()
    _low_high_cache.clear()
    _sum_last_digit_cache.clear()
    _prime_neighbor_cache.clear()
    _cluster_cache.clear()
    _first_last_zone_cache.clear()
    _alternation_cache.clear()
    _span_cache.clear()
    _min_gap_dist_cache.clear()
    _gap_median_dist_cache.clear()
    _zone_coverage_cache.clear()
    _quartile_dist_cache.clear()
    _position_cache.clear()  # SPEC-LOTTO-105: 위치별 분포 캐시 무효화
    _cross_pattern_cache.clear()  # SPEC-LOTTO-106: 조합 매트릭스 캐시 무효화
    _period_trend_cache.clear()  # SPEC-LOTTO-107: 기간별 추이 캐시 무효화
    _monthly_dist_cache.clear()  # SPEC-LOTTO-108: 월별 분포 캐시 무효화
    _gap_dist_cache.clear()  # SPEC-LOTTO-109: 간격 분포 캐시 무효화
    _yearly_dist_cache.clear()  # SPEC-LOTTO-110: 연도별 분포 캐시 무효화


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
def append_gen_history(
    strategy: str,
    numbers: list[int],
    target_drw_no: "Optional[int]" = None,  # noqa: UP045
    source: str = "api",
) -> None:
    """번호 생성 이력에 항목 1건을 추가합니다 (SPEC-LOTTO-033).

    최근 _GEN_HISTORY_MAX 건만 유지하며, 저장 실패 시 예외를 전파하지 않는다
    (호출자인 추천 API 응답은 정상 반환되어야 한다).
    target_drw_no: 당첨 확인 목표 회차 (저장 시 최신 회차+1 자동 지정 권장)
    """
    import uuid

    entry: dict[str, Any] = {
        "id": uuid.uuid4().hex[:8],
        # SPEC-LOTTO-033: UTC ISO-8601 (Python 3.9 호환)
        "generated_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),  # noqa: UP017
        "strategy": strategy,
        "numbers": list(numbers),
        "source": source,
    }
    if target_drw_no is not None:
        entry["target_drw_no"] = target_drw_no
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


def calc_prize_rank(numbers: list[int], n1: int, n2: int, n3: int, n4: int, n5: int, n6: int, bonus: int) -> dict[str, Any]:
    """추천 번호 6개와 당첨 번호를 비교해 당첨 등수를 반환합니다.

    Returns: {"rank": 0~5, "matched": 일치 개수, "bonus_matched": 보너스 일치 여부}
    rank 0 = 미당첨, 1~5 = 해당 등수
    """
    winning = {n1, n2, n3, n4, n5, n6}
    nums_set = set(numbers)
    matched = len(nums_set & winning)
    bonus_matched = bonus in nums_set

    if matched == 6:
        rank = 1
    elif matched == 5 and bonus_matched:
        rank = 2
    elif matched == 5:
        rank = 3
    elif matched == 4:
        rank = 4
    elif matched == 3:
        rank = 5
    else:
        rank = 0

    return {"rank": rank, "matched": matched, "bonus_matched": bonus_matched}


def get_draw_by_no(drw_no: int) -> "Optional[Any]":  # noqa: UP045
    """drwNo로 단일 DrawResult를 반환합니다. 없으면 None."""
    draws = get_draws()
    if not draws:
        return None
    for d in draws:
        if d.drwNo == drw_no:
            return d
    return None


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
    """시뮬레이션 결과를 반환합니다. draws.csv 없으면 None.

    결과를 파일 캐시에 저장하여 동일 조건 재요청 시 즉시 반환합니다.
    캐시 키: (rounds, 마지막_회차_번호).
    """
    if not DRAWS_PATH.exists():
        return None
    draws = get_draws()
    if not draws:
        return None

    last_drw_no = draws[-1].drwNo
    cache_path = settings.data_dir / f"sim_cache_{rounds}_{last_drw_no}.json"

    # 캐시 히트
    if cache_path.exists():
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            from lotto.models import SimulationResult
            return SimulationResult.model_validate(raw)
        except Exception:  # noqa: BLE001
            cache_path.unlink(missing_ok=True)

    from lotto.simulator import LottoSimulator

    result = LottoSimulator(draws).simulate(rounds=rounds)

    # 캐시 저장 (실패해도 결과 반환에 영향 없음)
    with contextlib.suppress(Exception):
        cache_path.write_text(
            json.dumps(result.model_dump(), ensure_ascii=False),
            encoding="utf-8",
        )

    return result


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


def _count_parity_transitions(numbers: list[int]) -> int:
    """본번호를 오름차순 정렬한 뒤 인접 쌍의 홀짝 전환 횟수를 센다 (SPEC-LOTTO-084).

    정렬된 번호열에서 인접한 두 번호의 홀짝(n % 2)이 서로 다르면 전환 1회로
    계산한다. 6개 번호는 인접 쌍 5개이므로 전환 횟수는 0~5 범위이다.
    예) [1,2,3,4,5,6] → OEOEOE 완전 교차 → 5, [1,3,5,7,9,11] → 전부 홀수 → 0.

    SPEC-060(홀짝 개수 비율)과는 다른 별개 지표로, 개수가 아니라 정렬된 번호열의
    패리티 "전환 횟수"를 센다.

    Args:
        numbers: 한 회차 본번호 6개(보너스 제외). 정렬 여부 무관.

    Returns:
        홀짝 전환 횟수(0~5).
    """
    sorted_nums = sorted(numbers)
    transitions = 0
    for i in range(len(sorted_nums) - 1):
        if (sorted_nums[i] % 2) != (sorted_nums[i + 1] % 2):
            transitions += 1
    return transitions


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-084 홀짝 전환 횟수 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-084
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_parity_transition_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 홀짝 전환 횟수(0~5)의 분포를 분석합니다 (SPEC-LOTTO-084).

    각 회차의 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤, 인접한 두 번호의
    홀짝이 다른 횟수를 산출하여 6개 고정 키("0"~"5")로 분류한다.

    정의:
        - transitions:             정렬된 번호열의 홀짝 전환 횟수(회차당 0~5).
        - avg_transitions:         회차당 평균 전환 횟수(소수 2자리).
        - most_common_transitions: 최빈 전환 횟수. 동률 시 _PARITY_TRANS_KEYS
                                   정의 순서상 앞선(=더 작은) 값을 선택한다.
        - high_alternation_pct:    전환 횟수가 4 이상인 회차 비율(%, 소수 2자리).
        - parity_transition_distribution: 6개 고정 키를 항상 포함(미관측 0 채움).

    SPEC-060(홀짝 개수 비율)과는 출력 구조와 정의가 완전히 다른 별개 기능이다.
    SPEC-060은 회차 내 홀수/짝수의 "개수"를 세지만, 본 기능은 정렬된 번호열에서
    패리티가 "전환되는 횟수"를 센다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 0, most_common_transitions=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_transitions, most_common_transitions,
        high_alternation_pct, parity_transition_distribution} 매핑.
        parity_transition_distribution 은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _parity_trans_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _PARITY_TRANS_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_transitions": 0.0,
            "most_common_transitions": 0,
            "high_alternation_pct": 0.0,
            "parity_transition_distribution": dist,
        }
        _parity_trans_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    trans_counts: list[int] = []
    for draw in draws:
        c = _count_parity_transitions(draw.numbers())  # 본번호 6개 (보너스 제외)
        trans_counts.append(c)
        dist[str(c)]["count"] += 1

    for k in _PARITY_TRANS_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    high = sum(1 for c in trans_counts if c >= 4)
    # 동률 시 정의 순서상 앞선(=더 작은) 키가 이기도록 _PARITY_TRANS_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _PARITY_TRANS_KEYS)
    most_common = int(next(k for k in _PARITY_TRANS_KEYS if dist[k]["count"] == max_cnt))

    result = {
        "total_draws": total,
        "avg_transitions": round(sum(trans_counts) / total, 2),
        "most_common_transitions": most_common,
        "high_alternation_pct": round(high / total * 100, 2),
        "parity_transition_distribution": dist,
    }
    _parity_trans_cache[cache_key] = result
    return result


def _count_last_digit_pairs(numbers: list[int]) -> int:
    """본번호의 일의 자리를 그룹화하여 2개 이상 공유 그룹 수를 센다 (SPEC-LOTTO-085).

    각 번호의 일의 자리(n % 10)별로 묶은 뒤, 같은 일의 자리를 2개 이상 가진
    서로 다른 일의 자리 값의 개수를 반환한다. "쌍의 개수"가 아니라 "2개 이상을
    가진 그룹의 수"이며, 3을 초과하면 3으로 상한 처리한다.
    예) [1,11,2,12,3,13] → 일의 자리 1·2·3 각 2개 → 3, [1,2,3,4,5,6] → 0.

    SPEC-063/079(끝자리 합계 분포), SPEC-055(끝자리별 누적 빈도)와는 다른 별개
    지표로, 합계나 빈도가 아니라 같은 일의 자리를 공유하는 그룹의 수를 센다.

    Args:
        numbers: 한 회차 본번호(보너스 제외). 정렬 여부 무관.

    Returns:
        2개 이상 공유 일의 자리 그룹 수(0~3, 3 초과는 3으로 상한).
    """
    digit_groups: dict[int, int] = {}
    for n in numbers:
        d = n % 10
        digit_groups[d] = digit_groups.get(d, 0) + 1
    return min(sum(1 for cnt in digit_groups.values() if cnt >= 2), 3)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-085 일의 자리 중복 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-085
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_last_digit_pair_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 일의 자리 중복 그룹 수(0~3)의 분포를 분석합니다 (SPEC-LOTTO-085).

    각 회차의 본번호 6개(보너스 제외)를 일의 자리(n % 10)별로 묶어, 같은 일의
    자리를 2개 이상 가진 그룹의 수를 산출하고 4개 고정 키("0"~"3")로 분류한다.

    정의:
        - pair_count:             회차당 2개 이상 공유 일의 자리 그룹 수(0~3).
        - avg_pair_count:         회차당 평균 그룹 수(소수 2자리).
        - most_common_pair_count: 최빈 그룹 수. 동률 시 _LAST_DIGIT_PAIR_KEYS
                                  정의 순서상 앞선(=더 작은) 값을 선택한다.
        - has_pair_pct:           그룹 수가 1 이상인 회차 비율(%, 소수 2자리).
        - last_digit_pair_distribution: 4개 고정 키를 항상 포함(미관측 0 채움).

    SPEC-063/079(끝자리 합계 분포), SPEC-055(끝자리별 누적 빈도)와는 출력 구조와
    정의가 완전히 다른 별개 기능이다. 본 기능은 같은 일의 자리를 공유하는 그룹의
    수를 센다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               4개 키 전부 0, most_common_pair_count=0 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, has_pair_pct, most_common_pair_count, avg_pair_count,
        last_digit_pair_distribution} 매핑.
        last_digit_pair_distribution 은 4개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _last_digit_pair_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _LAST_DIGIT_PAIR_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "has_pair_pct": 0.0,
            "most_common_pair_count": 0,
            "avg_pair_count": 0.0,
            "last_digit_pair_distribution": dist,
        }
        _last_digit_pair_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    pair_counts: list[int] = []
    for draw in draws:
        c = _count_last_digit_pairs(draw.numbers())  # 본번호 6개 (보너스 제외)
        pair_counts.append(c)
        dist[str(c)]["count"] += 1

    for k in _LAST_DIGIT_PAIR_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    has_pair = sum(1 for c in pair_counts if c >= 1)
    # 동률 시 정의 순서상 앞선(=더 작은) 키가 이기도록 _LAST_DIGIT_PAIR_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _LAST_DIGIT_PAIR_KEYS)
    most_common = int(next(k for k in _LAST_DIGIT_PAIR_KEYS if dist[k]["count"] == max_cnt))

    result = {
        "total_draws": total,
        "has_pair_pct": round(has_pair / total * 100, 2),
        "most_common_pair_count": most_common,
        "avg_pair_count": round(sum(pair_counts) / total, 2),
        "last_digit_pair_distribution": dist,
    }
    _last_digit_pair_cache[cache_key] = result
    return result


# ─── SPEC-LOTTO-086: 번호 합계 구간 세분화 분포 분석 ──────────────────────────


# @MX:NOTE: [AUTO] SPEC-LOTTO-086 — 합계 비균등 10단위 세분화 버킷 분류
# @MX:SPEC: SPEC-LOTTO-086
def _sum_range_bucket(s: int) -> str:
    """본번호 6개 합계 s를 6개 비균등 구간 중 하나로 분류한다 (SPEC-LOTTO-086).

    중앙 구간(101-160)은 130/131에서 분할하여 정상 분포 중심을 포착한다.
    합계 가능 범위는 21~255이지만, 경계 밖 값도 가장 가까운 끝 구간으로 흡수한다.
    """
    if s <= 60:
        return "21-60"
    elif s <= 100:
        return "61-100"
    elif s <= 130:
        return "101-130"
    elif s <= 160:
        return "131-160"
    elif s <= 200:
        return "161-200"
    else:
        return "201-255"


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-086 합계 구간 세분화 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-086
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_sum_range_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개 합계를 비균등 10단위 세분화 6구간으로 분류해 분석한다 (SPEC-LOTTO-086).

    각 회차 본번호 6개(보너스 제외)의 합계를 구간("21-60","61-100","101-130",
    "131-160","161-200","201-255")으로 분류한다. 중앙 구간을 130/131에서 분할해
    정상 분포 중심을 포착한다.

    정의:
        - avg_sum:           회차 합계 평균(소수 2자리). 데이터 없으면 0.0.
        - most_common_range: count 최대 구간. 동률 시 _SUM_RANGE_KEYS 정의 순서상
                             앞선(=더 작은) 구간을 선택한다. 데이터 없으면 "21-60".
        - middle_range_pct:  "101-130"+"131-160" 합산 비율(%, 소수 2자리).

    SPEC-049(sum_range_analysis, 폭 20 버킷 + 공통 영역)와는 버킷 정의·출력 구조가
    완전히 다른 별개 지표다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 0, most_common_range="21-60"의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_sum, most_common_range, middle_range_pct,
        sum_range_distribution} 매핑. sum_range_distribution은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _sum_range_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _SUM_RANGE_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_sum": 0.0,
            "most_common_range": "21-60",
            "middle_range_pct": 0.0,
            "sum_range_distribution": dist,
        }
        _sum_range_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    sums: list[int] = []
    for draw in draws:
        s = sum(draw.numbers())  # 본번호 6개 (보너스 제외)
        sums.append(s)
        dist[_sum_range_bucket(s)]["count"] += 1

    for k in _SUM_RANGE_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=더 작은) 구간이 이기도록 _SUM_RANGE_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _SUM_RANGE_KEYS)
    most_common = next(k for k in _SUM_RANGE_KEYS if dist[k]["count"] == max_cnt)
    middle_cnt = dist["101-130"]["count"] + dist["131-160"]["count"]

    result = {
        "total_draws": total,
        "avg_sum": round(sum(sums) / total, 2),
        "most_common_range": most_common,
        "middle_range_pct": round(middle_cnt / total * 100, 2),
        "sum_range_distribution": dist,
    }
    _sum_range_cache[cache_key] = result
    return result


def _median_range_bucket(numbers: list[int]) -> str:
    """본번호 6개의 중앙값이 속하는 10단위 구간 키를 반환합니다 (SPEC-LOTTO-087).

    중앙값은 정렬된 6개 본번호의 3·4번째(0-indexed 2,3) 평균 (sorted[2]+sorted[3])/2 이다.
    경계는 하위 구간의 상한 미만으로 판정한다(예: 10.0 → "10-19", 40.0 → "40-45").

    SPEC-071의 `_median_bucket`(중앙값 9구간)과는 버킷 정의가 다른 별개 헬퍼다.

    Args:
        numbers: 회차 본번호 6개(보너스 제외).

    Returns:
        "1-9","10-19","20-29","30-39","40-45" 5개 키 중 해당 구간.
    """
    sorted_nums = sorted(numbers)
    median = (sorted_nums[2] + sorted_nums[3]) / 2
    if median < 10:
        return "1-9"
    if median < 20:
        return "10-19"
    if median < 30:
        return "20-29"
    if median < 40:
        return "30-39"
    return "40-45"


def get_median_range_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 중앙값이 속하는 10단위 구간(5개) 분포를 분석합니다 (SPEC-LOTTO-087).

    각 회차 본번호 6개(보너스 제외)를 정렬한 [a,b,c,d,e,f]의 (c+d)/2 를 중앙값으로
    산출한 뒤, 전체 회차를 "1-9","10-19","20-29","30-39","40-45" 5개 고정 키로 분류한다.
    경계는 하위 구간의 상한 미만으로 판정한다(예: 10.0 → "10-19").

    정의:
        - avg_median:          회차 중앙값 평균(소수 2자리). 데이터 없으면 0.0.
        - most_common_range:   count 최대 구간. 동률 시 _MEDIAN_RANGE_KEYS 정의 순서상
                               앞선(=더 작은) 구간을 선택한다. 데이터 없으면 "1-9".
        - central_median_pct:  중앙값이 "20-29"(균형 구간)인 회차 비율(%, 소수 2자리).

    SPEC-071(중앙값 9구간 "1-5".."41-45")과는 버킷 정의·출력 구조가 다른 별개 지표다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               5개 키 전부 0, most_common_range="1-9"의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_median, most_common_range, central_median_pct,
        median_range_distribution} 매핑. median_range_distribution은 5개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _median_range_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _MEDIAN_RANGE_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_median": 0.0,
            "most_common_range": "1-9",
            "central_median_pct": 0.0,
            "median_range_distribution": dist,
        }
        _median_range_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    medians: list[float] = []
    for draw in draws:
        nums = list(draw.numbers())  # 본번호 6개 (보너스 제외)
        sorted_nums = sorted(nums)
        medians.append((sorted_nums[2] + sorted_nums[3]) / 2)
        dist[_median_range_bucket(nums)]["count"] += 1

    for k in _MEDIAN_RANGE_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=더 작은) 구간이 이기도록 _MEDIAN_RANGE_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _MEDIAN_RANGE_KEYS)
    most_common = next(k for k in _MEDIAN_RANGE_KEYS if dist[k]["count"] == max_cnt)

    result = {
        "total_draws": total,
        "avg_median": round(sum(medians) / total, 2),
        "most_common_range": most_common,
        "central_median_pct": dist["20-29"]["pct"],
        "median_range_distribution": dist,
    }
    _median_range_cache[cache_key] = result
    return result


def _compute_gap_variance(numbers: list[int]) -> float:
    """정렬된 6개 번호의 인접 간격 5개에 대한 모분산을 산출합니다 (SPEC-LOTTO-088).

    간격은 정렬된 [a,b,c,d,e,f]에서 [b-a, c-b, d-c, e-d, f-e] 5개이며,
    모분산 = sum((g - mean)**2) / 5, mean = sum(gaps)/5 로 계산한다(표본분산 아님).

    Args:
        numbers: 회차 본번호 6개(보너스 제외).

    Returns:
        5개 간격의 모분산(float).
    """
    sorted_nums = sorted(numbers)
    gaps = [sorted_nums[i + 1] - sorted_nums[i] for i in range(5)]
    mean = sum(gaps) / 5
    return sum((g - mean) ** 2 for g in gaps) / 5


def _gap_variance_bucket_from_variance(variance: float) -> str:
    """간격 분산값이 속하는 5단계 구간 키를 반환합니다 (SPEC-LOTTO-088).

    경계는 하위 구간의 상한 미만으로 판정한다(예: 10.0 → "10-30", 100.0 → "100+").

    Args:
        variance: 간격 모분산값.

    Returns:
        "0-10","10-30","30-60","60-100","100+" 5개 키 중 해당 구간.
    """
    if variance < 10:
        return "0-10"
    if variance < 30:
        return "10-30"
    if variance < 60:
        return "30-60"
    if variance < 100:
        return "60-100"
    return "100+"


def _gap_variance_bucket(numbers: list[int]) -> str:
    """본번호 6개의 간격 분산이 속하는 5단계 구간 키를 반환합니다 (SPEC-LOTTO-088).

    Args:
        numbers: 회차 본번호 6개(보너스 제외).

    Returns:
        "0-10","10-30","30-60","60-100","100+" 5개 키 중 해당 구간.
    """
    return _gap_variance_bucket_from_variance(_compute_gap_variance(numbers))


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-088 — 간격 분산 구간 분포 집계 (API/페이지 라우트가 호출)
# @MX:SPEC: SPEC-LOTTO-088
# @MX:REASON: API 엔드포인트·페이지 라우트·테스트에서 호출되는 공개 통계 진입점(fan_in>=3)
def get_gap_variance_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 간격 분산(균등도)이 속하는 5개 구간 분포를 분석합니다 (SPEC-LOTTO-088).

    각 회차 본번호 6개(보너스 제외)를 정렬한 [a,b,c,d,e,f]의 인접 간격 5개
    [b-a,c-b,d-c,e-d,f-e]에 대한 모분산을 산출한 뒤, 전체 회차를
    "0-10"(<10),"10-30"(<30),"30-60"(<60),"60-100"(<100),"100+"(>=100)
    5개 고정 키로 분류한다. 분산이 작을수록 번호가 등간격에 가깝다(균등 분포).

    정의:
        - avg_variance:        회차 간격 분산 평균(소수 2자리). 데이터 없으면 0.0.
        - most_common_range:   count 최대 구간. 동률 시 _GAP_VAR_KEYS 정의 순서상
                               앞선(=더 작은) 구간을 선택한다. 데이터 없으면 "0-10".
        - uniform_gap_pct:     분산 < 10("0-10", 균등 간격) 회차 비율(%, 소수 2자리).

    SPEC-056(간격 패턴 min/max)·SPEC-079(최대 간격 분포)와는 산출 대상이 다른 별개 지표다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               5개 키 전부 0, most_common_range="0-10"의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_variance, most_common_range, uniform_gap_pct,
        gap_variance_distribution} 매핑. gap_variance_distribution은 5개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _gap_var_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _GAP_VAR_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_variance": 0.0,
            "most_common_range": "0-10",
            "uniform_gap_pct": 0.0,
            "gap_variance_distribution": dist,
        }
        _gap_var_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    variances: list[float] = []
    for draw in draws:
        nums = list(draw.numbers())  # 본번호 6개 (보너스 제외)
        variance = _compute_gap_variance(nums)
        variances.append(variance)
        dist[_gap_variance_bucket_from_variance(variance)]["count"] += 1

    for k in _GAP_VAR_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=더 작은) 구간이 이기도록 _GAP_VAR_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _GAP_VAR_KEYS)
    most_common = next(k for k in _GAP_VAR_KEYS if dist[k]["count"] == max_cnt)

    result = {
        "total_draws": total,
        "avg_variance": round(sum(variances) / total, 2),
        "most_common_range": most_common,
        "uniform_gap_pct": dist["0-10"]["pct"],
        "gap_variance_distribution": dist,
    }
    _gap_var_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-089: 저·고 번호 균형 분포 분석 (low/high balance combo analysis)
# ---------------------------------------------------------------------------


def _low_high_combo(numbers: list[int]) -> str:
    """본번호 리스트의 저(n<=22)/고(n>=23) 개수 조합 키를 반환합니다 (SPEC-LOTTO-089).

    high_count는 6 - low_count로 파생하여 합 불변식을 보장한다.
    예) [1,2,3,4,5,6] → "6저0고" / [1,22,23,24,25,45] → "2저4고".
    """
    low_count = sum(1 for n in numbers if n <= _LOW_HIGH_COMBO_BOUNDARY)
    high_count = _LOW_HIGH_COMBO_PICK - low_count
    return f"{low_count}저{high_count}고"


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-089 저·고 균형 조합 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-089
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수 (fan_in >= 3)
def get_low_high_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 저·고 번호 개수 조합("{low}저{high}고") 분포를 분석합니다 (SPEC-LOTTO-089).

    각 회차 본번호 6개(보너스 제외)에서 저(n<=22) 개수(low_count, 0~6)를 세고
    high_count = 6 - low_count로 파생하여 조합 문자열로 분류한다. 전체 회차에 걸친
    평균 저번호 수/조합 분포/최빈 조합/균형(3저3고) 비율을 집계한다.

    분류:
        - 저(low):  1~22 (n <= 22, 경계 22는 저).
        - 고(high): 23~45 (n >= 23, 경계 23은 고).

    정의:
        - avg_low_count:      회차 평균 저번호 수 (소수 2자리).
        - most_common_combo:  최빈 조합. 동률 시 _LOW_HIGH_KEYS 정의 순서상
                              앞선(=더 작은) 조합을 선택한다.
        - balanced_pct:       "3저3고"(균형) 회차 비율(%, 소수 2자리).
        - low_high_distribution: 조합 키 → {count, pct}. 7개 키를 항상 포함한다.

    SPEC-061(고저 비율, 정수 키 분포)과는 출력 구조가 다른 별개 지표다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               avg_low_count=0.0, most_common_combo="0저6고", balanced_pct=0.0,
               7개 키 전부 0의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_low_count, most_common_combo, balanced_pct,
        low_high_distribution} 매핑. low_high_distribution은 7개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _low_high_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _LOW_HIGH_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_low_count": 0.0,
            "most_common_combo": _LOW_HIGH_KEYS[0],
            "balanced_pct": 0.0,
            "low_high_distribution": dist,
        }
        _low_high_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    low_sum = 0
    for draw in draws:
        nums = list(draw.numbers())  # 본번호 6개 (보너스 제외)
        low_sum += sum(1 for n in nums if n <= _LOW_HIGH_COMBO_BOUNDARY)
        dist[_low_high_combo(nums)]["count"] += 1

    for k in _LOW_HIGH_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=더 작은) 조합이 이기도록 _LOW_HIGH_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _LOW_HIGH_KEYS)
    most_common = next(k for k in _LOW_HIGH_KEYS if dist[k]["count"] == max_cnt)

    result = {
        "total_draws": total,
        "avg_low_count": round(low_sum / total, 2),
        "most_common_combo": most_common,
        "balanced_pct": dist[_LOW_HIGH_BALANCED_KEY]["pct"],
        "low_high_distribution": dist,
    }
    _low_high_cache[cache_key] = result
    return result


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-090 합계 일의 자리 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-090
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수 (fan_in >= 3)
def get_sum_last_digit_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개 합계의 일의 자리(0~9) 분포를 분석합니다 (SPEC-LOTTO-090).

    각 회차 본번호 6개(보너스 제외)의 합계 total_sum을 구하고 그 일의 자리
    last_digit = total_sum % 10 을 기준으로 회차를 분류한다. 전체 회차에 걸친
    평균 합계 / 분포 / 최빈 끝자리 / 짝수 끝자리 비율을 집계한다.

    정의:
        - avg_sum:           회차 평균 합계 (소수 2자리).
        - most_common_digit: 최빈 끝자리. 동률 시 _SUM_LAST_DIGIT_KEYS 정의 순서상
                             가장 작은 키("0" < "1" < ...)를 선택한다.
        - even_digit_pct:    끝자리가 짝수(0,2,4,6,8)인 회차 비율(%, 소수 2자리).
        - sum_last_digit_distribution: 끝자리 키 → {count, pct}. 10개 키를 항상 포함한다.

    SPEC-063(개별 번호 끝자리 합, low/mid/high 3구간 관측값)·SPEC-079(끝자리합 6키)와는
    정의·출력 구조가 다른 별개 지표다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0, avg_sum=0.0,
               most_common_digit="0", even_digit_pct=0.0, 10개 키 전부 0의 일관된
               빈 구조를 반환한다.

    Returns:
        {total_draws, avg_sum, most_common_digit, even_digit_pct,
        sum_last_digit_distribution} 매핑. distribution은 10개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _sum_last_digit_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _SUM_LAST_DIGIT_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_sum": 0.0,
            "most_common_digit": _SUM_LAST_DIGIT_KEYS[0],
            "even_digit_pct": 0.0,
            "sum_last_digit_distribution": dist,
        }
        _sum_last_digit_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    total_sum_all = 0
    for draw in draws:
        s = sum(draw.numbers())  # 본번호 6개 합 (보너스 제외)
        total_sum_all += s
        dist[str(s % 10)]["count"] += 1

    for k in _SUM_LAST_DIGIT_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=가장 작은) 키가 이기도록 _SUM_LAST_DIGIT_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _SUM_LAST_DIGIT_KEYS)
    most_common = next(k for k in _SUM_LAST_DIGIT_KEYS if dist[k]["count"] == max_cnt)

    even_count = sum(dist[k]["count"] for k in _SUM_LAST_DIGIT_EVEN_KEYS)

    result = {
        "total_draws": total,
        "avg_sum": round(total_sum_all / total, 2),
        "most_common_digit": most_common,
        "even_digit_pct": round(even_count / total * 100, 2),
        "sum_last_digit_distribution": dist,
    }
    _sum_last_digit_cache[cache_key] = result
    return result


def _count_prime_neighbors(numbers: list) -> int:
    """본번호 리스트 중 소수 이웃 집합에 포함된 번호 개수를 센다 (SPEC-LOTTO-091).

    소수 이웃이란 1~45에서 자기 자신이 소수이거나 소수와 인접(소수±1)한 번호이다.
    """
    return sum(1 for n in numbers if n in _PRIME_NEIGHBOR_SET)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-091 소수 이웃 포함 개수(0~6) 분포 집계 공개 API
# @MX:SPEC: SPEC-LOTTO-091
# @MX:REASON: API/페이지 라우트 등 다수 호출자가 의존하는 분포 계약 — 7개 키 불변
def get_prime_neighbor_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개 중 소수 이웃 포함 개수(0~6) 분포를 분석합니다 (SPEC-LOTTO-091).

    각 회차 본번호 6개(보너스 제외) 중 소수 이웃 집합(_PRIME_NEIGHBOR_SET)에 포함된
    번호 개수를 세어 0~6 키로 분류한다. 소수 이웃이란 1~45에서 자기 자신이 소수이거나
    소수와 인접(소수±1)한 번호이다.

    정의:
        - avg_neighbor_count: 회차 평균 소수 이웃 개수 (소수 2자리).
        - most_common_count:  최빈 개수 키. 동률 시 _PRIME_NEIGHBOR_KEYS 정의 순서상
                              가장 작은 키("0" < "1" < ...)를 선택한다.
        - high_neighbor_pct:  소수 이웃 개수가 5 이상(5,6)인 회차 비율(%, 소수 2자리).
        - prime_neighbor_distribution: 개수 키 → {count, pct}. 7개 키를 항상 포함한다.

    SPEC-058(소수 개수만 세는 get_prime_stats)와는 정의·출력 구조가 다른 별개 지표다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               avg_neighbor_count=0.0, most_common_count="0", high_neighbor_pct=0.0,
               7개 키 전부 0의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_neighbor_count, most_common_count, high_neighbor_pct,
        prime_neighbor_distribution} 매핑. distribution은 7개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _prime_neighbor_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _PRIME_NEIGHBOR_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_neighbor_count": 0.0,
            "most_common_count": _PRIME_NEIGHBOR_KEYS[0],
            "high_neighbor_pct": 0.0,
            "prime_neighbor_distribution": dist,
        }
        _prime_neighbor_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    neighbor_sum = 0
    for draw in draws:
        cnt = _count_prime_neighbors(draw.numbers())  # 본번호 6개 (보너스 제외)
        neighbor_sum += cnt
        dist[str(cnt)]["count"] += 1

    for k in _PRIME_NEIGHBOR_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=가장 작은) 키가 이기도록 _PRIME_NEIGHBOR_KEYS 순서로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _PRIME_NEIGHBOR_KEYS)
    most_common = next(k for k in _PRIME_NEIGHBOR_KEYS if dist[k]["count"] == max_cnt)

    # 고밀도(소수 이웃 5개 이상) 회차 비율.
    high_count = dist["5"]["count"] + dist["6"]["count"]

    result = {
        "total_draws": total,
        "avg_neighbor_count": round(neighbor_sum / total, 2),
        "most_common_count": most_common,
        "high_neighbor_pct": round(high_count / total * 100, 2),
        "prime_neighbor_distribution": dist,
    }
    _prime_neighbor_cache[cache_key] = result
    return result


def _count_clusters(numbers: list) -> int:
    """본번호 리스트에서 간격이 1인 연속 정수 묶음(군집) 개수를 센다 (SPEC-LOTTO-092).

    군집이란 정렬된 번호에서 인접 간격이 모두 1인 최대 연속 정수 묶음이며,
    길이 2 이상이어야 인정한다(단일 고립 번호는 군집 아님). 결과는 0~3으로
    캡(min(clusters, 3))한다.
    """
    sorted_nums = sorted(numbers)
    clusters = 0
    run_len = 1
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] == sorted_nums[i - 1] + 1:
            run_len += 1
        else:
            if run_len >= 2:
                clusters += 1
            run_len = 1
    if run_len >= 2:
        clusters += 1
    return min(clusters, 3)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-092 군집 수(0~3) 분포 집계 공개 API
# @MX:SPEC: SPEC-LOTTO-092
# @MX:REASON: API/페이지 라우트 등 다수 호출자가 의존하는 분포 계약 — 4개 키 불변
def get_cluster_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개 중 연속 정수 묶음(군집) 개수(0~3) 분포를 분석합니다 (SPEC-LOTTO-092).

    각 회차 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤, 간격이 1인 최대 연속
    정수 묶음(길이 2 이상)을 군집으로 보고 그 개수를 센다. 군집 수는 0~3으로
    캡(min(clusters, 3))하며 "0"~"3" 4개 키로 분류한다.

    정의:
        - avg_cluster_count: 회차 평균 군집 수 (소수 2자리).
        - most_common_count: 최빈 군집 수 키. 동률 시 _CLUSTER_KEYS 정의 순서상
                             가장 작은 키("0" < "1" < ...)를 선택한다.
        - has_cluster_pct:   군집 수가 1 이상인 회차 비율(%, 소수 2자리).
        - cluster_distribution: 군집 수 키 → {count, pct}. 4개 키를 항상 포함한다.

    SPEC-069(연속 쌍 개수), SPEC-062(연속 패턴), SPEC-078(3연속 묶음)과는
    정의·출력 구조가 다른 별개 지표다. 본 지표는 길이 2 이상 묶음의 개수를 센다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               avg_cluster_count=0.0, most_common_count="0", has_cluster_pct=0.0,
               4개 키 전부 0의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_cluster_count, most_common_count, has_cluster_pct,
        cluster_distribution} 매핑. distribution은 4개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _cluster_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _CLUSTER_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_cluster_count": 0.0,
            "most_common_count": _CLUSTER_KEYS[0],
            "has_cluster_pct": 0.0,
            "cluster_distribution": dist,
        }
        _cluster_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    cluster_sum = 0
    for draw in draws:
        cnt = _count_clusters(draw.numbers())  # 본번호 6개 (보너스 제외)
        cluster_sum += cnt
        dist[str(cnt)]["count"] += 1

    for k in _CLUSTER_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=가장 작은) 키가 이기도록 _CLUSTER_KEYS 순서로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _CLUSTER_KEYS)
    most_common = next(k for k in _CLUSTER_KEYS if dist[k]["count"] == max_cnt)

    # 군집이 1개 이상 존재한 회차 비율("0" 제외).
    has_cluster_count = total - dist["0"]["count"]

    result = {
        "total_draws": total,
        "avg_cluster_count": round(cluster_sum / total, 2),
        "most_common_count": most_common,
        "has_cluster_pct": round(has_cluster_count / total * 100, 2),
        "cluster_distribution": dist,
    }
    _cluster_cache[cache_key] = result
    return result


def _first_last_zone(n: int) -> str:
    """번호 n이 속한 3구간 밴드를 반환한다 (SPEC-LOTTO-093).

    A: 1~15, B: 16~30, C: 31~45.
    """
    if n <= 15:
        return "A"
    if n <= 30:
        return "B"
    return "C"


def get_first_last_zone_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 최솟값·최댓값 소속 구간 조합(AA~CC) 분포를 분석합니다 (SPEC-LOTTO-093).

    각 회차 본번호 6개(보너스 제외)에서 최솟값(첫 번호)과 최댓값(마지막 번호)이
    각각 어느 3구간 밴드(A:1-15 / B:16-30 / C:31-45)에 속하는지 판정한 뒤
    조합 키 f"{min_zone}{max_zone}"로 분류한다. min ≤ max 이므로 가능한 조합은
    AA, AB, AC, BB, BC, CC 6가지뿐이며 BA/CA/CB는 나타나지 않는다.

    정의:
        - avg_span: 회차별 (max - min) 평균 (소수 2자리).
        - most_common_combo: 최빈 조합. 동률 시 _FIRST_LAST_ZONE_KEYS 정의 순서상
                             앞선 키("AA" < "AB" < ... < "CC")를 선택한다.
        - wide_span_pct: 조합이 "AC"(가능한 최대 폭)인 회차 비율(%, 소수 2자리).
        - first_last_zone_distribution: 조합 키 → {count, pct}. 6개 키를 항상 포함한다.

    SPEC-064(get_min_max_stats: 최솟값·최댓값 값/범위 통계)와는 정의·출력 구조가
    다른 별개 지표다. 본 지표는 구간 밴드 조합 분포를 다룬다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               avg_span=0.0, most_common_combo="AA", wide_span_pct=0.0,
               6개 키 전부 0의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_span, most_common_combo, wide_span_pct,
        first_last_zone_distribution} 매핑. distribution은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _first_last_zone_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _FIRST_LAST_ZONE_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_span": 0.0,
            "most_common_combo": _FIRST_LAST_ZONE_KEYS[0],
            "wide_span_pct": 0.0,
            "first_last_zone_distribution": dist,
        }
        _first_last_zone_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    total_span = 0
    for draw in draws:
        nums = draw.numbers()  # 본번호 6개 (보너스 제외)
        mn = min(nums)
        mx = max(nums)
        total_span += mx - mn
        combo = _first_last_zone(mn) + _first_last_zone(mx)
        dist[combo]["count"] += 1

    for k in _FIRST_LAST_ZONE_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=키 순서상 작은) 조합이 이기도록 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _FIRST_LAST_ZONE_KEYS)
    most_common = next(
        k for k in _FIRST_LAST_ZONE_KEYS if dist[k]["count"] == max_cnt
    )

    result = {
        "total_draws": total,
        "avg_span": round(total_span / total, 2),
        "most_common_combo": most_common,
        "wide_span_pct": round(dist["AC"]["count"] / total * 100, 2),
        "first_last_zone_distribution": dist,
    }
    _first_last_zone_cache[cache_key] = result
    return result


def _count_alternations(numbers: list[int]) -> int:
    """본번호를 오름차순 정렬한 뒤 인접 쌍의 홀짝 교차 횟수를 센다 (SPEC-LOTTO-094).

    정렬된 번호열에서 인접한 두 번호의 홀짝(n % 2)이 서로 다르면 교차 1회로
    계산한다. 6개 번호는 인접 쌍 5개이므로 교차 횟수는 0~5 범위이다.
    예) [1,2,3,4,5,6] → O,E,O,E,O,E → 5회(완전 교차), [1,3,5,7,9,11] → 0회.

    SPEC-060(홀짝 개수)과는 다른 별개 지표로, 개수가 아니라 정렬된 번호열의
    홀짝 "교차 횟수"를 센다.

    Args:
        numbers: 한 회차 본번호 6개(보너스 제외). 정렬 여부 무관.

    Returns:
        홀짝 교차 횟수(0~5).
    """
    sorted_nums = sorted(numbers)
    count = 0
    for i in range(len(sorted_nums) - 1):
        if (sorted_nums[i] % 2) != (sorted_nums[i + 1] % 2):
            count += 1
    return count


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-094 홀짝 교차 단계 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-094
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_alternation_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 홀짝 교차 횟수(0~5)의 단계 분포를 분석합니다 (SPEC-LOTTO-094).

    각 회차의 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤, 인접한 두 번호의
    홀짝이 다른 횟수를 산출하여 6개 고정 키("교차0"~"교차5")로 분류한다.

    정의:
        - avg_alternation:      회차당 평균 교차 횟수(소수 2자리).
        - most_common_level:    최빈 교차 단계. 동률 시 _ALTERNATION_KEYS
                                정의 순서상 앞선(=더 작은) 단계를 선택한다.
        - full_alternation_pct: "교차5"(완전 교차) 회차 비율(%, 소수 2자리).
                                SPEC-084의 high_alternation_pct(전환>=4 비율)와는
                                정의가 다르다(교차5 단계만 집계).
        - alternation_distribution: 6개 고정 키를 항상 포함(미관측 0 채움).

    SPEC-084(get_parity_transition_stats)와 동일한 교차 횟수 산출을 사용하지만,
    출력 구조(한국어 키, full_alternation_pct=교차5 비율, most_common_level 문자열)가
    완전히 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 0, most_common_level="교차0" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_alternation, most_common_level, full_alternation_pct,
        alternation_distribution} 매핑. alternation_distribution 은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _alternation_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _ALTERNATION_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_alternation": 0.0,
            "most_common_level": "교차0",
            "full_alternation_pct": 0.0,
            "alternation_distribution": dist,
        }
        _alternation_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    total_alt = 0
    for draw in draws:
        alt = _count_alternations(draw.numbers())  # 본번호 6개 (보너스 제외)
        total_alt += alt
        dist[f"교차{alt}"]["count"] += 1

    for k in _ALTERNATION_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선(=더 작은) 단계가 이기도록 _ALTERNATION_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _ALTERNATION_KEYS)
    most_common = next(k for k in _ALTERNATION_KEYS if dist[k]["count"] == max_cnt)

    result = {
        "total_draws": total,
        "avg_alternation": round(total_alt / total, 2),
        "most_common_level": most_common,
        "full_alternation_pct": round(dist["교차5"]["count"] / total * 100, 2),
        "alternation_distribution": dist,
    }
    _alternation_cache[cache_key] = result
    return result


def _span_bucket(span: int) -> str:
    """스팬 값(max-min)을 7개 고정 버킷 중 하나로 분류한다 (SPEC-LOTTO-095).

    경계값은 구간의 상한에 포함된다(예: span=20 → "11-20", span=21 → "21-25").

    Args:
        span: 한 회차 본번호 6개의 최댓값 - 최솟값(0 이상).

    Returns:
        "10 이하" / "11-20" / "21-25" / "26-30" / "31-35" / "36-40" / "41 이상".
    """
    if span <= 10:
        return "10 이하"
    if span <= 20:
        return "11-20"
    if span <= 25:
        return "21-25"
    if span <= 30:
        return "26-30"
    if span <= 35:
        return "31-35"
    if span <= 40:
        return "36-40"
    return "41 이상"


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-095 번호 스팬 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-095
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_span_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 번호 스팬(max-min)의 7개 버킷 분포를 분석합니다 (SPEC-LOTTO-095).

    각 회차의 본번호 6개(보너스 제외)에서 최댓값 - 최솟값을 산출하여 7개 고정
    버킷("10 이하"~"41 이상")으로 분류한다.

    정의:
        - avg_span:          회차당 평균 스팬(소수 2자리).
        - most_common_range: 최빈 버킷. 동률 시 _SPAN_KEYS 정의 순서상 앞선
                             버킷을 선택한다.
        - narrow_pct:        스팬 ≤ 20 회차 비율(%, 소수 2자리, 경계 20 포함).
        - wide_pct:          스팬 ≥ 36 회차 비율(%, 소수 2자리, 경계 36 포함).
        - span_distribution: 7개 고정 키를 항상 포함(미관측 0 채움).

    SPEC-064(get_min_max_stats: 최솟값·최댓값 값/범위)와 동일한 스팬 개념을 쓰지만,
    출력 구조(7개 버킷 키, narrow_pct/wide_pct 요약)가 완전히 다른 별개 기능이다.

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               7개 키 전부 0, most_common_range="10 이하" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_span, most_common_range, narrow_pct, wide_pct,
        span_distribution} 매핑. span_distribution 은 7개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _span_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _SPAN_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_span": 0.0,
            "most_common_range": "10 이하",
            "narrow_pct": 0.0,
            "wide_pct": 0.0,
            "span_distribution": dist,
        }
        _span_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    total_span = 0
    narrow_cnt = 0  # 스팬 ≤ 20
    wide_cnt = 0  # 스팬 ≥ 36
    for draw in draws:
        nums = draw.numbers()  # 본번호 6개 (보너스 제외)
        span = max(nums) - min(nums)
        total_span += span
        dist[_span_bucket(span)]["count"] += 1
        if span <= 20:
            narrow_cnt += 1
        if span >= 36:
            wide_cnt += 1

    for k in _SPAN_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    # 동률 시 정의 순서상 앞선 버킷이 이기도록 _SPAN_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _SPAN_KEYS)
    most_common = next(k for k in _SPAN_KEYS if dist[k]["count"] == max_cnt)

    result = {
        "total_draws": total,
        "avg_span": round(total_span / total, 2),
        "most_common_range": most_common,
        "narrow_pct": round(narrow_cnt / total * 100, 2),
        "wide_pct": round(wide_cnt / total * 100, 2),
        "span_distribution": dist,
    }
    _span_cache[cache_key] = result
    return result


def _min_gap_bucket(g: int) -> str:
    """번호 간격 최솟값 g를 6개 고정 구간 버킷 라벨로 변환한다 (SPEC-LOTTO-096).

    경계: ==1→"1", ==2→"2", ==3→"3", <=5→"4-5", <=10→"6-10", 그 외(>=11)→"11+".
    """
    if g == 1:
        return "1"
    elif g == 2:
        return "2"
    elif g == 3:
        return "3"
    elif g <= 5:
        return "4-5"
    elif g <= 10:
        return "6-10"
    else:
        return "11+"


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-096 최소 간격 구간 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-096
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_min_gap_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 인접 간격 최솟값(min_gap) 구간 분포를 분석합니다 (SPEC-LOTTO-096).

    각 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이 5개의 최솟값(min_gap)을
    구한 뒤, 6개 고정 구간 버킷("1","2","3","4-5","6-10","11+")으로 분류한다.

    정의:
        - min_gap:           정렬 본번호 인접 차이 중 최솟값 (회차당 1개).
        - avg_min_gap:       회차 평균 min_gap (소수 2자리).
        - most_common_range: 최빈 구간. 동률 시 _MIN_GAP_KEYS 정의 순서상
                             앞선(=더 작은) 구간을 선택한다.
        - min1_pct:          min_gap=1인 회차(연속번호 포함 회차) 비율(%, 소수 2자리).
        - large_gap_pct:     min_gap>=6인 회차 비율(%, 소수 2자리).
        - min_gap_distribution: 6개 고정 키를 항상 포함(미관측 0 채움).

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 0, most_common_range="1" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_min_gap, most_common_range, min1_pct, large_gap_pct,
        min_gap_distribution} 매핑. min_gap_distribution 은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _min_gap_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _MIN_GAP_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_min_gap": 0.0,
            "most_common_range": "1",
            "min1_pct": 0.0,
            "large_gap_pct": 0.0,
            "min_gap_distribution": dist,
        }
        _min_gap_dist_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    min_gaps: list[int] = []
    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        # 인접 쌍의 차이 5개 중 최솟값
        g = min(b - a for a, b in zip(nums, nums[1:]))  # noqa: B905 — Python 3.9 호환
        min_gaps.append(g)
        dist[_min_gap_bucket(g)]["count"] += 1

    for k in _MIN_GAP_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    avg = round(sum(min_gaps) / total, 2)
    # 동률 시 정의 순서상 앞선(=더 작은) 구간이 이기도록 _MIN_GAP_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _MIN_GAP_KEYS)
    most_common = next(k for k in _MIN_GAP_KEYS if dist[k]["count"] == max_cnt)
    min1 = sum(1 for g in min_gaps if g == 1)
    large = sum(1 for g in min_gaps if g >= 6)

    result: dict[str, Any] = {
        "total_draws": total,
        "avg_min_gap": avg,
        "most_common_range": most_common,
        "min1_pct": round(min1 / total * 100, 2),
        "large_gap_pct": round(large / total * 100, 2),
        "min_gap_distribution": dist,
    }
    _min_gap_dist_cache[cache_key] = result
    return result


def _gap_median_bucket(g: int) -> str:
    """간격 중앙값을 6개 고정 구간 버킷 키로 변환한다 (SPEC-LOTTO-097).

    Args:
        g: 정수형 간격 중앙값(gap_median).

    Returns:
        "1-2" / "3-4" / "5-6" / "7-8" / "9-10" / "11+" 중 하나.
    """
    if g <= 2:
        return "1-2"
    elif g <= 4:
        return "3-4"
    elif g <= 6:
        return "5-6"
    elif g <= 8:
        return "7-8"
    elif g <= 10:
        return "9-10"
    else:
        return "11+"


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-097 간격 중앙값 구간 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-097
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_gap_median_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개의 인접 간격 중앙값(gap_median) 구간 분포를 분석합니다 (SPEC-LOTTO-097).

    각 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이 5개를 구한 뒤
    정렬하여 3번째(인덱스 2) 값을 중앙값으로 삼고,
    6개 고정 구간 버킷("1-2","3-4","5-6","7-8","9-10","11+")으로 분류한다.

    정의:
        - gap_median:         정렬 본번호 인접 차이 5개의 중앙값 (회차당 1개).
        - avg_gap_median:     회차 평균 gap_median (소수 2자리).
        - most_common_range:  최빈 구간. 동률 시 _GAP_MEDIAN_KEYS 정의 순서상
                              앞선(=더 작은) 구간을 선택한다.
        - low_median_pct:     gap_median <= 4인 회차(조밀한 간격) 비율(%, 소수 2자리).
        - high_median_pct:    gap_median >= 9인 회차(넓은 간격) 비율(%, 소수 2자리).
        - gap_median_distribution: 6개 고정 키를 항상 포함(미관측 0 채움).

    회차별 집계를 1회 수행한 뒤 캐시에 보관하여 반복 요청 시 재계산을 피한다.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 0, most_common_range="1-2" 의 일관된 빈 구조를 반환한다.

    Returns:
        {total_draws, avg_gap_median, most_common_range, low_median_pct,
        high_median_pct, gap_median_distribution} 매핑.
        gap_median_distribution 은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _gap_median_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _GAP_MEDIAN_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_gap_median": 0.0,
            "most_common_range": "1-2",
            "low_median_pct": 0.0,
            "high_median_pct": 0.0,
            "gap_median_distribution": dist,
        }
        _gap_median_dist_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    gap_medians: list[int] = []
    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        # 인접 쌍의 차이 5개를 정렬하여 중앙값(인덱스 2) 추출
        gaps = sorted(b - a for a, b in zip(nums, nums[1:]))  # noqa: B905 — Python 3.9 호환
        gap_median = gaps[2]  # 5개 중 3번째 = 중앙값
        gap_medians.append(gap_median)
        dist[_gap_median_bucket(gap_median)]["count"] += 1

    for k in _GAP_MEDIAN_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    avg = round(sum(gap_medians) / total, 2)
    # 동률 시 정의 순서상 앞선(=더 작은) 구간이 이기도록 _GAP_MEDIAN_KEYS 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _GAP_MEDIAN_KEYS)
    most_common = next(k for k in _GAP_MEDIAN_KEYS if dist[k]["count"] == max_cnt)
    low = sum(1 for g in gap_medians if g <= 4)
    high = sum(1 for g in gap_medians if g >= 9)

    result: dict[str, Any] = {
        "total_draws": total,
        "avg_gap_median": avg,
        "most_common_range": most_common,
        "low_median_pct": round(low / total * 100, 2),
        "high_median_pct": round(high / total * 100, 2),
        "gap_median_distribution": dist,
    }
    _gap_median_dist_cache[cache_key] = result
    return result


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-098 구간별 번호 선택 분포 집계 진입점
# @MX:SPEC: SPEC-LOTTO-098
# @MX:REASON: 페이지/API 라우트 및 테스트에서 호출하는 단일 집계 함수
def get_zone_coverage_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개가 커버하는 구간 수(zones_covered) 분포를 분석합니다 (SPEC-LOTTO-098).

    1-45 번호를 9개 구간(각 5개 번호)으로 나누어 각 회차의 본번호 6개가 몇 개의
    서로 다른 구간을 점유하는지 계산하고 6개 고정 버킷("1"~"6")으로 집계한다.

    zone_idx 공식: (num - 1) // 5  (결과: 0~8)
    zones_covered: len(set(zone_idx for num in numbers))

    정의:
        - avg_zones_covered:  회차 평균 커버 구간 수 (소수 2자리).
        - most_common_zones:  최빈 커버 구간 수 라벨. 동률 시 _ZONE_COV_KEYS
                              정의 순서상 앞선(=더 작은) 값을 선택한다.
        - full_spread_pct:    zones_covered==6인 회차 비율(%, 소수 2자리).
        - concentrated_pct:   zones_covered<=3인 회차 비율(%, 소수 2자리).
        - zone_coverage_distribution: 6개 고정 버킷 {count, pct} 형태.

    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. 빈 리스트/None이면 total_draws=0,
               6개 키 전부 {"count":0,"pct":0.0}, most_common_zones="1" 반환.

    Returns:
        {total_draws, avg_zones_covered, most_common_zones, full_spread_pct,
        concentrated_pct, zone_coverage_distribution} 매핑.
        zone_coverage_distribution 은 6개 키를 항상 포함한다.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _zone_coverage_cache.get(cache_key)
    if cached is not None:
        return cached

    dist: dict[str, dict[str, Any]] = {
        k: {"count": 0, "pct": 0.0} for k in _ZONE_COV_KEYS
    }

    if not draws:
        empty_result: dict[str, Any] = {
            "total_draws": 0,
            "avg_zones_covered": 0.0,
            "most_common_zones": "1",
            "full_spread_pct": 0.0,
            "concentrated_pct": 0.0,
            "zone_coverage_distribution": dist,
        }
        _zone_coverage_cache[cache_key] = empty_result
        return empty_result

    total = len(draws)
    zones_list: list[int] = []
    for draw in draws:
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        zones = len({(n - 1) // 5 for n in nums})
        key = str(min(zones, 6))
        dist[key]["count"] += 1
        zones_list.append(zones)

    for k in _ZONE_COV_KEYS:
        dist[k]["pct"] = round(dist[k]["count"] / total * 100, 2)

    avg = round(sum(zones_list) / total, 2)
    # 동률 시 _ZONE_COV_KEYS 정의 순서상 앞선(=더 작은) 값이 이기도록 순서대로 찾는다.
    max_cnt = max(dist[k]["count"] for k in _ZONE_COV_KEYS)
    most_common = next(k for k in _ZONE_COV_KEYS if dist[k]["count"] == max_cnt)
    full_spread = round(dist["6"]["count"] / total * 100, 2)
    concentrated = round(
        (dist["1"]["count"] + dist["2"]["count"] + dist["3"]["count"]) / total * 100, 2
    )

    result: dict[str, Any] = {
        "total_draws": total,
        "avg_zones_covered": avg,
        "most_common_zones": most_common,
        "full_spread_pct": full_spread,
        "concentrated_pct": concentrated,
        "zone_coverage_distribution": dist,
    }
    _zone_coverage_cache[cache_key] = result
    return result


def _get_quartile(n: int) -> int:
    """번호 n의 사분위 구간(1~4)을 반환합니다 (SPEC-LOTTO-099, Python 3.9 호환).

    Q1: 1~11, Q2: 12~22, Q3: 23~33, Q4: 34~45
    """
    if n <= 11:
        return 1
    elif n <= 22:
        return 2
    elif n <= 33:
        return 3
    else:
        return 4


# @MX:NOTE: [AUTO] SPEC-LOTTO-099 — 사분위 구간 분포 분석 함수
# @MX:SPEC: SPEC-LOTTO-099
def get_quartile_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    """회차별 본번호 6개를 4개 사분위 구간(Q1~Q4)으로 분류하여 분포를 분석합니다 (SPEC-LOTTO-099).

    구간 정의:
        Q1: 1~11 (11개), Q2: 12~22 (11개), Q3: 23~33 (11개), Q4: 34~45 (12개)

    각 회차별 q1_count+q2_count+q3_count+q4_count = 6이어야 한다.
    조합 키는 "{q1}-{q2}-{q3}-{q4}" 형식의 문자열 (예: "2-1-2-1").

    균형 분포(balanced): q1, q2, q3, q4 각각이 1 또는 2인 회차.
    쏠림 분포(skewed): 어느 하나의 구간에 4개 이상 번호가 몰린 회차.
    most_common_combination 동률 시 사전순(lexicographic) 앞선 값 선택.
    캐시 키는 str(len(draws))이며 invalidate_cache()로 무효화된다.

    Args:
        draws: 분석 대상 회차 리스트. None 또는 빈 리스트이면 total_draws=0,
               most_common_combination="0-0-0-0", 나머지 값 0 반환.

    Returns:
        {total_draws, avg_q1, avg_q2, avg_q3, avg_q4,
         most_common_combination, balanced_pct, skewed_pct,
         quartile_distribution} 매핑.
    """
    cache_key = str(len(draws) if draws else 0)
    cached: dict[str, Any] | None = _quartile_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    empty_result: dict[str, Any] = {
        "total_draws": 0,
        "avg_q1": 0.0,
        "avg_q2": 0.0,
        "avg_q3": 0.0,
        "avg_q4": 0.0,
        "most_common_combination": "0-0-0-0",
        "balanced_pct": 0.0,
        "skewed_pct": 0.0,
        "quartile_distribution": {},
    }

    if not draws:
        _quartile_dist_cache[cache_key] = empty_result
        return empty_result

    pattern_counts: dict[str, int] = {}
    total = 0
    sum_q1 = sum_q2 = sum_q3 = sum_q4 = 0
    balanced = 0
    skewed = 0

    for draw in draws:
        if draw is None:
            continue
        nums = draw.numbers()  # 정렬된 본번호 6개 (보너스 제외)
        if not nums:
            continue
        q1 = q2 = q3 = q4 = 0
        for n in nums:
            q = _get_quartile(n)
            if q == 1:
                q1 += 1
            elif q == 2:
                q2 += 1
            elif q == 3:
                q3 += 1
            else:
                q4 += 1
        pattern = f"{q1}-{q2}-{q3}-{q4}"
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        sum_q1 += q1
        sum_q2 += q2
        sum_q3 += q3
        sum_q4 += q4
        # 균형 분포: 각 구간이 1 또는 2개
        if (q1 >= 1 and q1 <= 2 and q2 >= 1 and q2 <= 2
                and q3 >= 1 and q3 <= 2 and q4 >= 1 and q4 <= 2):
            balanced += 1
        # 쏠림 분포: 어느 한 구간에 4개 이상
        if q1 >= 4 or q2 >= 4 or q3 >= 4 or q4 >= 4:
            skewed += 1
        total += 1

    if total == 0:
        _quartile_dist_cache[cache_key] = empty_result
        return empty_result

    # 동률 시 사전순(lexicographic) 앞선 값 선택
    max_cnt = max(pattern_counts.values())
    most_common = min(k for k, v in pattern_counts.items() if v == max_cnt)

    # quartile_distribution: 관측된 패턴만 포함, {count, pct} 형태
    dist: dict[str, dict[str, Any]] = {}
    for pattern, cnt in pattern_counts.items():
        dist[pattern] = {
            "count": cnt,
            "pct": round(cnt / total * 100, 2),
        }

    result: dict[str, Any] = {
        "total_draws": total,
        "avg_q1": round(sum_q1 / total, 2),
        "avg_q2": round(sum_q2 / total, 2),
        "avg_q3": round(sum_q3 / total, 2),
        "avg_q4": round(sum_q4 / total, 2),
        "most_common_combination": most_common,
        "balanced_pct": round(balanced / total * 100, 2),
        "skewed_pct": round(skewed / total * 100, 2),
        "quartile_distribution": dist,
    }
    _quartile_dist_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-100: 통계 기반 번호 조합 적합도 점수 (Fitness Score)
# ---------------------------------------------------------------------------

def _get_fitness_grade(score: float) -> str:
    """점수에 따른 등급을 반환한다.

    # @MX:NOTE: [AUTO] 등급 임계값 — S>=80, A>=60, B>=40, C>=20, D<20
    # @MX:SPEC: SPEC-LOTTO-100
    """
    if score >= 80.0:
        return "S"
    if score >= 60.0:
        return "A"
    if score >= 40.0:
        return "B"
    if score >= 20.0:
        return "C"
    return "D"


def _fitness_span_bucket(numbers: list[int]) -> str:
    """6개 번호의 스팬 구간 버킷 키를 반환한다 (적합도 점수용)."""
    span = max(numbers) - min(numbers)
    if span <= 10:
        return "10 이하"
    if span <= 20:
        return "11-20"
    if span <= 25:
        return "21-25"
    if span <= 30:
        return "26-30"
    if span <= 35:
        return "31-35"
    if span <= 40:
        return "36-40"
    return "41 이상"


def _fitness_total_sum_bucket(numbers: list[int]) -> str:
    """6개 번호 합계의 구간 버킷 키를 반환한다."""
    # _TOTAL_SUM_BUCKETS = ["21-80","81-110","111-130","131-150","151-170","171-255"]
    total = sum(numbers)
    if total <= 80:
        return "21-80"
    if total <= 110:
        return "81-110"
    if total <= 130:
        return "111-130"
    if total <= 150:
        return "131-150"
    if total <= 170:
        return "151-170"
    return "171-255"


def _fitness_min_gap_bucket(numbers: list[int]) -> str:
    """정렬된 번호들의 최소 갭 구간 버킷 키를 반환한다 (적합도 점수용).

    # @MX:NOTE: [AUTO] _MIN_GAP_KEYS = ["1","2","3","4-5","6-10","11+"]
    """
    sorted_nums = sorted(numbers)
    gaps = [sorted_nums[i + 1] - sorted_nums[i] for i in range(len(sorted_nums) - 1)]  # noqa: B905
    min_gap = min(gaps)
    if min_gap == 1:
        return "1"
    if min_gap == 2:
        return "2"
    if min_gap == 3:
        return "3"
    if min_gap <= 5:
        return "4-5"
    if min_gap <= 10:
        return "6-10"
    return "11+"


def _fitness_gap_median_bucket(numbers: list[int]) -> str:
    """정렬된 번호들의 갭 중앙값 구간 버킷 키를 반환한다 (적합도 점수용).

    # @MX:NOTE: [AUTO] gap_median = sorted(gaps)[2] (5개 갭의 3번째)
    # @MX:SPEC: SPEC-LOTTO-099
    # _GAP_MEDIAN_KEYS = ["1-2","3-4","5-6","7-8","9-10","11+"]
    """
    sorted_nums = sorted(numbers)
    gaps = sorted([sorted_nums[i + 1] - sorted_nums[i] for i in range(len(sorted_nums) - 1)])  # noqa: B905
    gap_median = gaps[2]  # 3번째 값 (인덱스 2)
    if gap_median <= 2:
        return "1-2"
    if gap_median <= 4:
        return "3-4"
    if gap_median <= 6:
        return "5-6"
    if gap_median <= 8:
        return "7-8"
    if gap_median <= 10:
        return "9-10"
    return "11+"


def _quartile_key(numbers: list[int]) -> str:
    """6개 번호의 사분위 분포 패턴 키를 반환한다 (예: '2-2-1-1').

    # @MX:NOTE: [AUTO] Q1=1-11, Q2=12-22, Q3=23-33, Q4=34-45
    """
    q_counts = [0, 0, 0, 0]
    for n in numbers:
        if n <= 11:
            q_counts[0] += 1
        elif n <= 22:
            q_counts[1] += 1
        elif n <= 33:
            q_counts[2] += 1
        else:
            q_counts[3] += 1
    return f"{q_counts[0]}-{q_counts[1]}-{q_counts[2]}-{q_counts[3]}"


def _zone_coverage_key(numbers: list[int]) -> str:
    """6개 번호가 커버하는 구간 수를 문자열로 반환한다.

    # @MX:NOTE: [AUTO] 구간 = (num-1)//5, 1~9 구간 중 몇 개를 커버하는지
    """
    zones = {(n - 1) // 5 for n in numbers}
    return str(len(zones))


def _consecutive_pairs_bucket(numbers: list[int]) -> str:
    """연속 쌍의 수를 기반으로 consecutive_pairs 버킷 키를 반환한다.

    # @MX:NOTE: [AUTO] _CONSECUTIVE_BUCKETS = ["0","1","2","3+"]
    """
    sorted_nums = sorted(numbers)
    pair_count = sum(
        1 for i in range(len(sorted_nums) - 1)  # noqa: B905
        if sorted_nums[i + 1] - sorted_nums[i] == 1
    )
    if pair_count >= 3:
        return "3+"
    return str(pair_count)


def _get_flat_pct(dist: dict[str, int], key: str, total: int) -> float:
    """플랫(count만 있는) 분포에서 pct를 계산한다."""
    if total <= 0:
        return 0.0
    count = dist.get(key, 0)
    return round(count / total * 100, 2)


def _get_nested_pct(dist: dict[str, Any], key: str) -> float:
    """중첩({count, pct}) 분포에서 pct를 반환한다."""
    entry = dist.get(key)
    if entry is None:
        return 0.0
    if isinstance(entry, dict):
        return float(entry.get("pct", 0.0))
    return 0.0


def _primes_set() -> set[int]:
    """1~45 범위의 소수 집합을 반환한다."""
    return {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43}


# @MX:ANCHOR: [AUTO] 통계 기반 번호 조합 적합도 점수 계산 — fan_in >= 3 예상
# @MX:REASON: api.py, pages.py, 테스트에서 직접 호출됨
# @MX:SPEC: SPEC-LOTTO-100
def get_fitness_score(numbers: list[int], draws: list[DrawResult] | None) -> dict[str, Any]:
    """6개 번호 조합의 역대 당첨 패턴 부합도를 0~100 점수로 반환한다.

    15개 통계 각각의 해당 구간 출현 비율(pct)을 평균하여 점수를 계산한다.

    Args:
        numbers: 분석할 6개 번호 리스트 (1~45, 중복 없음)
        draws: 역대 당첨 회차 리스트 (None 또는 빈 리스트면 0점 반환)

    Returns:
        {"numbers", "fitness_score", "grade", "disclaimer", "breakdown"}

    Raises:
        ValueError: 번호 6개 미충족, 범위 오류, 중복 오류
    """
    # 입력 유효성 검사
    if len(numbers) != 6:
        raise ValueError(f"번호는 정확히 6개여야 합니다. 현재: {len(numbers)}개")
    if any(n < 1 or n > 45 for n in numbers):  # noqa: B905
        raise ValueError("번호는 1~45 범위여야 합니다.")
    if len(set(numbers)) != 6:
        raise ValueError("중복 번호가 있습니다.")

    # 빈 회차 처리
    if not draws:
        return {
            "numbers": sorted(numbers),
            "fitness_score": 0.0,
            "grade": "D",
            "disclaimer": "당첨 이력 데이터가 없어 점수를 계산할 수 없습니다.",
            "breakdown": [],
        }

    sorted_nums = sorted(numbers)

    # 각 통계 함수 호출 및 구간 pct 조회
    pcts: list[float] = []
    breakdown: list[dict[str, Any]] = []

    def _add(name: str, label: str, pct: float) -> None:
        pcts.append(pct)
        breakdown.append({"name": name, "label": label, "pct": round(float(pct), 2)})

    # 1. 홀짝 분포
    odd_even = get_odd_even_stats(draws)
    odd_count = sum(1 for n in numbers if n % 2 == 1)  # noqa: B905
    oe_dist = odd_even["odd_distribution"]
    oe_total = sum(oe_dist.values())
    _add("odd_even", f"홀수 {odd_count}개",
         _get_flat_pct(oe_dist, odd_count, oe_total))

    # 2. 고저 분포 (low=1~22)
    high_low = get_high_low_stats(draws)
    low_count = sum(1 for n in numbers if n <= 22)  # noqa: B905
    hl_dist = high_low["low_distribution"]
    hl_total = sum(hl_dist.values())
    _add("high_low", f"저번호 {low_count}개",
         _get_flat_pct(hl_dist, low_count, hl_total))

    # 3. 합계 구간 분포
    total_sum_stat = get_total_sum_stats(draws)
    ts_key = _fitness_total_sum_bucket(sorted_nums)
    ts_dist = total_sum_stat["total_sum_distribution"]
    ts_total = sum(ts_dist.values())
    _add("total_sum", f"합계 구간 {ts_key}",
         _get_flat_pct(ts_dist, ts_key, ts_total))

    # 4. 스팬 분포
    span_stat = get_span_stats(draws)
    sp_key = _fitness_span_bucket(sorted_nums)
    _add("span", f"스팬 {sp_key}",
         _get_nested_pct(span_stat["span_distribution"], sp_key))

    # 5. 연속 쌍 (pair_distribution, int 키)
    consec_stat = get_consecutive_pattern_stats(draws)
    cp_dist = consec_stat["pair_distribution"]
    cp_total = sum(cp_dist.values())
    consec_sorted = sorted(sorted_nums)
    pair_count = sum(
        1 for i in range(len(consec_sorted) - 1)  # noqa: B905
        if consec_sorted[i + 1] - consec_sorted[i] == 1
    )
    _add("consecutive", f"연속쌍 {pair_count}개",
         _get_flat_pct(cp_dist, pair_count, cp_total))

    # 6. AC값 분포
    ac_stat = get_ac_value_stats(draws)
    ac_val = compute_ac_value(sorted_nums)
    _add("ac_value", f"AC값 {ac_val}",
         _get_nested_pct(ac_stat["ac_distribution"], str(ac_val)))

    # 7. 사분위 분포
    quartile_stat = get_quartile_dist_stats(draws)
    q_key = _quartile_key(sorted_nums)
    _add("quartile", f"사분위 {q_key}",
         _get_nested_pct(quartile_stat["quartile_distribution"], q_key))

    # 8. 구간 커버리지 분포
    zone_stat = get_zone_coverage_stats(draws)
    z_key = _zone_coverage_key(sorted_nums)
    _add("zone_coverage", f"구간 커버 {z_key}개",
         _get_nested_pct(zone_stat["zone_coverage_distribution"], z_key))

    # 9. 최소 갭 분포
    min_gap_stat = get_min_gap_dist_stats(draws)
    mg_key = _fitness_min_gap_bucket(sorted_nums)
    _add("min_gap", f"최소갭 {mg_key}",
         _get_nested_pct(min_gap_stat["min_gap_distribution"], mg_key))

    # 10. 갭 중앙값 분포
    gap_med_stat = get_gap_median_dist_stats(draws)
    gm_key = _fitness_gap_median_bucket(sorted_nums)
    _add("gap_median", f"갭중앙값 {gm_key}",
         _get_nested_pct(gap_med_stat["gap_median_distribution"], gm_key))

    # 11. 소수 개수 분포
    prime_stat = get_prime_stats(draws)
    prime_count = sum(1 for n in numbers if n in _primes_set())  # noqa: B905
    pr_dist = prime_stat["prime_distribution"]
    pr_total = sum(pr_dist.values())
    _add("prime", f"소수 {prime_count}개",
         _get_flat_pct(pr_dist, prime_count, pr_total))

    # 12. 끝수 합계 분포 (last_digit_sum — int 키, 관측값만)
    lds_stat = get_last_digit_sum_stats(draws)
    last_digit_sum = sum(n % 10 for n in numbers)  # noqa: B905
    lds_dist = lds_stat["sum_distribution"]
    lds_total = sum(lds_dist.values())
    _add("last_digit_sum", f"끝수합 {last_digit_sum}",
         _get_flat_pct(lds_dist, last_digit_sum, lds_total))

    # 13. 합계 끝자리 분포 (sum_last_digit)
    sld_stat = get_sum_last_digit_stats(draws)
    total_sum = sum(numbers)
    sld_key = str(total_sum % 10)
    _add("sum_last_digit", f"합계끝자리 {sld_key}",
         _get_nested_pct(sld_stat["sum_last_digit_distribution"], sld_key))

    # 14. 연속쌍 분포 (consecutive_pairs, str 키 "0"/"1"/"2"/"3+")
    cp_pairs_stat = get_consecutive_pairs_stats(draws)
    cpairs_key = _consecutive_pairs_bucket(sorted_nums)
    _add("consecutive_pairs", f"연속쌍구간 {cpairs_key}",
         _get_nested_pct(cp_pairs_stat["consecutive_distribution"], cpairs_key))

    # 15. AC값 분포 (ac_value_dist — ac_value_stats와 동일 함수)
    ac_dist_stat = get_ac_value_stats(draws)
    _add("ac_value_dist", f"AC분포 {ac_val}",
         _get_nested_pct(ac_dist_stat["ac_distribution"], str(ac_val)))

    # 평균 점수 계산
    avg_pct = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
    grade = _get_fitness_grade(avg_pct)

    return {
        "numbers": sorted_nums,
        "fitness_score": avg_pct,
        "grade": grade,
        "disclaimer": (
            "이 점수는 과거 통계 기반 분석 결과이며 당첨을 보장하지 않습니다. "
            "로또는 무작위 추첨이므로 모든 조합의 당첨 확률은 동일합니다."
        ),
        "breakdown": breakdown,
    }


# @MX:ANCHOR: [AUTO] 적합도 기반 번호 추천 — pool에서 고적합도 조합 선별
# @MX:REASON: api.py, pages.py에서 호출되는 SPEC-LOTTO-101 핵심 진입점
# @MX:SPEC: SPEC-LOTTO-101
def get_fitness_recommendations(
    count: int = 5,
    min_score: float = 60.0,
    pool_size: int = 1000,
    draws: list[DrawResult] | None = None,
) -> list[dict[str, Any]]:
    """pool_size개 무작위 조합 중 min_score 이상의 상위 count개 적합도 추천을 반환한다.

    get_fitness_score(SPEC-LOTTO-100)로 각 조합의 적합도를 계산하고,
    min_score 이상만 필터링해 점수 내림차순으로 정렬한 뒤 상위 count개를 반환한다.

    Args:
        count: 반환할 추천 개수 (기본 5)
        min_score: 최소 적합도 점수 임계값 0~100 (기본 60.0)
        pool_size: 평가할 무작위 조합 개수 (기본 1000)
        draws: 역대 당첨 회차 (None이면 get_draws() 호출)

    Returns:
        [{"numbers": [int,...], "score": float, "grade": str}, ...]
        score 내림차순 정렬, 최대 count개.
    """
    if draws is None:
        draws = get_draws()

    results: list[dict[str, Any]] = []
    for _ in range(pool_size):
        numbers = sorted(random.sample(range(1, 46), 6))
        fitness = get_fitness_score(numbers, draws)
        score = float(fitness["fitness_score"])
        if score >= min_score:
            results.append({
                "numbers": numbers,
                "score": score,
                "grade": fitness["grade"],
            })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:count]


# SPEC-LOTTO-102: 번호 조합 회차별 백테스트
# 한국 로또 6/45 당첨 등수 고정 키 (발생 0인 등급도 포함)
_COMBO_GRADES = ["1등", "2등", "3등", "4등", "5등", "꽝"]
_COMBO_DISCLAIMER = (
    "이 시뮬레이션은 과거 회차 결과에 대한 회고 분석이며 "
    "미래 당첨 가능성을 예측하지 않습니다."
)


def _judge_grade(match_count: int, bonus_match: bool) -> str:
    """일치 개수와 보너스 일치 여부로 한국 로또 당첨 등수를 판정한다.

    2등(5개+보너스) 판정을 3등(5개)보다 먼저 검사한다.
    """
    if match_count == 6:  # noqa: PLR2004 — 본번호 6개 일치
        return "1등"
    if match_count == 5 and bonus_match:  # noqa: PLR2004 — 5개 + 보너스
        return "2등"
    if match_count == 5:  # noqa: PLR2004 — 5개, 보너스 불일치
        return "3등"
    if match_count == 4:  # noqa: PLR2004 — 4개 일치
        return "4등"
    if match_count == 3:  # noqa: PLR2004 — 3개 일치
        return "5등"
    return "꽝"


# @MX:ANCHOR: [AUTO] 사용자 지정 6개 번호를 역대 회차에 백테스트하는 핵심 진입점
# @MX:REASON: api.py(POST /api/stats/simulate)에서 호출되는 SPEC-LOTTO-102 핵심 함수
# @MX:SPEC: SPEC-LOTTO-102
def get_combo_simulation(
    numbers: list[int],
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    """사용자 지정 6개 번호를 역대 모든 회차에 백테스트한다.

    Args:
        numbers: 시뮬레이션할 6개 번호 (1~45, 중복 없음)
        draws: 역대 당첨 회차 리스트 (None 또는 빈 리스트면 빈 요약 반환)

    Returns:
        {"numbers", "summary", "rounds", "fitness", "disclaimer"}

    Raises:
        ValueError: 번호 6개 미충족, 범위(1~45) 오류, 중복 오류
    """
    # 입력 검증 (REQ-SIM-N01, N02, N03)
    if len(numbers) != 6:  # noqa: PLR2004 — 로또 번호는 정확히 6개
        raise ValueError(f"번호는 정확히 6개여야 합니다. 현재: {len(numbers)}개")
    if any(n < 1 or n > 45 for n in numbers):  # noqa: B905, PLR2004 — 1~45 범위
        raise ValueError("번호는 1~45 범위여야 합니다.")
    if len(set(numbers)) != 6:  # noqa: PLR2004 — 중복 없는 6개
        raise ValueError("중복된 번호가 있습니다.")

    sorted_numbers = sorted(numbers)
    user_set = set(sorted_numbers)

    grade_counts: dict[str, int] = dict.fromkeys(_COMBO_GRADES, 0)

    # 빈 회차 처리 (REQ-SIM-S01)
    if not draws:
        return {
            "numbers": sorted_numbers,
            "summary": {
                "total_rounds": 0,
                "grade_counts": grade_counts,
                "grade_percentages": dict.fromkeys(_COMBO_GRADES, 0.0),
            },
            "rounds": [],
            "fitness": {"fitness_score": 0.0, "grade": "D"},
            "disclaimer": _COMBO_DISCLAIMER,
        }

    rounds_detail: list[dict[str, Any]] = []
    for draw in draws:
        # REQ-SIM-N04: 보너스는 match_count에 포함하지 않음
        match_count = len(user_set & set(draw.numbers()))
        bonus_match = draw.bonus in user_set
        grade = _judge_grade(match_count, bonus_match)
        grade_counts[grade] += 1
        rounds_detail.append({
            "draw_no": draw.drwNo,
            "date": str(draw.date),
            "match_count": match_count,
            "bonus_match": bonus_match,
            "grade": grade,
        })

    total = len(draws)
    grade_percentages = {
        g: round(grade_counts[g] / total * 100, 2) for g in _COMBO_GRADES
    }

    # REQ-SIM-U06: 동일 조합의 적합도 점수 계산
    fitness_raw = get_fitness_score(sorted_numbers, draws)
    fitness = {
        "fitness_score": fitness_raw["fitness_score"],
        "grade": fitness_raw["grade"],
    }

    return {
        "numbers": sorted_numbers,
        "summary": {
            "total_rounds": total,
            "grade_counts": grade_counts,
            "grade_percentages": grade_percentages,
        },
        "rounds": rounds_detail,
        "fitness": fitness,
        "disclaimer": _COMBO_DISCLAIMER,
    }


# ─── SPEC-LOTTO-103: 보너스 번호 분석 ─────────────────────────────────────────

# SPEC-LOTTO-103 REQ-BON-N03: 회고 분석임을 명시하는 면책 고지
_BONUS_DISCLAIMER = (
    "이 분석은 과거 회차 보너스 번호에 대한 회고 분석이며 "
    "미래 보너스 번호를 예측하지 않습니다."
)

# SPEC-LOTTO-103 REQ-BON-S03: hot/cold 판정 배율 (평균 대비)
_BONUS_HOT_RATIO = 1.2
_BONUS_COLD_RATIO = 0.8
# SPEC-LOTTO-103 REQ-BON-U04/U06: top/cooccurrence 반환 개수 한계
_BONUS_TOP_LIMIT = 10
_BONUS_COOC_LIMIT = 5


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-103 보너스 번호 분석 단일 진입점
# @MX:REASON: /api/stats/bonus API와 /stats/bonus 페이지가 모두 의존하는 순수 분석 함수
# @MX:SPEC: SPEC-LOTTO-103 REQ-BON-U01
def get_bonus_analysis(
    draws: list[DrawResult] | None,
    recent_n: int = 50,
) -> dict[str, Any]:
    """역대 보너스 번호의 빈도·비율·동시출현·최근추세를 분석한다 (SPEC-LOTTO-103).

    본번호 6개(n1~n6)는 동시 출현(cooccurrence) 계산에만 사용하고,
    1차 분석 대상은 보너스 번호(draw.bonus)이다. 본번호 분포와 보너스 분포는
    엄격히 분리된다(REQ-BON-N02).

    hot/cold/normal 판정은 방식 A(전체 기준)를 채택한다: 번호별 전체 보너스
    빈도를 평균 빈도(total_draws/45)와 비교하여 평균*1.2 초과는 "hot",
    평균*0.8 미만은 "cold", 그 외는 "normal"로 분류한다(REQ-BON-S03).

    Args:
        draws: 추첨 결과 리스트. None 또는 빈 리스트면 0 채움 결과를 반환한다.
        recent_n: 최근 추세 윈도우 크기 (기본 50). 전체보다 크면 전체를 사용한다.

    Returns:
        {
          "total_draws", "recent_n", "recent_count",
          "bonus_frequency", "bonus_percentage",
          "top_bonus", "recent_bonus", "cooccurrence",
          "hot_cold", "disclaimer"
        }
    """
    # REQ-BON-S01: None/빈 데이터 가드 — 1~45 키를 0/0.0/빈 값으로 채운다
    if not draws:
        zero_freq = dict.fromkeys(range(1, 46), 0)
        zero_pct = dict.fromkeys(range(1, 46), 0.0)
        empty_cooc: dict[int, list[dict[str, int]]] = {
            n: [] for n in range(1, 46)
        }
        all_normal = dict.fromkeys(range(1, 46), "normal")
        return {
            "total_draws": 0,
            "recent_n": recent_n,
            "recent_count": 0,
            "bonus_frequency": zero_freq,
            "bonus_percentage": zero_pct,
            "top_bonus": [],
            "recent_bonus": {"frequency": dict.fromkeys(range(1, 46), 0), "recent_count": 0},
            "cooccurrence": empty_cooc,
            "hot_cold": all_normal,
            "disclaimer": _BONUS_DISCLAIMER,
        }

    total_draws = len(draws)

    # REQ-BON-U02: 전체 보너스 빈도 (1~45 전체 키, 0채움)
    bonus_frequency = dict.fromkeys(range(1, 46), 0)
    for draw in draws:
        bonus_frequency[draw.bonus] += 1

    # REQ-BON-U03: 보너스 비율 (소수 2자리)
    bonus_percentage = {
        n: round(bonus_frequency[n] / total_draws * 100, 2) for n in range(1, 46)
    }

    # REQ-BON-U04: top_bonus — 빈도 내림차순, 동률 시 작은 번호 우선, 상위 10
    sorted_numbers = sorted(
        range(1, 46), key=lambda n: (-bonus_frequency[n], n)
    )
    top_bonus = [
        {
            "number": n,
            "count": bonus_frequency[n],
            "percentage": bonus_percentage[n],
        }
        for n in sorted_numbers[:_BONUS_TOP_LIMIT]
    ]

    # REQ-BON-U05: 최근 추세 — 회차 오름차순 정렬 후 최근 N개 슬라이싱
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    recent_slice = sorted_draws[-recent_n:]
    recent_count = len(recent_slice)
    recent_freq = dict.fromkeys(range(1, 46), 0)
    for draw in recent_slice:
        recent_freq[draw.bonus] += 1
    recent_bonus = {"frequency": recent_freq, "recent_count": recent_count}

    # REQ-BON-U06: 동시 출현 — 보너스별 본번호 카운트 후 상위 5 (보너스 자기 제외)
    cooc_counters: dict[int, Counter[int]] = {n: Counter() for n in range(1, 46)}
    for draw in draws:
        b = draw.bonus
        for main in draw.numbers():  # numbers()는 메서드 (본번호만)
            cooc_counters[b][main] += 1
    cooccurrence: dict[int, list[dict[str, int]]] = {}
    for n in range(1, 46):
        # 동률 시 작은 번호 우선: (-count, number)로 정렬
        items = sorted(
            cooc_counters[n].items(), key=lambda kv: (-kv[1], kv[0])
        )[:_BONUS_COOC_LIMIT]
        cooccurrence[n] = [{"number": num, "count": cnt} for num, cnt in items]

    # REQ-BON-S03: hot/cold/normal 판정 (방식 A — 전체 빈도 vs 평균 빈도)
    average = total_draws / 45
    hot_cold: dict[int, str] = {}
    for n in range(1, 46):
        count = bonus_frequency[n]
        if count > average * _BONUS_HOT_RATIO:
            hot_cold[n] = "hot"
        elif count < average * _BONUS_COLD_RATIO:
            hot_cold[n] = "cold"
        else:
            hot_cold[n] = "normal"

    return {
        "total_draws": total_draws,
        "recent_n": recent_n,
        "recent_count": recent_count,
        "bonus_frequency": bonus_frequency,
        "bonus_percentage": bonus_percentage,
        "top_bonus": top_bonus,
        "recent_bonus": recent_bonus,
        "cooccurrence": cooccurrence,
        "hot_cold": hot_cold,
        "disclaimer": _BONUS_DISCLAIMER,
    }


# ─── SPEC-LOTTO-104: 번호 출현 주기(recency / interval) 분석 ──────────────────

# SPEC-LOTTO-104 REQ-REC-N03: 회고 분석임을 명시하는 면책 고지 (도박사의 오류 경계)
_RECENCY_DISCLAIMER = (
    "이 분석은 과거 회차에 대한 회고 분석이며 미래 출현을 예측하지 않습니다. "
    "오래 미출현한 번호가 곧 나올 확률이 높아지는 것은 아닙니다."
)


def _build_recency_number_item(
    number: int,
    occ_idx: list[int],
    last_idx: int,
) -> dict[str, Any]:
    """한 번호의 출현 인덱스 리스트로부터 주기 통계 항목을 생성한다.

    출현이 없으면 모든 통계는 None/0, 1회면 간격 통계만 None.
    """
    appearance_count = len(occ_idx)
    if appearance_count == 0:
        # REQ-REC-S01/U03: 미출현 → last_seen_ago=None, 간격 None
        return {
            "number": number,
            "last_seen_ago": None,
            "avg_interval": None,
            "max_interval": None,
            "min_interval": None,
            "appearance_count": 0,
        }

    # REQ-REC-U03: 가장 최근 회차(last_idx) 기준 마지막 출현까지 경과 회차
    last_seen_ago = last_idx - occ_idx[-1]

    # REQ-REC-U04/U05: 연속 출현 사이 실제 간격 표본
    gaps = [occ_idx[i + 1] - occ_idx[i] for i in range(appearance_count - 1)]
    if gaps:
        avg_interval: float | None = round(sum(gaps) / len(gaps), 2)
        max_interval: int | None = max(gaps)
        min_interval: int | None = min(gaps)
    else:
        # REQ-REC-S02: 1회 출현 → 간격 표본 없음 → None (0이 아님)
        avg_interval = None
        max_interval = None
        min_interval = None

    return {
        "number": number,
        "last_seen_ago": last_seen_ago,
        "avg_interval": avg_interval,
        "max_interval": max_interval,
        "min_interval": min_interval,
        "appearance_count": appearance_count,
    }


def _recency_overdue_key(item: dict[str, Any]) -> tuple[float, int]:
    """overdue 정렬 키 — None(미출현)을 가장 연체된 것으로 취급 (Python 3.9 호환).

    last_seen_ago 내림차순이 되도록 (-값, 번호) 오름차순 정렬 키를 만든다.
    None은 math.inf로 환산해 최상단, 동률은 작은 번호 우선 (REQ-REC-U07).
    """
    last = item["last_seen_ago"]
    val = math.inf if last is None else float(last)
    return (-val, item["number"])


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-104 — 번호 주기 분석 단일 진입점
# @MX:REASON: /api/stats/recency 와 /stats/recency 양쪽에서 호출됨
# @MX:SPEC: SPEC-LOTTO-104 REQ-REC-U01
def get_recency_analysis(
    draws: list[DrawResult] | None,
    top_n: int = 10,
) -> dict[str, Any]:
    """번호 1~45의 마지막 출현 경과·출현 간격(평균/최대/최소) 통계를 분석한다.

    SPEC-LOTTO-047 cycle_analysis와는 별개 기능이다. cycle_analysis는
    avg_cycle = total_draws / appearances(비율 추정치)를 쓰지만, 본 함수는
    avg_interval = mean(연속 출현 사이 실제 간격들)(간격 표본 평균)을 쓴다.
    본 함수는 cycle_analysis를 호출·수정하지 않는다.

    Args:
        draws: 추첨 결과 리스트. None/빈 리스트면 None 채움 결과를 반환한다.
        top_n: overdue 상위 N (기본 10). 라우트에서 1~45로 검증된다.

    Returns:
        {
          "total_draws", "top_n",
          "numbers": [{number, last_seen_ago, avg_interval,
                       max_interval, min_interval, appearance_count}, ...] (45개),
          "overdue": [...], "recent": [...], "disclaimer": "..."
        }
    """
    # REQ-REC-S01: None/빈 데이터 가드 — 45개 항목을 None/0으로 채운다
    if not draws:
        empty_numbers = [
            _build_recency_number_item(n, [], 0) for n in range(1, 46)
        ]
        return {
            "total_draws": 0,
            "top_n": top_n,
            "numbers": empty_numbers,
            "overdue": [],
            "recent": [],
            "disclaimer": _RECENCY_DISCLAIMER,
        }

    # REQ-REC-U03: 회차 오름차순 정렬로 인덱스 기준을 명시한다
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    total_draws = len(sorted_draws)
    last_idx = total_draws - 1

    # REQ-REC-U06/N02: 본번호(numbers())만 단일 패스로 출현 인덱스 수집
    occ_idx: dict[int, list[int]] = {n: [] for n in range(1, 46)}
    for idx, draw in enumerate(sorted_draws):
        for n in draw.numbers():  # numbers()는 메서드 (본번호만, 보너스 제외)
            occ_idx[n].append(idx)

    # REQ-REC-U02: 1~45 모든 항목을 번호 오름차순으로 생성
    numbers = [
        _build_recency_number_item(n, occ_idx[n], last_idx)
        for n in range(1, 46)
    ]

    # REQ-REC-U07: overdue — None 최우선, last_seen_ago 내림차순, 동률 작은 번호
    overdue = sorted(numbers, key=_recency_overdue_key)[:top_n]

    # REQ-REC-U08: recent — 가장 최근 회차 본번호 (오름차순)
    recent = list(sorted_draws[-1].numbers())

    return {
        "total_draws": total_draws,
        "top_n": top_n,
        "numbers": numbers,
        "overdue": overdue,
        "recent": recent,
        "disclaimer": _RECENCY_DISCLAIMER,
    }


# ─── SPEC-LOTTO-105: 번호 위치별 분포(position distribution) 분석 ──────────────
# SPEC-LOTTO-105 REQ-POS-... : 정렬된 본번호의 위치(1~6)별 통계 요약.
# 회고 분석임을 명시하는 면책 고지 (도박사의 오류 경계).
_POSITION_DISCLAIMER = (
    "이 분석은 과거 회차의 정렬된 당첨번호에 대한 회고적 위치 분포 요약이며 "
    "미래 출현을 예측하지 않습니다. 특정 위치에 작은/큰 수가 자주 나왔다는 사실이 "
    "다음 회차의 선택을 정당화하지 않습니다."
)

# SPEC-LOTTO-105 REQ-POS-003: 본번호는 6개이므로 위치 인덱스는 0~5 고정.
_POSITION_COUNT = 6


def _empty_position_item(position: int) -> dict[str, Any]:
    """REQ-POS-014: 빈/None 입력 시 한 위치의 0 채움 항목을 생성한다."""
    return {
        "position": position,
        "avg": 0.0,
        "median": 0.0,
        "min_ever": 0,
        "max_ever": 0,
        "std": 0.0,
        "top_numbers": [],
    }


def _build_position_item(
    position: int,
    values: list[int],
    total_draws: int,
    top_n: int,
) -> dict[str, Any]:
    """한 위치의 관측 번호 리스트로부터 위치 통계 항목을 생성한다.

    REQ-POS-006: avg/median/std는 소수 2자리 반올림.
    REQ-POS-007/008: top_numbers는 빈도 내림차순·동률 작은 번호 우선, pct 계산.
    표본이 1개면 표본 표준편차 계산 불가 → std=0.0.
    """
    avg = round(sum(values) / len(values), 2)
    median = round(statistics.median(values), 2)
    # statistics.stdev는 표본 1개에서 StatisticsError를 던지므로 분기한다.
    std = round(statistics.stdev(values), 2) if len(values) > 1 else 0.0

    # 빈도 집계 후 (빈도 내림차순, 번호 오름차순)으로 정렬해 상위 top_n개 선택.
    counts = Counter(values)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
    top_numbers = [
        {
            "number": number,
            "count": count,
            "pct": round(count / total_draws * 100, 2),
        }
        for number, count in ordered
    ]

    return {
        "position": position,
        "avg": avg,
        "median": median,
        "min_ever": min(values),
        "max_ever": max(values),
        "std": std,
        "top_numbers": top_numbers,
    }


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-105 — 위치별 분포 분석 단일 진입점
# @MX:REASON: /api/stats/position 과 /stats/position 양쪽에서 호출됨
# @MX:SPEC: SPEC-LOTTO-105 REQ-POS-001
def get_position_distribution(
    draws: list[DrawResult] | None,
    top_n: int = 5,
) -> dict[str, Any]:
    """정렬된 본번호의 위치(1~6)별 평균·중앙값·최소·최대·표준편차·최빈 번호를 분석한다.

    기존 number_stats(SPEC-LOTTO-030)의 by_position(번호 중심: 특정 번호가 각
    위치에 나온 횟수)과는 집계 축이 다른 별개 기능이다. 본 함수는 위치를 고정하고
    그 위치에 나타난 번호들의 분포를 통계 요약한다(위치 중심). number_stats를
    호출·수정하지 않는다.

    Args:
        draws: 추첨 결과 리스트. None/빈 리스트면 0 채움 결과를 반환한다.
        top_n: 위치별 최빈 번호 개수 (기본 5). 라우트에서 1~45로 검증된다.

    Returns:
        {
          "total_draws", "top_n",
          "positions": [{position, avg, median, min_ever,
                         max_ever, std, top_numbers}, ...] (6개),
          "disclaimer": "..."
        }
    """
    # NFR-POS-006: f"{len(draws)}:{top_n}" 캐시 키로 프로세스 수명 캐시 재사용.
    cache_key = f"{0 if not draws else len(draws)}:{top_n}"
    cached: dict[str, Any] | None = _position_cache.get(cache_key)
    if cached is not None:
        return cached

    # REQ-POS-014: None/빈 데이터 가드 — 6개 위치를 0으로 채운다.
    if not draws:
        empty_result = {
            "total_draws": 0,
            "top_n": top_n,
            "positions": [
                _empty_position_item(pos) for pos in range(1, _POSITION_COUNT + 1)
            ],
            "disclaimer": _POSITION_DISCLAIMER,
        }
        _position_cache[cache_key] = empty_result
        return empty_result

    total_draws = len(draws)

    # REQ-POS-002/003: 본번호(numbers())만 오름차순 정렬해 위치 인덱스로 펼친다.
    # numbers()는 메서드 호출이며 이미 오름차순 정렬된 본번호 6개를 반환한다.
    position_values: list[list[int]] = [[] for _ in range(_POSITION_COUNT)]
    for draw in draws:
        sorted_numbers = sorted(draw.numbers())  # 방어적 재정렬 (보너스 제외)
        for idx in range(_POSITION_COUNT):
            position_values[idx].append(sorted_numbers[idx])

    positions = [
        _build_position_item(idx + 1, position_values[idx], total_draws, top_n)
        for idx in range(_POSITION_COUNT)
    ]

    result = {
        "total_draws": total_draws,
        "top_n": top_n,
        "positions": positions,
        "disclaimer": _POSITION_DISCLAIMER,
    }
    _position_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-106: 홀짝·고저 조합 매트릭스 분석
# ---------------------------------------------------------------------------

# REQ-CROSS-001: 고번호 경계 — 번호 > 23(24~45)이 고번호.
_CROSS_HIGH_THRESHOLD = 23
# REQ-CROSS-003: 본번호 6개 기준 odd_count/high_count 범위는 0~6.
_CROSS_AXIS_MAX = 6

_CROSS_DISCLAIMER = (
    "본 분석은 과거 당첨 데이터의 홀짝·고저 결합 분포를 통계적으로 관찰하기 위한 "
    "참고 자료이며, 미래 당첨 번호의 예측력을 보장하지 않습니다. 로또는 매 회차 "
    "독립적인 무작위 추첨입니다."
)


def _empty_cross_matrix() -> dict[str, int]:
    """49개(7×7) 키를 0으로 채운 교차 매트릭스를 생성한다."""
    return {
        f"odd_{i}_high_{j}": 0
        for i in range(_CROSS_AXIS_MAX + 1)
        for j in range(_CROSS_AXIS_MAX + 1)
    }


def _empty_cross_marginal() -> dict[str, int]:
    """0~6 키를 0으로 채운 주변합 매핑을 생성한다."""
    return {str(i): 0 for i in range(_CROSS_AXIS_MAX + 1)}


# @MX:NOTE: [AUTO] SPEC-LOTTO-106 — 홀짝·고저 조합 매트릭스 분석 공개 함수
# @MX:SPEC: SPEC-LOTTO-106 REQ-CROSS-001
def get_cross_pattern_stats(
    draws: list[DrawResult] | None,
    top_n: int = 10,
) -> dict[str, Any]:
    """본번호 6개의 홀수 개수×고번호(>23) 개수 교차 빈도 매트릭스를 분석한다.

    각 회차에 대해 odd_count(홀수 개수 0~6)와 high_count(고번호 개수 0~6)를 구하고,
    (odd_count, high_count) 조합별 회차 수를 49개(7×7) 매트릭스로 집계한다. 상위 빈도
    조합(top_combinations), 각 축의 주변합(marginal_odd/high), 평균(avg_odd/high)을 함께
    제공한다. 기존 홀짝·고저 분석과 달리 두 축의 결합 분포를 하나로 본다(코어 모듈 불변).

    Args:
        draws: 추첨 결과 리스트. None/빈 리스트면 0 채움 결과를 반환한다.
        top_n: 상위 조합 개수 (기본 10). 라우트에서 1~49로 검증된다.

    Returns:
        {
          "total_draws", "top_n",
          "matrix": {"odd_{i}_high_{j}": int, ...} (49개),
          "top_combinations": [{odd_count, high_count, count, pct}, ...],
          "marginal_odd": {"0":int, ..., "6":int},
          "marginal_high": {"0":int, ..., "6":int},
          "avg_odd": float, "avg_high": float,
          "disclaimer": "..."
        }
    """
    # 프로세스 수명 캐시 — invalidate_cache로 무효화(conftest autouse fixture가 호출).
    cache_key = f"{0 if not draws else len(draws)}:{top_n}"
    cached: dict[str, Any] | None = _cross_pattern_cache.get(cache_key)
    if cached is not None:
        return cached

    # REQ-CROSS-008: None/빈 데이터 가드 — 0 채움 구조 반환.
    if not draws:
        empty_result = {
            "total_draws": 0,
            "top_n": top_n,
            "matrix": _empty_cross_matrix(),
            "top_combinations": [],
            "marginal_odd": _empty_cross_marginal(),
            "marginal_high": _empty_cross_marginal(),
            "avg_odd": 0.0,
            "avg_high": 0.0,
            "disclaimer": _CROSS_DISCLAIMER,
        }
        _cross_pattern_cache[cache_key] = empty_result
        return empty_result

    total_draws = len(draws)

    matrix = _empty_cross_matrix()
    marginal_odd = _empty_cross_marginal()
    marginal_high = _empty_cross_marginal()
    odd_sum = 0
    high_sum = 0
    # REQ-CROSS-002/003: 회차별 odd_count·high_count 집계.
    # numbers()는 메서드 호출이며 오름차순 본번호 6개를 반환한다(보너스 제외).
    for draw in draws:
        nums = draw.numbers()
        odd_count = sum(1 for n in nums if n % 2 == 1)
        high_count = sum(1 for n in nums if n > _CROSS_HIGH_THRESHOLD)
        matrix[f"odd_{odd_count}_high_{high_count}"] += 1
        marginal_odd[str(odd_count)] += 1
        marginal_high[str(high_count)] += 1
        odd_sum += odd_count
        high_sum += high_count

    # REQ-CROSS-004: 빈도 상위 top_n 조합. count desc, 동률은 odd asc → high asc.
    combos = [
        {
            "odd_count": i,
            "high_count": j,
            "count": matrix[f"odd_{i}_high_{j}"],
            "pct": round(matrix[f"odd_{i}_high_{j}"] / total_draws * 100, 2),
        }
        for i in range(_CROSS_AXIS_MAX + 1)
        for j in range(_CROSS_AXIS_MAX + 1)
        if matrix[f"odd_{i}_high_{j}"] > 0
    ]
    combos.sort(key=lambda c: (-c["count"], c["odd_count"], c["high_count"]))
    top_combinations = combos[:top_n]

    result = {
        "total_draws": total_draws,
        "top_n": top_n,
        "matrix": matrix,
        "top_combinations": top_combinations,
        "marginal_odd": marginal_odd,
        "marginal_high": marginal_high,
        "avg_odd": round(odd_sum / total_draws, 2),
        "avg_high": round(high_sum / total_draws, 2),
        "disclaimer": _CROSS_DISCLAIMER,
    }
    _cross_pattern_cache[cache_key] = result
    return result


# REQ-PT-001/REQ-PT-NFR-002: 본번호 범위 1~45.
_PERIOD_NUMBER_MAX = 45

_PERIOD_TREND_DISCLAIMER = (
    "본 분석은 과거 당첨 데이터를 초기·중기·최근 3구간으로 나누어 번호별 출현 추이를 "
    "통계적으로 관찰하기 위한 참고 자료이며, 미래 당첨 번호의 예측력을 보장하지 않습니다. "
    "로또는 매 회차 독립적인 무작위 추첨입니다."
)


def _empty_period_numbers() -> list[dict[str, Any]]:
    """번호 1~45를 0/0.0/stable로 채운 추이 항목 리스트를 생성한다."""
    return [
        {
            "number": num,
            "count_early": 0,
            "count_middle": 0,
            "count_recent": 0,
            "pct_early": 0.0,
            "pct_middle": 0.0,
            "pct_recent": 0.0,
            "delta": 0,
            "trend": "stable",
        }
        for num in range(1, _PERIOD_NUMBER_MAX + 1)
    ]


def _count_period(period: list[DrawResult]) -> list[int]:
    """구간 내 회차들에서 번호 1~45 출현 횟수를 집계한다(index 0 = 번호 1)."""
    counts = [0] * _PERIOD_NUMBER_MAX
    for draw in period:
        # numbers()는 메서드 호출이며 오름차순 본번호 6개를 반환한다(보너스 제외).
        for n in draw.numbers():
            counts[n - 1] += 1
    return counts


def _period_pct(count: int, period_size: int) -> float:
    """구간 출현 횟수를 비율(%)로 변환한다. 빈 구간이면 0.0."""
    if period_size == 0:
        return 0.0
    return round(count / period_size * 100, 2)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-107 — 기간별 번호 빈도 추이 분석 공개 함수
# @MX:REASON: API·페이지 두 라우트가 호출하는 진입점(fan_in>=2)이며 구간 분할 슬라이스
#             공식과 정렬 규칙(rising/falling)이 결과 계약의 핵심 불변식이다.
def get_period_trend(
    draws: list[DrawResult] | None,
    top_n: int = 10,
) -> dict[str, Any]:
    """전체 회차를 초기/중기/최근 3구간으로 균등 분할하여 번호별 출현 추이를 분석한다.

    n=len(draws)일 때 슬라이스 공식을 엄격히 적용한다:
    early=draws[0:n//3], middle=draws[n//3:2*n//3], recent=draws[2*n//3:].
    각 번호(1~45)에 대해 구간별 출현 횟수·비율(pct)·델타(count_recent-count_early)·
    추세(rising/falling/stable)를 산출하고, 델타 기준 상위 상승/하락 top_n 번호를 제공한다.
    기존 hot_cold_analysis(최근 N회 vs 전체 단순 비교)와 달리 3구간 시계열 추이를 본다
    (코어 모듈 불변).

    Args:
        draws: 추첨 결과 리스트. None/빈 리스트면 0 채움 결과를 반환한다.
        top_n: 상승/하락 상위 번호 개수 (기본 10). 라우트에서 1~45로 검증된다.

    Returns:
        {
          "total_draws", "top_n",
          "period_sizes": {"early":int, "middle":int, "recent":int},
          "numbers": [{number, count_early, count_middle, count_recent,
                       pct_early, pct_middle, pct_recent, delta, trend}, ...] (45개),
          "top_rising": [...],   # delta desc, number asc
          "top_falling": [...],  # delta asc, number desc
          "disclaimer": "..."
        }
    """
    # 프로세스 수명 캐시 — invalidate_cache로 무효화(conftest autouse fixture가 호출).
    cache_key = f"{0 if not draws else len(draws)}:{top_n}"
    cached: dict[str, Any] | None = _period_trend_cache.get(cache_key)
    if cached is not None:
        return cached

    # REQ-PT-004: None/빈 데이터 가드 — 0 채움 구조 반환.
    if not draws:
        empty_result = {
            "total_draws": 0,
            "top_n": top_n,
            "period_sizes": {"early": 0, "middle": 0, "recent": 0},
            "numbers": _empty_period_numbers(),
            "top_rising": [],
            "top_falling": [],
            "disclaimer": _PERIOD_TREND_DISCLAIMER,
        }
        _period_trend_cache[cache_key] = empty_result
        return empty_result

    total_draws = len(draws)

    # REQ-PT-001/005/006: 구간 분할 슬라이스 공식(단일 진실 원천).
    third = total_draws // 3
    two_thirds = 2 * total_draws // 3
    early = draws[0:third]
    middle = draws[third:two_thirds]
    recent = draws[two_thirds:]
    period_sizes = {
        "early": len(early),
        "middle": len(middle),
        "recent": len(recent),
    }

    early_counts = _count_period(early)
    middle_counts = _count_period(middle)
    recent_counts = _count_period(recent)

    numbers: list[dict[str, Any]] = []
    for idx in range(_PERIOD_NUMBER_MAX):
        count_early = early_counts[idx]
        count_middle = middle_counts[idx]
        count_recent = recent_counts[idx]
        delta = count_recent - count_early
        # REQ-PT-001: 추세 분류(파이썬 3.9 호환 — match/case 미사용).
        if delta > 0:
            trend = "rising"
        elif delta < 0:
            trend = "falling"
        else:
            trend = "stable"
        numbers.append(
            {
                "number": idx + 1,
                "count_early": count_early,
                "count_middle": count_middle,
                "count_recent": count_recent,
                "pct_early": _period_pct(count_early, period_sizes["early"]),
                "pct_middle": _period_pct(count_middle, period_sizes["middle"]),
                "pct_recent": _period_pct(count_recent, period_sizes["recent"]),
                "delta": delta,
                "trend": trend,
            }
        )

    # REQ-PT-002: 상위 상승/하락 — top_rising은 delta desc, number asc;
    #             top_falling은 delta asc, number desc.
    def _top_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "number": item["number"],
            "count_early": item["count_early"],
            "count_middle": item["count_middle"],
            "count_recent": item["count_recent"],
            "delta": item["delta"],
            "trend": item["trend"],
        }

    rising_sorted = sorted(numbers, key=lambda x: (-x["delta"], x["number"]))
    falling_sorted = sorted(numbers, key=lambda x: (x["delta"], -x["number"]))
    top_rising = [_top_item(x) for x in rising_sorted[:top_n]]
    top_falling = [_top_item(x) for x in falling_sorted[:top_n]]

    result = {
        "total_draws": total_draws,
        "top_n": top_n,
        "period_sizes": period_sizes,
        "numbers": numbers,
        "top_rising": top_rising,
        "top_falling": top_falling,
        "disclaimer": _PERIOD_TREND_DISCLAIMER,
    }
    _period_trend_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-108: 번호 월별 출현 분포 분석 (Monthly Distribution Analysis)
# ---------------------------------------------------------------------------

# REQ-MD-001/004: 월(1~12) → 약어. index 0 = 1월(Jan).
_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
_MONTHLY_NUMBER_MAX = 45  # 본번호 범위 1~45

_MONTHLY_DIST_DISCLAIMER = (
    "본 분석은 과거 당첨 데이터를 추첨일의 달(1~12월) 기준으로 그룹화하여 번호별 출현 "
    "빈도를 통계적으로 관찰하기 위한 참고 자료이며, 미래 당첨 번호의 예측력을 보장하지 "
    "않습니다. 로또는 매 회차 독립적인 무작위 추첨입니다."
)


def _empty_monthly_summary() -> list[dict[str, Any]]:
    """월 1~12를 draw_count=0으로 채운 요약 리스트를 생성한다(index 0 = 1월)."""
    return [
        {"month": m, "month_name": _MONTH_NAMES[m - 1], "draw_count": 0}
        for m in range(1, 13)
    ]


def _empty_top_numbers_by_month() -> dict[str, list[dict[str, Any]]]:
    """월 "1"~"12"를 빈 리스트로 채운 매핑을 생성한다."""
    return {str(m): [] for m in range(1, 13)}


def _empty_top_months_by_number() -> list[dict[str, Any]]:
    """번호 1~45를 best_month=0/0/0.0으로 채운 리스트를 생성한다(index 0 = 번호 1)."""
    return [
        {
            "number": num,
            "best_month": 0,
            "best_month_count": 0,
            "best_month_pct": 0.0,
        }
        for num in range(1, _MONTHLY_NUMBER_MAX + 1)
    ]


def _monthly_pct(count: int, draw_count: int) -> float:
    """월 출현 횟수를 비율(%)로 변환한다. 회차 없는 월이면 0.0."""
    if draw_count == 0:
        return 0.0
    return round(count / draw_count * 100, 2)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-108 — 번호 월별 출현 분포 분석 공개 함수
# @MX:REASON: API·페이지 두 라우트가 호출하는 진입점(fan_in>=2)이며 draw.date.month
#             그룹화·정렬 규칙(count desc/number asc, 동률 시 작은 월)이 결과 계약의
#             핵심 불변식이다.
def get_monthly_distribution(
    draws: list[DrawResult] | None,
    top_n: int = 5,
) -> dict[str, Any]:
    """추첨일의 달(1~12월)을 축으로 번호(1~45)의 출현 빈도를 분석한다.

    `draw.date.month`(속성, 1=1월 … 12=12월)로 회차를 월별 그룹화하고, 각 월에서
    번호별 출현 횟수·비율을 집계한다. 회차 인덱스 기준(rolling/period_trend)이 아니라
    달력 기반 주기성을 본다(코어 모듈 불변).

    Args:
        draws: 추첨 결과 리스트. None/빈 리스트면 0 채움 구조를 반환한다.
        top_n: 월별 상위 번호 개수 (기본 5). 라우트에서 1~45로 검증된다.

    Returns:
        {
          "total_draws", "top_n",
          "monthly_summary": [{month, month_name, draw_count}, ...] (12개, index0=1월),
          "top_numbers_by_month": {"1": [{number, count, pct}, ...], ..., "12": [...]},
          "top_months_by_number": [{number, best_month, best_month_count,
                                     best_month_pct}, ...] (45개),
          "disclaimer": "..."
        }
    """
    # 프로세스 수명 캐시 — invalidate_cache로 무효화(conftest autouse fixture가 호출).
    cache_key = f"{0 if not draws else len(draws)}:{top_n}"
    cached: dict[str, Any] | None = _monthly_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    # REQ-MD-005/012: None/빈 데이터 가드 — 0 채움 구조 반환.
    if not draws:
        empty_result = {
            "total_draws": 0,
            "top_n": top_n,
            "monthly_summary": _empty_monthly_summary(),
            "top_numbers_by_month": _empty_top_numbers_by_month(),
            "top_months_by_number": _empty_top_months_by_number(),
            "disclaimer": _MONTHLY_DIST_DISCLAIMER,
        }
        _monthly_dist_cache[cache_key] = empty_result
        return empty_result

    total_draws = len(draws)

    # REQ-MD-001: 월별 회차 수와 월별 번호 카운트 누적.
    # month_draw_count[m] = 월 m(1~12)의 회차 수.
    # month_number_counts[m] = 월 m의 번호별 출현 횟수 리스트(index 0 = 번호 1).
    month_draw_count = dict.fromkeys(range(1, 13), 0)
    month_number_counts = {
        m: [0] * _MONTHLY_NUMBER_MAX for m in range(1, 13)
    }
    for draw in draws:
        # draw.date.month는 속성 접근(int, 1~12). numbers()는 메서드 호출(본번호 6개).
        month = draw.date.month
        month_draw_count[month] += 1
        for n in draw.numbers():
            month_number_counts[month][n - 1] += 1

    # REQ-MD-004: monthly_summary(12개, index 0 = 1월).
    monthly_summary = [
        {
            "month": m,
            "month_name": _MONTH_NAMES[m - 1],
            "draw_count": month_draw_count[m],
        }
        for m in range(1, 13)
    ]

    # REQ-MD-002/009: 월별 상위 top_n 번호 — count desc, 동률은 number asc.
    #                 출현 없는(count=0) 번호는 제외한다.
    top_numbers_by_month: dict[str, list[dict[str, Any]]] = {}
    for m in range(1, 13):
        draw_count = month_draw_count[m]
        counts = month_number_counts[m]
        appeared = [
            {
                "number": idx + 1,
                "count": counts[idx],
                "pct": _monthly_pct(counts[idx], draw_count),
            }
            for idx in range(_MONTHLY_NUMBER_MAX)
            if counts[idx] > 0
        ]
        appeared.sort(key=lambda x: (-x["count"], x["number"]))
        top_numbers_by_month[str(m)] = appeared[:top_n]

    # REQ-MD-003/011: 번호별 최빈 월 — count 최대 월(동률 시 가장 작은 월).
    #                 미출현 번호는 best_month=0.
    top_months_by_number: list[dict[str, Any]] = []
    for idx in range(_MONTHLY_NUMBER_MAX):
        best_month = 0
        best_count = 0
        # 월 1~12 오름차순 순회 — 더 큰 count일 때만 갱신하므로 동률은 작은 월이 유지된다.
        for m in range(1, 13):
            count = month_number_counts[m][idx]
            if count > best_count:
                best_count = count
                best_month = m
        best_pct = (
            _monthly_pct(best_count, month_draw_count[best_month])
            if best_month != 0
            else 0.0
        )
        top_months_by_number.append(
            {
                "number": idx + 1,
                "best_month": best_month,
                "best_month_count": best_count,
                "best_month_pct": best_pct,
            }
        )

    result = {
        "total_draws": total_draws,
        "top_n": top_n,
        "monthly_summary": monthly_summary,
        "top_numbers_by_month": top_numbers_by_month,
        "top_months_by_number": top_months_by_number,
        "disclaimer": _MONTHLY_DIST_DISCLAIMER,
    }
    _monthly_dist_cache[cache_key] = result
    return result


# ─── SPEC-LOTTO-110: 번호 연도별 출현 분포(yearly distribution) 분석 ───────────
# draw.date.year(속성, int)로 회차를 달력 연도(2002~현재)별로 그룹화하여 각 연도에서
# 번호(1~45)의 출현 횟수·비율을 집계한다. period_trend(107, 회차 인덱스 3등분)나
# monthly(108, 달력 월 1~12 고정 버킷)와 달리 실제 달력 연도(가변 개수)를 축으로
# 장기 추세를 본다. 세 기능은 절대 병합하지 않는다. 코어 모듈 불변.
_YEARLY_NUMBER_MAX = 45  # 본번호 범위 1~45

_YEARLY_DIST_DISCLAIMER = (
    "본 분석은 과거 당첨 데이터를 추첨일의 연도(달력 연도) 기준으로 그룹화하여 번호별 "
    "출현 빈도를 통계적으로 관찰하기 위한 참고 자료이며, 미래 당첨 번호의 예측력을 "
    "보장하지 않습니다. 로또는 매 회차 독립적인 무작위 추첨입니다."
)


def _empty_top_years_by_number() -> list[dict[str, Any]]:
    """번호 1~45를 best_year=None/0/0.0으로 채운 리스트를 생성한다(index 0 = 번호 1)."""
    return [
        {
            "number": num,
            "best_year": None,
            "best_year_count": 0,
            "best_year_pct": 0.0,
        }
        for num in range(1, _YEARLY_NUMBER_MAX + 1)
    ]


def _yearly_pct(count: int, draw_count: int) -> float:
    """연도 출현 횟수를 비율(%)로 변환한다. 회차 없는 연도면 0.0."""
    if draw_count == 0:
        return 0.0
    return round(count / draw_count * 100, 2)


# @MX:ANCHOR: [AUTO] SPEC-LOTTO-110 — 번호 연도별 출현 분포 분석 공개 함수
# @MX:REASON: API·페이지 두 라우트가 호출하는 진입점(fan_in>=2)이며 draw.date.year
#             그룹화·정렬 규칙(count desc/number asc, 동률 시 이른 연도)이 결과 계약의
#             핵심 불변식이다.
def get_yearly_distribution(
    draws: list[DrawResult] | None,
    top_n: int = 5,
) -> dict[str, Any]:
    """추첨일의 연도(달력 연도)를 축으로 번호(1~45)의 출현 빈도를 분석한다.

    `draw.date.year`(속성, int)로 회차를 연도별 그룹화하고, 각 연도에서 번호별 출현
    횟수·비율을 집계한다. 회차 인덱스 기준(period_trend)이나 달력 월(monthly)이 아니라
    실제 달력 연도(가변 개수)를 축으로 삼아 장기 추세 패턴을 관찰한다(코어 모듈 불변).

    Args:
        draws: 추첨 결과 리스트. None/빈 리스트면 0 채움 구조를 반환한다.
        top_n: 연도별 상위 번호 개수 (기본 5). 라우트에서 1~45로 검증된다.

    Returns:
        {
          "total_draws", "total_years", "top_n",
          "yearly_summary": [{year, draw_count}, ...] (연도 오름차순),
          "top_numbers_by_year": {"2002": [{number, count, pct}, ...], ...},
          "top_years_by_number": [{number, best_year, best_year_count,
                                    best_year_pct}, ...] (45개, index0=번호1),
          "disclaimer": "..."
        }
    """
    # 프로세스 수명 캐시 — invalidate_cache로 무효화(conftest autouse fixture가 호출).
    cache_key = f"{0 if not draws else len(draws)}:{top_n}"
    cached: dict[str, Any] | None = _yearly_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    # REQ-YD-006: None/빈 데이터 가드 — 0 채움 구조 반환.
    if not draws:
        empty_result = {
            "total_draws": 0,
            "total_years": 0,
            "top_n": top_n,
            "yearly_summary": [],
            "top_numbers_by_year": {},
            "top_years_by_number": _empty_top_years_by_number(),
            "disclaimer": _YEARLY_DIST_DISCLAIMER,
        }
        _yearly_dist_cache[cache_key] = empty_result
        return empty_result

    total_draws = len(draws)

    # REQ-YD-001: 연도별 회차 수와 연도별 번호 카운트 누적.
    # year_draw_count[y] = 연도 y의 회차 수.
    # year_number_counts[y] = 연도 y의 번호별 출현 횟수 리스트(index 0 = 번호 1).
    year_draw_count: dict[int, int] = {}
    year_number_counts: dict[int, list[int]] = {}
    for draw in draws:
        # draw.date.year는 속성 접근(int). numbers()는 메서드 호출(본번호 6개).
        year = draw.date.year
        if year not in year_draw_count:
            year_draw_count[year] = 0
            year_number_counts[year] = [0] * _YEARLY_NUMBER_MAX
        year_draw_count[year] += 1
        counts = year_number_counts[year]
        for n in draw.numbers():
            counts[n - 1] += 1

    sorted_years = sorted(year_draw_count)  # 연도 오름차순

    # REQ-YD-004/005: yearly_summary(연도 오름차순)와 total_years.
    yearly_summary = [
        {"year": y, "draw_count": year_draw_count[y]} for y in sorted_years
    ]

    # REQ-YD-002: 연도별 상위 top_n 번호 — count desc, 동률은 number asc.
    #             출현 없는(count=0) 번호는 제외한다.
    top_numbers_by_year: dict[str, list[dict[str, Any]]] = {}
    for y in sorted_years:
        draw_count = year_draw_count[y]
        counts = year_number_counts[y]
        appeared = [
            {
                "number": idx + 1,
                "count": counts[idx],
                "pct": _yearly_pct(counts[idx], draw_count),
            }
            for idx in range(_YEARLY_NUMBER_MAX)
            if counts[idx] > 0
        ]
        appeared.sort(key=lambda x: (-x["count"], x["number"]))
        top_numbers_by_year[str(y)] = appeared[:top_n]

    # REQ-YD-003/007: 번호별 최빈 연도 — count 최대 연도(동률 시 가장 이른 연도).
    #                 미출현 번호는 best_year=None.
    top_years_by_number: list[dict[str, Any]] = []
    for idx in range(_YEARLY_NUMBER_MAX):
        best_year: int | None = None
        best_count = 0
        # 연도 오름차순 순회 — 더 큰 count일 때만 갱신하므로 동률은 이른 연도가 유지된다.
        for y in sorted_years:
            count = year_number_counts[y][idx]
            if count > best_count:
                best_count = count
                best_year = y
        best_pct = (
            _yearly_pct(best_count, year_draw_count[best_year])
            if best_year is not None
            else 0.0
        )
        top_years_by_number.append(
            {
                "number": idx + 1,
                "best_year": best_year,
                "best_year_count": best_count,
                "best_year_pct": best_pct,
            }
        )

    result = {
        "total_draws": total_draws,
        "total_years": len(sorted_years),
        "top_n": top_n,
        "yearly_summary": yearly_summary,
        "top_numbers_by_year": top_numbers_by_year,
        "top_years_by_number": top_years_by_number,
        "disclaimer": _YEARLY_DIST_DISCLAIMER,
    }
    _yearly_dist_cache[cache_key] = result
    return result


# ─── SPEC-LOTTO-109: 번호 출현 간격 상세 분포(gap distribution) 분석 ───────────
# 각 번호의 연속 출현 간격(drwNo 차이) 표본 전체의 min/max/avg/median/std와
# 6버킷 히스토그램을 산출한다. cycle_analysis(047, 비율 추정)·recency_analysis
# (104, 마지막 출현·평균 간격)와 별개 기능으로, 간격의 "분포"(std·히스토그램)에
# 초점을 둔다. 코어 모듈 불변.
_GAP_DIST_DISCLAIMER = (
    "이 분석은 과거 회차에서 각 번호의 연속 출현 간격을 회고적으로 집계한 "
    "분포 요약이며 미래 출현을 예측하지 않습니다. 특정 번호의 간격이 짧거나 "
    "길었다는 사실이 다음 회차의 선택을 정당화하지 않습니다."
)

# 본번호 범위 1~45.
_GAP_NUMBER_MAX = 45

# REQ-GAP-003: 간격 히스토그램 버킷 라벨(고정 순서). 51 이상은 "51+".
_GAP_BUCKET_LABELS = ["1-10", "11-20", "21-30", "31-40", "41-50", "51+"]


def _empty_gap_histogram() -> dict[str, int]:
    """REQ-GAP-003/006: 모든 버킷이 0인 히스토그램을 생성한다."""
    return dict.fromkeys(_GAP_BUCKET_LABELS, 0)


def _gap_bucket_label(gap: int) -> str:
    """간격값을 6버킷 중 하나의 라벨로 매핑한다(1~10, …, 41~50, 51+)."""
    if gap <= 10:  # noqa: PLR2004
        return "1-10"
    if gap <= 20:  # noqa: PLR2004
        return "11-20"
    if gap <= 30:  # noqa: PLR2004
        return "21-30"
    if gap <= 40:  # noqa: PLR2004
        return "31-40"
    if gap <= 50:  # noqa: PLR2004
        return "41-50"
    return "51+"


def _gap_histogram(gaps: list[int]) -> dict[str, int]:
    """REQ-GAP-003: 간격 리스트를 6버킷 히스토그램으로 집계한다."""
    histogram = _empty_gap_histogram()
    for gap in gaps:
        histogram[_gap_bucket_label(gap)] += 1
    return histogram


def _build_gap_number_item(
    number: int,
    gaps: list[int],
    appearance_count: int,
) -> dict[str, Any]:
    """REQ-GAP-002/003/006: 한 번호의 간격 통계 항목을 생성한다.

    count = len(gaps) = max(appearance_count - 1, 0). count=0이면 모든 통계 None.
    표본이 1개(count=1)면 표본 표준편차 계산 불가 → std_gap=None.
    """
    count = len(gaps)
    if count == 0:
        return {
            "number": number,
            "appearance_count": appearance_count,
            "count": 0,
            "gaps": [],
            "avg_gap": None,
            "median_gap": None,
            "min_gap": None,
            "max_gap": None,
            "std_gap": None,
            "gap_histogram": _empty_gap_histogram(),
        }
    # statistics.stdev는 표본 1개에서 StatisticsError를 던지므로 분기한다.
    std_gap = round(statistics.stdev(gaps), 2) if count > 1 else None
    return {
        "number": number,
        "appearance_count": appearance_count,
        "count": count,
        "gaps": gaps,
        "avg_gap": round(statistics.mean(gaps), 2),
        "median_gap": round(statistics.median(gaps), 2),
        "min_gap": min(gaps),
        "max_gap": max(gaps),
        "std_gap": std_gap,
        "gap_histogram": _gap_histogram(gaps),
    }


def _empty_gap_overall_summary() -> dict[str, Any]:
    """REQ-GAP-004/005: 간격이 하나도 없을 때의 None 채움 요약."""
    return {
        "avg_gap_all": None,
        "max_gap_ever": None,
        "max_gap_number": None,
        "min_gap_ever": None,
        "min_gap_number": None,
    }


def _gap_overall_summary(
    all_gaps_with_owner: list[tuple[int, int]],
) -> dict[str, Any]:
    """REQ-GAP-004: 전체 간격 표본으로 요약을 계산한다.

    all_gaps_with_owner: (gap, number) 쌍 리스트. 번호 1→45 순으로 누적되므로
    동률(같은 gap)일 때 더 작은 번호가 먼저 등장한다. 더 큰/작은 값에서만
    갱신하면 동률은 자연히 가장 작은 번호가 유지된다.
    """
    if not all_gaps_with_owner:
        return _empty_gap_overall_summary()

    gap_values = [gap for gap, _ in all_gaps_with_owner]
    max_gap_ever, max_gap_number = all_gaps_with_owner[0]
    min_gap_ever, min_gap_number = all_gaps_with_owner[0]
    for gap, number in all_gaps_with_owner:
        if gap > max_gap_ever:
            max_gap_ever, max_gap_number = gap, number
        if gap < min_gap_ever:
            min_gap_ever, min_gap_number = gap, number
    return {
        "avg_gap_all": round(statistics.mean(gap_values), 2),
        "max_gap_ever": max_gap_ever,
        "max_gap_number": max_gap_number,
        "min_gap_ever": min_gap_ever,
        "min_gap_number": min_gap_number,
    }


# @MX:ANCHOR: [AUTO] 번호 출현 간격 분포 분석 — API/페이지 라우트의 단일 진입점
# @MX:REASON: api.py·pages.py에서 호출되는 SPEC-LOTTO-109 공개 데이터 함수
# @MX:SPEC: SPEC-LOTTO-109
def get_gap_distribution(draws: list[DrawResult] | None) -> dict[str, Any]:
    """번호 1~45의 연속 출현 간격(drwNo 차이) 상세 분포를 분석한다.

    번호 X가 연속한 두 회차 A, B(그 사이에 X 없음)에서 출현하면
    gap = B.drwNo - A.drwNo 이다. 번호별로 모든 간격을 모아 min/max/avg/median/
    std와 6버킷 히스토그램을 산출하고, 전체 간격 표본으로 역대 최대·최소 간격
    요약을 만든다. cycle_analysis(047)·recency_analysis(104)를 호출·수정하지
    않으며, 간격의 분포(다양성)에 초점을 둔다.

    Args:
        draws: 추첨 결과 리스트. None/빈 리스트면 0 채움 구조를 반환한다.
               drwNo 오름차순을 가정하나 내부에서도 안전하게 정렬한다.

    Returns:
        {
          "total_draws": int,
          "overall_summary": {avg_gap_all, max_gap_ever, max_gap_number,
                              min_gap_ever, min_gap_number},
          "numbers": [{number, appearance_count, count, gaps, avg_gap,
                       median_gap, min_gap, max_gap, std_gap, gap_histogram},
                      ...] (45개, index 0 = 번호 1),
          "disclaimer": "..."
        }
    """
    # 프로세스 수명 캐시 — top_n 파라미터가 없으므로 키는 회차 수만 사용한다.
    cache_key = str(0 if not draws else len(draws))
    cached: dict[str, Any] | None = _gap_dist_cache.get(cache_key)
    if cached is not None:
        return cached

    # REQ-GAP-005: None/빈 데이터 가드 — 45개 None/0 채움 항목을 반환한다.
    if not draws:
        empty_result = {
            "total_draws": 0,
            "overall_summary": _empty_gap_overall_summary(),
            "numbers": [
                _build_gap_number_item(n, [], 0)
                for n in range(1, _GAP_NUMBER_MAX + 1)
            ],
            "disclaimer": _GAP_DIST_DISCLAIMER,
        }
        _gap_dist_cache[cache_key] = empty_result
        return empty_result

    # REQ-GAP-001: drwNo 오름차순 정렬로 간격(차이)의 부호를 보장한다.
    sorted_draws = sorted(draws, key=lambda d: d.drwNo)
    total_draws = len(sorted_draws)

    # 번호별 출현 drwNo를 단일 패스로 수집한다. numbers()는 메서드(본번호 6개).
    occ: dict[int, list[int]] = {n: [] for n in range(1, _GAP_NUMBER_MAX + 1)}
    for draw in sorted_draws:
        for n in draw.numbers():
            occ[n].append(draw.drwNo)

    # REQ-GAP-001/002/004: 번호별 항목 생성 + 전체 간격(번호 소유주 포함) 누적.
    # 번호 1→45 순으로 누적하므로 동률 간격은 더 작은 번호가 먼저 등장한다.
    numbers: list[dict[str, Any]] = []
    all_gaps_with_owner: list[tuple[int, int]] = []
    for n in range(1, _GAP_NUMBER_MAX + 1):
        drwnos = occ[n]
        gaps = [drwnos[i + 1] - drwnos[i] for i in range(len(drwnos) - 1)]
        numbers.append(_build_gap_number_item(n, gaps, len(drwnos)))
        for gap in gaps:
            all_gaps_with_owner.append((gap, n))

    result = {
        "total_draws": total_draws,
        "overall_summary": _gap_overall_summary(all_gaps_with_owner),
        "numbers": numbers,
        "disclaimer": _GAP_DIST_DISCLAIMER,
    }
    _gap_dist_cache[cache_key] = result
    return result


def get_historic_match(
    numbers: list,
    draws: list | None,
) -> dict | None:
    """SPEC-LOTTO-114: 입력 번호의 역대 당첨 일치 이력 조회.

    # @MX:ANCHOR: [AUTO] 역대 일치 이력 조회 진입점
    # @MX:REASON: pages.py, api.py에서 호출 (fan_in >= 2)
    # @MX:SPEC: SPEC-LOTTO-114 REQ-HM-001~005
    """
    if draws is None or len(draws) < 1 or len(numbers) != 6:
        return None

    nums_set = set(numbers)
    results = []
    rank_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    main_match_dist = dict.fromkeys(range(7), 0)  # 0..6

    for d in draws:
        main = set(d.numbers())
        main_match = len(nums_set & main)
        bonus_match = (d.bonus in nums_set) and (d.bonus not in main)

        if main_match == 6:
            rank = 1
        elif main_match == 5 and bonus_match:
            rank = 2
        elif main_match == 5:
            rank = 3
        elif main_match == 4:
            rank = 4
        elif main_match == 3:
            rank = 5
        else:
            rank = 0

        rank_counts[rank] = rank_counts.get(rank, 0) + 1
        main_match_dist[main_match] = main_match_dist.get(main_match, 0) + 1

        if main_match >= 2:
            results.append({
                "drwNo": d.drwNo,
                "date": d.date.isoformat(),
                "main_numbers": list(d.numbers()),
                "bonus": d.bonus,
                "main_match": main_match,
                "bonus_match": bonus_match,
                "rank": rank,
            })

    results.sort(key=lambda x: (x["main_match"], x["drwNo"]), reverse=True)

    return {
        "input_numbers": sorted(numbers),
        "total_draws": len(draws),
        "rank_counts": rank_counts,
        "main_match_dist": main_match_dist,
        "results": results[:200],
        "results_total": len(results),
    }


def get_number_heatmap() -> list[dict[str, Any]] | None:
    """1~45 번호별 통합 점수를 반환합니다.

    각 번호에 대해 다음 4가지 지표를 [0, 1] 정규화 후 평균:
    - freq_score: 전체 출현 빈도
    - recent_score: 최근 20회차 출현 빈도
    - gap_score: 출현 비율 (빈도/총회차)
    - pair_score: 동반 쌍 점수 합계
    """
    draws = get_draws()
    if not draws:
        return None

    import warnings  # noqa: PLC0415

    from lotto.analyzer import LottoAnalyzer  # noqa: PLC0415

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stats = LottoAnalyzer().analyze(draws)

    # 원시 점수 수집
    freq_raw: dict[int, float] = {
        n: float(stats.frequency.absolute.get(n, 0)) for n in range(1, 46)
    }
    recent_raw: dict[int, float] = {
        n: float(stats.recent_pattern.counts.get(n, 0)) for n in range(1, 46)
    }

    # gap_score: 출현 비율 = count / total_draws
    total = len(draws)
    gap_raw: dict[int, float] = {n: freq_raw[n] / total for n in range(1, 46)}

    # pair_score: 해당 번호가 포함된 상위 쌍의 count 합산
    pair_raw: dict[int, float] = dict.fromkeys(range(1, 46), 0.0)
    for a, b, count in stats.pair_analysis.top_pairs:
        pair_raw[a] = pair_raw.get(a, 0.0) + count
        pair_raw[b] = pair_raw.get(b, 0.0) + count

    def _normalize(d: dict[int, float]) -> dict[int, float]:
        lo = min(d.values())
        hi = max(d.values())
        if hi == lo:
            return dict.fromkeys(d, 0.5)
        return {k: (v - lo) / (hi - lo) for k, v in d.items()}

    freq_n = _normalize(freq_raw)
    recent_n = _normalize(recent_raw)
    gap_n = _normalize(gap_raw)
    pair_n = _normalize(pair_raw)

    result = []
    for n in range(1, 46):
        f = freq_n[n]
        r = recent_n[n]
        g = gap_n[n]
        p = pair_n[n]
        result.append(
            {
                "number": n,
                "freq_score": round(f, 4),
                "recent_score": round(r, 4),
                "gap_score": round(g, 4),
                "pair_score": round(p, 4),
                "composite": round((f + r + g + p) / 4, 4),
            }
        )
    return result


def get_carryover_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-118: 이월 번호 분석.

    전 회차 당첨 번호 중 다음 회차에도 등장한 번호(이월 번호) 수의 분포를 반환.
    """
    draws = get_draws()
    if len(draws) < 2:
        return None

    # 연속 회차 쌍에서 이월 번호 수 계산
    carryover_counts: list[int] = []
    for i in range(1, len(draws)):
        prev_nums = set(draws[i - 1].numbers())
        curr_nums = set(draws[i].numbers())
        overlap = len(prev_nums & curr_nums)
        carryover_counts.append(overlap)

    total = len(carryover_counts)
    # 분포: 0개~6개
    dist: dict[int, int] = {k: 0 for k in range(7)}
    for c in carryover_counts:
        dist[c] += 1

    avg = sum(carryover_counts) / total if total > 0 else 0.0

    # 최근 20회차 이월 번호 (draw_no, count 쌍) — 최신순
    recent_pairs = []
    for i in range(max(1, len(draws) - 20), len(draws)):
        prev_nums = set(draws[i - 1].numbers())
        curr_nums = set(draws[i].numbers())
        overlap_nums = sorted(prev_nums & curr_nums)
        recent_pairs.append({
            "drwNo": draws[i].drwNo,
            "count": len(overlap_nums),
            "numbers": overlap_nums,
        })
    recent_pairs.reverse()  # 최신순

    return {
        "total_pairs": total,
        "distribution": dist,
        "avg_carryover": round(avg, 3),
        "most_common": max(dist, key=lambda k: dist[k]),
        "recent": recent_pairs,
    }


def get_combo_guide() -> dict[str, Any] | None:
    """SPEC-LOTTO-119: 번호 조합 가이드.

    실제 당첨 데이터 기반으로 최적 조합 패턴(홀짝·합계·AC값·구간·연속번호) 통계를 반환.
    """
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    # 1. 홀짝 비율 분포 (홀수 개수 기준)
    odd_dist: dict[int, int] = {k: 0 for k in range(7)}
    for draw in draws:
        odd_count = sum(1 for n in draw.numbers() if n % 2 == 1)
        odd_dist[odd_count] += 1

    # 2. 합계 분포 (20단위 구간)
    # 6개 번호의 합계: 최소 21(1+2+3+4+5+6), 최대 255(40+41+42+43+44+45)
    # 구간: <80, 80-99, 100-119, 120-139, 140-159, 160-179, 180-199, >=200
    sum_bins = [80, 100, 120, 140, 160, 180, 200]
    sum_labels = ["~79", "80~99", "100~119", "120~139", "140~159", "160~179", "180~199", "200~"]
    sum_dist: list[int] = [0] * len(sum_labels)
    for draw in draws:
        s = sum(draw.numbers())
        bucket = len(sum_bins)  # 기본값: 마지막 버킷
        for i, boundary in enumerate(sum_bins):
            if s < boundary:
                bucket = i
                break
        sum_dist[bucket] += 1

    # 3. 연속 번호 포함 여부 분포 (연속 쌍 개수)
    consec_dist: dict[int, int] = {k: 0 for k in range(6)}
    for draw in draws:
        nums = sorted(draw.numbers())
        pairs = sum(1 for i in range(len(nums) - 1) if nums[i + 1] == nums[i] + 1)
        consec_dist[min(pairs, 5)] += 1

    # 4. 구간(십의 자리) 분포 — 1~9, 10~19, 20~29, 30~39, 40~45 중 몇 개 구간이 커버되는가
    zone_dist: dict[int, int] = {k: 0 for k in range(1, 6)}
    for draw in draws:
        zones = set()
        for n in draw.numbers():
            if n <= 9:
                zones.add(1)
            elif n <= 19:
                zones.add(2)
            elif n <= 29:
                zones.add(3)
            elif n <= 39:
                zones.add(4)
            else:
                zones.add(5)
        zone_dist[len(zones)] = zone_dist.get(len(zones), 0) + 1

    # 5. 고저 비율 분포 (22 이하 = 저, 23 이상 = 고)
    low_dist: dict[int, int] = {k: 0 for k in range(7)}
    for draw in draws:
        low_count = sum(1 for n in draw.numbers() if n <= 22)
        low_dist[low_count] += 1

    def most_common_key(d: dict) -> int:  # type: ignore[type-arg]
        return max(d, key=lambda k: d[k])

    def top_pct(d: dict, k: object) -> float:  # type: ignore[type-arg]
        return round(d[k] / total * 100, 1)

    # 구간별 최빈 버킷
    best_sum_idx = sum_dist.index(max(sum_dist))

    return {
        "total": total,
        "odd_dist": odd_dist,
        "best_odd": most_common_key(odd_dist),
        "best_odd_pct": top_pct(odd_dist, most_common_key(odd_dist)),
        "sum_labels": sum_labels,
        "sum_dist": sum_dist,
        "best_sum_label": sum_labels[best_sum_idx],
        "best_sum_pct": round(sum_dist[best_sum_idx] / total * 100, 1),
        "consec_dist": consec_dist,
        "best_consec": most_common_key(consec_dist),
        "best_consec_pct": top_pct(consec_dist, most_common_key(consec_dist)),
        "zone_dist": zone_dist,
        "best_zone": most_common_key(zone_dist),
        "best_zone_pct": top_pct(zone_dist, most_common_key(zone_dist)),
        "low_dist": low_dist,
        "best_low": most_common_key(low_dist),
        "best_low_pct": top_pct(low_dist, most_common_key(low_dist)),
    }


def get_seasonal_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-120: 계절별 번호 출현 분석.

    봄(3~5월)/여름(6~8월)/가을(9~11월)/겨울(12~2월)별 번호 빈도를 분석.
    """
    draws = get_draws()
    if not draws:
        return None

    seasons = {
        "봄": (3, 4, 5),
        "여름": (6, 7, 8),
        "가을": (9, 10, 11),
        "겨울": (12, 1, 2),
    }
    season_order = ["봄", "여름", "가을", "겨울"]

    # 계절별 번호 카운트와 회차 수
    season_counts: dict[str, dict[int, int]] = {
        s: {n: 0 for n in range(1, 46)} for s in season_order
    }
    season_draws: dict[str, int] = {s: 0 for s in season_order}

    for draw in draws:
        month = draw.date.month
        for season, months in seasons.items():
            if month in months:
                season_draws[season] += 1
                for n in draw.numbers():
                    season_counts[season][n] += 1
                break

    result: dict[str, Any] = {
        "season_order": season_order,
        "season_draws": season_draws,
        "seasons": {},
    }

    for season in season_order:
        draws_in_season = season_draws[season]
        if draws_in_season == 0:
            result["seasons"][season] = {
                "draws": 0,
                "top10": [],
                "counts": {},
            }
            continue

        counts = season_counts[season]
        sorted_nums = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        top10 = [
            {
                "number": n,
                "count": c,
                "rate": round(c / draws_in_season * 100, 1),
            }
            for n, c in sorted_nums[:10]
        ]
        result["seasons"][season] = {
            "draws": draws_in_season,
            "top10": top10,
            "counts": {str(n): c for n, c in counts.items()},
        }

    return result


# ---------------------------------------------------------------------------
# SPEC-LOTTO-121: AC값(산술 복잡도) 분포 분석
# ---------------------------------------------------------------------------

def _calc_ac(numbers: list[int]) -> int:
    """AC값(산술 복잡도) 계산: 6개 번호의 서로 다른 차이값 수 - 5."""
    nums = sorted(numbers)
    diffs: set[int] = set()
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            diffs.add(nums[j] - nums[i])
    return len(diffs) - 5


def get_ac_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-121: AC값(산술 복잡도) 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)
    ac_values = [_calc_ac(draw.numbers()) for draw in draws]

    # 분포: AC 0~10
    dist: dict[int, int] = dict.fromkeys(range(11), 0)
    for ac in ac_values:
        dist[min(ac, 10)] += 1

    best_ac = max(dist, key=lambda k: dist[k])
    avg_ac = round(sum(ac_values) / total, 3)

    # 최근 20회차 AC값
    recent = []
    for draw in draws[-20:][::-1]:
        ac = _calc_ac(draw.numbers())
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "ac": ac,
        })

    return {
        "total": total,
        "distribution": dist,
        "best_ac": best_ac,
        "best_ac_pct": round(dist[best_ac] / total * 100, 1),
        "avg_ac": avg_ac,
        "recent": recent,
    }


# ---------------------------------------------------------------------------
# SPEC-LOTTO-122: 번호 끝자리(일의 자리) 분포 분석
# ---------------------------------------------------------------------------

def get_tail_digit_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-122: 번호 끝자리(일의 자리) 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)
    total_numbers = total * 6  # 전체 번호 출현 수

    # 1. 끝자리별 전체 출현 빈도
    tail_freq: dict[int, int] = {d: 0 for d in range(10)}
    for draw in draws:
        for n in draw.numbers():
            tail_freq[n % 10] += 1

    best_tail = max(tail_freq, key=lambda k: tail_freq[k])

    # 끝자리별 기대 빈도 (번호 수 비례)
    # 1~45에서 끝자리별 번호 수: 0→4개, 1~5→5개, 6~9→4개
    tail_pool: dict[int, int] = {d: 0 for d in range(10)}
    for n in range(1, 46):
        tail_pool[n % 10] += 1

    # 2. 회차별 끝자리 커버 수 분포 (몇 가지 끝자리를 커버하는가)
    cover_dist: dict[int, int] = {k: 0 for k in range(1, 7)}
    for draw in draws:
        tails = {n % 10 for n in draw.numbers()}
        cover_dist[len(tails)] += 1

    best_cover = max(cover_dist, key=lambda k: cover_dist[k])

    tail_data = []
    for d in range(10):
        count = tail_freq[d]
        pool = tail_pool[d]
        expected = total_numbers * (pool / 45)
        tail_data.append({
            "digit": d,
            "count": count,
            "rate": round(count / total_numbers * 100, 2),
            "pool": pool,
            "expected": round(expected, 1),
            "ratio": round(count / expected, 3) if expected > 0 else 0,
        })

    return {
        "total": total,
        "total_numbers": total_numbers,
        "tail_data": tail_data,
        "best_tail": best_tail,
        "best_tail_pct": round(tail_freq[best_tail] / total_numbers * 100, 1),
        "cover_dist": cover_dist,
        "best_cover": best_cover,
        "best_cover_pct": round(cover_dist[best_cover] / total * 100, 1),
    }


def get_number_gap_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-123: 번호 간격(Gap) 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    # 분포 딕셔너리 초기화
    min_gap_dist: dict[int, int] = {}
    max_gap_dist: dict[int, int] = {}
    consec_dist: dict[int, int] = {k: 0 for k in range(6)}  # 연속쌍 수 0~5
    avg_gaps: list[float] = []

    for draw in draws:
        nums = sorted(draw.numbers())
        gaps = [nums[i + 1] - nums[i] for i in range(5)]

        min_g = min(gaps)
        max_g = max(gaps)
        consec = sum(1 for g in gaps if g == 1)
        avg_gap = (nums[-1] - nums[0]) / 5

        min_gap_dist[min_g] = min_gap_dist.get(min_g, 0) + 1
        max_gap_dist[max_g] = max_gap_dist.get(max_g, 0) + 1
        consec_dist[consec] += 1
        avg_gaps.append(avg_gap)

    overall_avg = round(sum(avg_gaps) / total, 3)
    best_min_gap = max(min_gap_dist, key=lambda k: min_gap_dist[k])
    best_max_gap = max(max_gap_dist, key=lambda k: max_gap_dist[k])
    best_consec = max(consec_dist, key=lambda k: consec_dist[k])

    # min/max gap 분포를 정렬된 리스트로 변환
    min_gap_list = [
        {"gap": k, "count": min_gap_dist[k], "pct": round(min_gap_dist[k] / total * 100, 1)}
        for k in sorted(min_gap_dist)
    ]
    max_gap_list = [
        {"gap": k, "count": max_gap_dist[k], "pct": round(max_gap_dist[k] / total * 100, 1)}
        for k in sorted(max_gap_dist)
    ]

    return {
        "total": total,
        "avg_gap": overall_avg,
        "best_min_gap": best_min_gap,
        "best_min_gap_pct": round(min_gap_dist[best_min_gap] / total * 100, 1),
        "best_max_gap": best_max_gap,
        "best_max_gap_pct": round(max_gap_dist[best_max_gap] / total * 100, 1),
        "best_consec": best_consec,
        "best_consec_pct": round(consec_dist[best_consec] / total * 100, 1),
        "min_gap_list": min_gap_list,
        "max_gap_list": max_gap_list,
        "consec_dist": consec_dist,
    }


# SPEC-LOTTO-124: 1~45 중 소수 집합
PRIMES_1_45: set[int] = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43}


def get_prime_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-124: 소수 번호 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)
    total_numbers = total * 6

    # 회차별 소수 개수 분포 (0~6)
    prime_count_dist: dict[int, int] = {k: 0 for k in range(7)}
    # 개별 소수 출현 빈도
    prime_freq: dict[int, int] = {p: 0 for p in sorted(PRIMES_1_45)}
    prime_total = 0

    for draw in draws:
        nums = draw.numbers()
        primes_in_draw = [n for n in nums if n in PRIMES_1_45]
        cnt = len(primes_in_draw)
        prime_count_dist[cnt] += 1
        prime_total += cnt
        for n in primes_in_draw:
            prime_freq[n] += 1

    best_count = max(prime_count_dist, key=lambda k: prime_count_dist[k])
    prime_rate = round(prime_total / total_numbers * 100, 2)
    # 기대값: 14/45 ≈ 31.11%
    expected_rate = round(14 / 45 * 100, 2)

    prime_list = [
        {
            "number": p,
            "count": prime_freq[p],
            "rate": round(prime_freq[p] / total * 100, 2),
        }
        for p in sorted(PRIMES_1_45)
    ]

    return {
        "total": total,
        "prime_count_dist": prime_count_dist,
        "best_count": best_count,
        "best_count_pct": round(prime_count_dist[best_count] / total * 100, 1),
        "prime_rate": prime_rate,
        "expected_rate": expected_rate,
        "prime_total": prime_total,
        "prime_list": prime_list,
        "num_primes_in_range": len(PRIMES_1_45),
    }


def get_std_deviation_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-125: 번호 표준편차 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    def calc_std(nums: list[int]) -> float:
        mean = sum(nums) / len(nums)
        variance = sum((n - mean) ** 2 for n in nums) / len(nums)
        return round(math.sqrt(variance), 2)

    std_values: list[float] = [calc_std(draw.numbers()) for draw in draws]

    # 구간 분류: [0,5), [5,8), [8,11), [11,14), [14,17), [17,∞)
    buckets = [
        {"label": "0~4", "min": 0, "max": 5, "count": 0},
        {"label": "5~7", "min": 5, "max": 8, "count": 0},
        {"label": "8~10", "min": 8, "max": 11, "count": 0},
        {"label": "11~13", "min": 11, "max": 14, "count": 0},
        {"label": "14~16", "min": 14, "max": 17, "count": 0},
        {"label": "17+", "min": 17, "max": float("inf"), "count": 0},
    ]
    for s in std_values:
        for b in buckets:
            if b["min"] <= s < b["max"]:
                b["count"] += 1
                break

    avg_std = round(sum(std_values) / total, 2)
    min_std = min(std_values)
    max_std = max(std_values)
    min_draw = draws[std_values.index(min_std)]
    max_draw = draws[std_values.index(max_std)]

    best_bucket = max(buckets, key=lambda b: b["count"])

    # 최근 20회차
    recent = []
    for draw, s in zip(draws[-20:][::-1], reversed(std_values[-20:])):
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "std": s,
        })

    bucket_list = [
        {
            "label": b["label"],
            "count": b["count"],
            "pct": round(b["count"] / total * 100, 1),
        }
        for b in buckets
    ]

    return {
        "total": total,
        "avg_std": avg_std,
        "min_std": min_std,
        "min_draw": {"drwNo": min_draw.drwNo, "numbers": sorted(min_draw.numbers())},
        "max_std": max_std,
        "max_draw": {"drwNo": max_draw.drwNo, "numbers": sorted(max_draw.numbers())},
        "best_bucket_label": best_bucket["label"],
        "best_bucket_pct": round(best_bucket["count"] / total * 100, 1),
        "bucket_list": bucket_list,
        "recent": recent,
    }


def get_range_combo_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-126: 번호 구간 조합(저/중/고) 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    combo_dist: dict[str, int] = {}
    low_dist: dict[int, int] = dict.fromkeys(range(7), 0)
    mid_dist: dict[int, int] = dict.fromkeys(range(7), 0)
    high_dist: dict[int, int] = dict.fromkeys(range(7), 0)

    for draw in draws:
        nums = draw.numbers()
        low = sum(1 for n in nums if 1 <= n <= 15)
        mid = sum(1 for n in nums if 16 <= n <= 30)
        high = sum(1 for n in nums if 31 <= n <= 45)
        key = f"{low}-{mid}-{high}"
        combo_dist[key] = combo_dist.get(key, 0) + 1
        low_dist[low] += 1
        mid_dist[mid] += 1
        high_dist[high] += 1

    best_combo = max(combo_dist, key=lambda k: combo_dist[k])

    # 상위 15개 조합만 반환 (빈도 순)
    top_combos = sorted(
        [{"combo": k, "count": v, "pct": round(v / total * 100, 1)} for k, v in combo_dist.items()],
        key=lambda x: -x["count"],
    )[:15]

    def _zone_list(dist: dict[int, int]) -> list[dict[str, Any]]:
        return [
            {"count": k, "freq": dist[k], "pct": round(dist[k] / total * 100, 1)}
            for k in range(7)
        ]

    zone_data = {
        "low": _zone_list(low_dist),
        "mid": _zone_list(mid_dist),
        "high": _zone_list(high_dist),
    }

    return {
        "total": total,
        "best_combo": best_combo,
        "best_combo_count": combo_dist[best_combo],
        "best_combo_pct": round(combo_dist[best_combo] / total * 100, 1),
        "total_combos": len(combo_dist),
        "top_combos": top_combos,
        "zone_data": zone_data,
    }


# SPEC-LOTTO-127: 배수 분석용 상수
MULTIPLES_3 = {n for n in range(1, 46) if n % 3 == 0}   # 15개
MULTIPLES_5 = {n for n in range(1, 46) if n % 5 == 0}   # 9개
MULTIPLES_7 = {n for n in range(1, 46) if n % 7 == 0}   # 6개


def get_multiples_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-127: 배수 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    def analyze_multiples(multiples: set[int]) -> dict[str, Any]:
        count_dist: dict[int, int] = {k: 0 for k in range(7)}
        freq: dict[int, int] = {n: 0 for n in sorted(multiples)}
        total_appear = 0

        for draw in draws:
            nums = draw.numbers()
            in_draw = [n for n in nums if n in multiples]
            count_dist[len(in_draw)] += 1
            total_appear += len(in_draw)
            for n in in_draw:
                freq[n] += 1

        best_count = max(count_dist, key=lambda k: count_dist[k])
        rate = round(total_appear / (total * 6) * 100, 2)
        expected = round(len(multiples) / 45 * 100, 2)

        dist_list = [
            {"count": k, "freq": count_dist[k], "pct": round(count_dist[k] / total * 100, 1)}
            for k in range(7)
        ]
        freq_list = [
            {"number": n, "count": freq[n], "rate": round(freq[n] / total * 100, 2)}
            for n in sorted(multiples)
        ]

        return {
            "size": len(multiples),
            "best_count": best_count,
            "best_count_pct": round(count_dist[best_count] / total * 100, 1),
            "rate": rate,
            "expected": expected,
            "dist_list": dist_list,
            "freq_list": freq_list,
        }

    return {
        "total": total,
        "mult3": analyze_multiples(MULTIPLES_3),
        "mult5": analyze_multiples(MULTIPLES_5),
        "mult7": analyze_multiples(MULTIPLES_7),
    }


def get_hot_cold_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-128: 핫/콜드 번호 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)
    recent_50 = draws[-50:] if total >= 50 else draws
    recent_10 = draws[-10:] if total >= 10 else draws

    # all_count
    all_count: dict[int, int] = {n: 0 for n in range(1, 46)}
    for draw in draws:
        for n in draw.numbers():
            all_count[n] += 1

    # r50_count
    r50_count: dict[int, int] = {n: 0 for n in range(1, 46)}
    for draw in recent_50:
        for n in draw.numbers():
            r50_count[n] += 1

    # r10_count
    r10_count: dict[int, int] = {n: 0 for n in range(1, 46)}
    for draw in recent_10:
        for n in draw.numbers():
            r10_count[n] += 1

    # last_seen: find how many draws ago the number last appeared
    last_seen_ago: dict[int, int] = {}
    for n in range(1, 46):
        for i, draw in enumerate(reversed(draws)):
            if n in draw.numbers():
                last_seen_ago[n] = i  # 0 = last draw
                break
        else:
            last_seen_ago[n] = total  # never appeared

    numbers = []
    for n in range(1, 46):
        r10 = r10_count[n]
        status = "hot" if r10 >= 3 else ("cold" if r10 == 0 else "warm")
        numbers.append({
            "number": n,
            "all_count": all_count[n],
            "all_rate": round(all_count[n] / total * 100, 1),
            "r50_count": r50_count[n],
            "r50_rate": round(r50_count[n] / len(recent_50) * 100, 1),
            "r10_count": r10_count[n],
            "r10_rate": round(r10_count[n] / len(recent_10) * 100, 1),
            "last_seen_ago": last_seen_ago[n],
            "status": status,
        })

    hot_numbers = sorted([x for x in numbers if x["status"] == "hot"], key=lambda x: -x["r10_count"])
    cold_numbers = sorted([x for x in numbers if x["status"] == "cold"], key=lambda x: -x["last_seen_ago"])

    return {
        "total": total,
        "recent_50_size": len(recent_50),
        "recent_10_size": len(recent_10),
        "numbers": numbers,
        "hot_count": len(hot_numbers),
        "cold_count": len(cold_numbers),
        "top_hot": hot_numbers[:10],
        "top_cold": cold_numbers[:10],
        "expected_rate": round(6 / 45 * 100, 2),
    }


def get_number_range_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-130: 번호 범위(최대-최소) 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    ranges = [max(draw.numbers()) - min(draw.numbers()) for draw in draws]

    buckets = [
        {"label": "5~14", "min": 5, "max": 15, "count": 0},
        {"label": "15~19", "min": 15, "max": 20, "count": 0},
        {"label": "20~24", "min": 20, "max": 25, "count": 0},
        {"label": "25~29", "min": 25, "max": 30, "count": 0},
        {"label": "30~34", "min": 30, "max": 35, "count": 0},
        {"label": "35~39", "min": 35, "max": 40, "count": 0},
        {"label": "40~44", "min": 40, "max": 45, "count": 0},
    ]

    for r in ranges:
        for b in buckets:
            if b["min"] <= r < b["max"]:
                b["count"] += 1
                break

    avg_range = round(sum(ranges) / total, 2)
    min_range = min(ranges)
    max_range = max(ranges)
    min_draw = draws[ranges.index(min_range)]
    max_draw = draws[ranges.index(max_range)]

    best_bucket = max(buckets, key=lambda b: b["count"])

    # Min/Max number frequency
    min_freq: dict[int, int] = {n: 0 for n in range(1, 46)}
    max_freq: dict[int, int] = {n: 0 for n in range(1, 46)}
    for draw in draws:
        nums = draw.numbers()
        min_freq[min(nums)] += 1
        max_freq[max(nums)] += 1

    top_min = sorted(
        [{"number": n, "count": min_freq[n]} for n in range(1, 46) if min_freq[n] > 0],
        key=lambda x: -x["count"],
    )[:10]
    top_max = sorted(
        [{"number": n, "count": max_freq[n]} for n in range(1, 46) if max_freq[n] > 0],
        key=lambda x: -x["count"],
    )[:10]

    bucket_list = [
        {
            "label": b["label"],
            "count": b["count"],
            "pct": round(b["count"] / total * 100, 1),
        }
        for b in buckets
    ]

    recent = []
    for draw, r in zip(reversed(draws[-20:]), reversed(ranges[-20:])):
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "range": r,
        })

    return {
        "total": total,
        "avg_range": avg_range,
        "min_range": min_range,
        "max_range": max_range,
        "min_draw": {"drwNo": min_draw.drwNo, "numbers": sorted(min_draw.numbers())},
        "max_draw": {"drwNo": max_draw.drwNo, "numbers": sorted(max_draw.numbers())},
        "best_bucket_label": best_bucket["label"],
        "best_bucket_pct": round(best_bucket["count"] / total * 100, 1),
        "bucket_list": bucket_list,
        "top_min": top_min,
        "top_max": top_max,
        "recent": recent,
    }


def get_sum_last_digit_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-131: 번호 합계 끝자리 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    digit_dist: dict[int, int] = {d: 0 for d in range(10)}
    sums: list[int] = []

    for draw in draws:
        s = sum(draw.numbers())
        sums.append(s)
        digit_dist[s % 10] += 1

    avg_sum = round(sum(sums) / total, 2)
    best_digit = max(digit_dist, key=lambda d: digit_dist[d])
    worst_digit = min(digit_dist, key=lambda d: digit_dist[d])

    odd_count = sum(digit_dist[d] for d in [1, 3, 5, 7, 9])
    even_count = sum(digit_dist[d] for d in [0, 2, 4, 6, 8])

    digit_list = [
        {
            "digit": d,
            "count": digit_dist[d],
            "pct": round(digit_dist[d] / total * 100, 1),
        }
        for d in range(10)
    ]

    recent = []
    for draw, s in zip(reversed(draws[-20:]), reversed(sums[-20:])):
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "sum": s,
            "last_digit": s % 10,
        })

    return {
        "total": total,
        "avg_sum": avg_sum,
        "best_digit": best_digit,
        "best_digit_count": digit_dist[best_digit],
        "best_digit_pct": round(digit_dist[best_digit] / total * 100, 1),
        "worst_digit": worst_digit,
        "worst_digit_count": digit_dist[worst_digit],
        "worst_digit_pct": round(digit_dist[worst_digit] / total * 100, 1),
        "odd_count": odd_count,
        "odd_pct": round(odd_count / total * 100, 1),
        "even_count": even_count,
        "even_pct": round(even_count / total * 100, 1),
        "expected_pct": 10.0,
        "digit_list": digit_list,
        "recent": recent,
    }


def get_consecutive_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-132: 연속 번호 패턴 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    def find_consecutive_runs(nums: list[int]) -> list[list[int]]:
        s = sorted(nums)
        runs: list[list[int]] = []
        current = [s[0]]
        for n in s[1:]:
            if n == current[-1] + 1:
                current.append(n)
            else:
                if len(current) >= 2:
                    runs.append(current)
                current = [n]
        if len(current) >= 2:
            runs.append(current)
        return runs

    # 회차별 연속 쌍 수 분포
    pair_count_dist: dict[int, int] = {}
    max_run_dist: dict[int, int] = {k: 0 for k in range(1, 7)}
    pair_freq: dict[tuple[int, int], int] = {}

    for draw in draws:
        runs = find_consecutive_runs(draw.numbers())
        pairs = sum(len(r) - 1 for r in runs)
        pair_count_dist[pairs] = pair_count_dist.get(pairs, 0) + 1

        max_run = max((len(r) for r in runs), default=1)
        max_run_dist[max_run] = max_run_dist.get(max_run, 0) + 1

        for run in runs:
            for i in range(len(run) - 1):
                pair = (run[i], run[i + 1])
                pair_freq[pair] = pair_freq.get(pair, 0) + 1

    no_consec = pair_count_dist.get(0, 0)
    has_consec = total - no_consec
    best_pair_count = max(pair_count_dist, key=lambda k: pair_count_dist[k])

    pair_dist_list = sorted(
        [{"pairs": k, "count": v, "pct": round(v / total * 100, 1)}
         for k, v in pair_count_dist.items()],
        key=lambda x: x["pairs"],
    )

    max_run_list = [
        {"length": k, "count": max_run_dist[k], "pct": round(max_run_dist[k] / total * 100, 1)}
        for k in range(1, 7)
        if max_run_dist.get(k, 0) > 0
    ]

    top_pairs = sorted(
        [{"pair": list(p), "count": c} for p, c in pair_freq.items()],
        key=lambda x: -x["count"],
    )[:20]

    recent = []
    for draw in reversed(draws[-20:]):
        runs = find_consecutive_runs(draw.numbers())
        runs_str = ["-".join(str(n) for n in r) for r in runs]
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "runs": runs_str,
            "pair_count": sum(len(r) - 1 for r in runs),
        })

    return {
        "total": total,
        "no_consec": no_consec,
        "no_consec_pct": round(no_consec / total * 100, 1),
        "has_consec": has_consec,
        "has_consec_pct": round(has_consec / total * 100, 1),
        "best_pair_count": best_pair_count,
        "best_pair_count_pct": round(pair_count_dist[best_pair_count] / total * 100, 1),
        "pair_dist_list": pair_dist_list,
        "max_run_list": max_run_list,
        "top_pairs": top_pairs,
        "recent": recent,
    }


def get_pair_frequency_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-133: 번호 쌍(pair) 동시 출현 빈도 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    pair_count: dict[tuple[int, int], int] = {}

    for draw in draws:
        nums = sorted(draw.numbers())
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pair = (nums[i], nums[j])
                pair_count[pair] = pair_count.get(pair, 0) + 1

    expected = round(total * 15 / 990, 2)

    sorted_pairs = sorted(pair_count.items(), key=lambda x: -x[1])

    top_pairs = [
        {"pair": list(p), "count": c, "pct": round(c / total * 100, 2)}
        for p, c in sorted_pairs[:20]
    ]
    rare_pairs = [
        {"pair": list(p), "count": c, "pct": round(c / total * 100, 2)}
        for p, c in sorted_pairs[-20:][::-1]
        if c > 0
    ]

    # 번호별 주요 파트너 TOP 5
    partner_freq: dict[int, dict[int, int]] = {n: {} for n in range(1, 46)}
    for (a, b), c in pair_count.items():
        partner_freq[a][b] = c
        partner_freq[b][a] = c

    top_partners: dict[int, list[dict[str, int]]] = {}
    for n in range(1, 46):
        partners = sorted(partner_freq[n].items(), key=lambda x: -x[1])[:5]
        top_partners[n] = [{"number": p, "count": c} for p, c in partners]

    total_unique_pairs = len(pair_count)
    never_appeared = 990 - total_unique_pairs

    return {
        "total": total,
        "expected": expected,
        "total_unique_pairs": total_unique_pairs,
        "never_appeared": never_appeared,
        "top_pairs": top_pairs,
        "rare_pairs": rare_pairs,
        "top_partners": top_partners,
    }


def get_shared_numbers_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-134: 연속 회차 공유 번호 분석."""
    draws = get_draws()
    if not draws or len(draws) < 2:
        return None

    total = len(draws)
    pairs = total - 1  # number of consecutive pairs

    shared_dist: dict[int, int] = dict.fromkeys(range(7), 0)
    shared_counts: list[int] = []

    max_shared = 0
    min_shared = 6
    max_shared_pair: tuple[int, int] = (0, 0)
    min_shared_pair: tuple[int, int] = (0, 0)

    for i in range(pairs):
        a = set(draws[i].numbers())
        b = set(draws[i + 1].numbers())
        shared = len(a & b)
        shared_counts.append(shared)
        shared_dist[shared] += 1

        if shared > max_shared:
            max_shared = shared
            max_shared_pair = (draws[i].drwNo, draws[i + 1].drwNo)
        if shared < min_shared:
            min_shared = shared
            min_shared_pair = (draws[i].drwNo, draws[i + 1].drwNo)

    avg_shared = round(sum(shared_counts) / pairs, 3)

    dist_list = [
        {
            "shared": k,
            "count": shared_dist[k],
            "pct": round(shared_dist[k] / pairs * 100, 1),
        }
        for k in range(7)
    ]

    best_shared = max(shared_dist, key=lambda k: shared_dist[k])

    # recent 20 consecutive pairs
    recent = []
    start = max(0, pairs - 20)
    for i in range(start, pairs):
        a_nums = sorted(draws[i].numbers())
        b_nums = sorted(draws[i + 1].numbers())
        shared_nums = sorted(set(a_nums) & set(b_nums))
        recent.append({
            "draw_a": draws[i].drwNo,
            "draw_b": draws[i + 1].drwNo,
            "nums_a": a_nums,
            "nums_b": b_nums,
            "shared_nums": shared_nums,
            "shared_count": len(shared_nums),
        })
    recent = list(reversed(recent))

    return {
        "total": total,
        "pairs": pairs,
        "avg_shared": avg_shared,
        "max_shared": max_shared,
        "max_shared_pair": list(max_shared_pair),
        "min_shared": min_shared,
        "min_shared_pair": list(min_shared_pair),
        "best_shared": best_shared,
        "best_shared_pct": round(shared_dist[best_shared] / pairs * 100, 1),
        "no_shared_pct": round(shared_dist[0] / pairs * 100, 1),
        "dist_list": dist_list,
        "recent": recent,
    }


def get_special_numbers_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-135: 특수 번호(삼각수·제곱수) 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    TRIANGULAR = {1, 3, 6, 10, 15, 21, 28, 36, 45}
    SQUARE = {1, 4, 9, 16, 25, 36}
    BOTH = TRIANGULAR & SQUARE  # {1, 36}

    tri_count_dist: dict[int, int] = {k: 0 for k in range(7)}
    sq_count_dist: dict[int, int] = {k: 0 for k in range(7)}
    tri_freq: dict[int, int] = {n: 0 for n in TRIANGULAR}
    sq_freq: dict[int, int] = {n: 0 for n in SQUARE}

    tri_totals: list[int] = []
    sq_totals: list[int] = []

    for draw in draws:
        nums = set(draw.numbers())
        tri_in = nums & TRIANGULAR
        sq_in = nums & SQUARE
        tri_count_dist[len(tri_in)] += 1
        sq_count_dist[len(sq_in)] += 1
        tri_totals.append(len(tri_in))
        sq_totals.append(len(sq_in))
        for n in tri_in:
            tri_freq[n] += 1
        for n in sq_in:
            sq_freq[n] += 1

    avg_tri = round(sum(tri_totals) / total, 3)
    avg_sq = round(sum(sq_totals) / total, 3)

    # 기대값: 9/45 * 6 = 1.2 삼각수, 6/45 * 6 = 0.8 제곱수
    expected_tri = round(len(TRIANGULAR) / 45 * 6, 3)
    expected_sq = round(len(SQUARE) / 45 * 6, 3)

    best_tri = max(tri_count_dist, key=lambda k: tri_count_dist[k])
    best_sq = max(sq_count_dist, key=lambda k: sq_count_dist[k])

    tri_dist_list = [
        {"count": k, "draws": tri_count_dist[k], "pct": round(tri_count_dist[k] / total * 100, 1)}
        for k in range(7)
    ]
    sq_dist_list = [
        {"count": k, "draws": sq_count_dist[k], "pct": round(sq_count_dist[k] / total * 100, 1)}
        for k in range(7)
    ]

    tri_freq_list = sorted(
        [{"number": n, "count": tri_freq[n], "pct": round(tri_freq[n] / total * 100, 1), "is_both": n in BOTH} for n in TRIANGULAR],
        key=lambda x: -x["count"],
    )
    sq_freq_list = sorted(
        [{"number": n, "count": sq_freq[n], "pct": round(sq_freq[n] / total * 100, 1), "is_both": n in BOTH} for n in SQUARE],
        key=lambda x: -x["count"],
    )

    recent = []
    for draw in reversed(draws[-20:]):
        nums = set(draw.numbers())
        tri_in = sorted(nums & TRIANGULAR)
        sq_in = sorted(nums & SQUARE)
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "tri": tri_in,
            "sq": sq_in,
            "tri_count": len(tri_in),
            "sq_count": len(sq_in),
        })

    return {
        "total": total,
        "tri_count": len(TRIANGULAR),
        "sq_count": len(SQUARE),
        "both_count": len(BOTH),
        "avg_tri": avg_tri,
        "avg_sq": avg_sq,
        "expected_tri": expected_tri,
        "expected_sq": expected_sq,
        "best_tri": best_tri,
        "best_tri_pct": round(tri_count_dist[best_tri] / total * 100, 1),
        "best_sq": best_sq,
        "best_sq_pct": round(sq_count_dist[best_sq] / total * 100, 1),
        "tri_dist_list": tri_dist_list,
        "sq_dist_list": sq_dist_list,
        "tri_freq_list": tri_freq_list,
        "sq_freq_list": sq_freq_list,
        "recent": recent,
    }


def get_median_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-129: 번호 중앙값 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    def calc_median(nums: list[int]) -> float:
        s = sorted(nums)
        return (s[2] + s[3]) / 2

    medians = [calc_median(draw.numbers()) for draw in draws]

    buckets = [
        {"label": "~9", "min": 0, "max": 10, "count": 0},
        {"label": "10~14", "min": 10, "max": 15, "count": 0},
        {"label": "15~19", "min": 15, "max": 20, "count": 0},
        {"label": "20~24", "min": 20, "max": 25, "count": 0},
        {"label": "25~29", "min": 25, "max": 30, "count": 0},
        {"label": "30~34", "min": 30, "max": 35, "count": 0},
        {"label": "35~", "min": 35, "max": float("inf"), "count": 0},
    ]

    for m in medians:
        for b in buckets:
            if b["min"] <= m < b["max"]:
                b["count"] += 1
                break

    avg_median = round(sum(medians) / total, 2)
    min_median = min(medians)
    max_median = max(medians)
    min_draw = draws[medians.index(min_median)]
    max_draw = draws[medians.index(max_median)]

    best_bucket = max(buckets, key=lambda b: b["count"])

    below_center = sum(1 for m in medians if m < 23)
    above_center = sum(1 for m in medians if m > 23)
    at_center = total - below_center - above_center

    bucket_list = [
        {
            "label": b["label"],
            "count": b["count"],
            "pct": round(b["count"] / total * 100, 1),
        }
        for b in buckets
    ]

    recent = []
    for draw, m in zip(reversed(draws[-20:]), reversed(medians[-20:])):
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "median": m,
        })

    return {
        "total": total,
        "avg_median": avg_median,
        "min_median": min_median,
        "max_median": max_median,
        "min_draw": {"drwNo": min_draw.drwNo, "numbers": sorted(min_draw.numbers())},
        "max_draw": {"drwNo": max_draw.drwNo, "numbers": sorted(max_draw.numbers())},
        "best_bucket_label": best_bucket["label"],
        "best_bucket_pct": round(best_bucket["count"] / total * 100, 1),
        "below_center": below_center,
        "below_pct": round(below_center / total * 100, 1),
        "above_center": above_center,
        "above_pct": round(above_center / total * 100, 1),
        "at_center": at_center,
        "at_pct": round(at_center / total * 100, 1),
        "bucket_list": bucket_list,
        "recent": recent,
    }


def get_position_dist_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-136: 번호 위치별(순서) 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)
    # 각 위치(0~5)별로 출현한 번호 수집
    pos_numbers: list[list[int]] = [[] for _ in range(6)]

    for draw in draws:
        nums = sorted(draw.numbers())
        for i, n in enumerate(nums):
            pos_numbers[i].append(n)

    positions = []
    for i in range(6):
        nums_at_pos = pos_numbers[i]
        avg = round(sum(nums_at_pos) / total, 2)
        mn = min(nums_at_pos)
        mx = max(nums_at_pos)
        cnt = Counter(nums_at_pos)
        mode_num = cnt.most_common(1)[0][0]
        mode_count = cnt.most_common(1)[0][1]
        top5 = [
            {"number": n, "count": c, "pct": round(c / total * 100, 1)}
            for n, c in cnt.most_common(5)
        ]
        buckets = {"1-9": 0, "10-19": 0, "20-29": 0, "30-39": 0, "40-45": 0}
        for n in nums_at_pos:
            if n <= 9:
                buckets["1-9"] += 1
            elif n <= 19:
                buckets["10-19"] += 1
            elif n <= 29:
                buckets["20-29"] += 1
            elif n <= 39:
                buckets["30-39"] += 1
            else:
                buckets["40-45"] += 1
        bucket_list = [
            {"range": k, "count": v, "pct": round(v / total * 100, 1)}
            for k, v in buckets.items()
        ]
        positions.append({
            "pos": i + 1,
            "avg": avg,
            "min": mn,
            "max": mx,
            "mode": mode_num,
            "mode_count": mode_count,
            "mode_pct": round(mode_count / total * 100, 1),
            "top5": top5,
            "bucket_list": bucket_list,
        })

    recent = []
    for draw in reversed(draws[-20:]):
        nums = sorted(draw.numbers())
        recent.append({"drwNo": draw.drwNo, "numbers": nums})

    return {
        "total": total,
        "positions": positions,
        "recent": recent,
    }


def get_units_digit_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-137: 번호 끝자리(일의 자리) 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    # 1~45에서 끝자리별 풀 크기
    POOL_SIZE = {d: 0 for d in range(10)}
    for n in range(1, 46):
        POOL_SIZE[n % 10] += 1
    # 회차당 기댓값: POOL_SIZE[d]/45 * 6
    expected = {d: round(POOL_SIZE[d] / 45 * 6, 3) for d in range(10)}

    # 끝자리별 총 출현 횟수
    digit_total: dict[int, int] = {d: 0 for d in range(10)}
    # digit_draw_dist[d][count] = count개 나온 회차 수
    digit_draw_dist: dict[int, dict[int, int]] = {d: {k: 0 for k in range(7)} for d in range(10)}

    for draw in draws:
        per_digit: dict[int, int] = {d: 0 for d in range(10)}
        for n in draw.numbers():
            per_digit[n % 10] += 1
        for d in range(10):
            digit_total[d] += per_digit[d]
            digit_draw_dist[d][per_digit[d]] += 1

    digit_stats = []
    for d in range(10):
        avg = round(digit_total[d] / total, 3)
        pool = POOL_SIZE[d]
        exp = expected[d]
        best_count = max(digit_draw_dist[d], key=lambda k: digit_draw_dist[d][k])
        dist_list = [
            {"count": k, "draws": digit_draw_dist[d][k],
             "pct": round(digit_draw_dist[d][k] / total * 100, 1)}
            for k in range(7)
        ]
        pool_nums = sorted([n for n in range(1, 46) if n % 10 == d])
        digit_stats.append({
            "digit": d,
            "pool_size": pool,
            "pool_nums": pool_nums,
            "total_appearances": digit_total[d],
            "avg": avg,
            "expected": exp,
            "diff": round(avg - exp, 3),
            "best_count": best_count,
            "best_count_pct": round(digit_draw_dist[d][best_count] / total * 100, 1),
            "dist_list": dist_list,
        })

    recent = []
    for draw in reversed(draws[-20:]):
        nums = sorted(draw.numbers())
        digits = sorted([n % 10 for n in nums])
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": nums,
            "digits": digits,
        })

    most_digit = max(range(10), key=lambda d: digit_total[d])
    least_digit = min(range(10), key=lambda d: digit_total[d])

    return {
        "total": total,
        "digit_stats": digit_stats,
        "most_digit": most_digit,
        "most_digit_total": digit_total[most_digit],
        "least_digit": least_digit,
        "least_digit_total": digit_total[least_digit],
        "recent": recent,
    }


def get_tens_digit_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-138: 번호 십의 자리 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    # 십의 자리 그룹 정의
    GROUPS = [
        {"label": "01~09", "min": 1,  "max": 9,  "pool": 9},
        {"label": "10~19", "min": 10, "max": 19, "pool": 10},
        {"label": "20~29", "min": 20, "max": 29, "pool": 10},
        {"label": "30~39", "min": 30, "max": 39, "pool": 10},
        {"label": "40~45", "min": 40, "max": 45, "pool": 6},
    ]

    group_totals = [0] * 5
    # group_dist[g][count] = 해당 그룹에서 count개 나온 회차 수
    group_dist: list[dict[int, int]] = [{k: 0 for k in range(7)} for _ in range(5)]

    for draw in draws:
        per_group = [0] * 5
        for n in draw.numbers():
            for i, g in enumerate(GROUPS):
                if g["min"] <= n <= g["max"]:
                    per_group[i] += 1
                    break
        for i in range(5):
            group_totals[i] += per_group[i]
            group_dist[i][per_group[i]] += 1

    group_stats = []
    for i, g in enumerate(GROUPS):
        avg = round(group_totals[i] / total, 3)
        expected = round(g["pool"] / 45 * 6, 3)
        best_count = max(group_dist[i], key=lambda k: group_dist[i][k])
        dist_list = [
            {"count": k, "draws": group_dist[i][k],
             "pct": round(group_dist[i][k] / total * 100, 1)}
            for k in range(7)
        ]
        pool_nums = list(range(g["min"], g["max"] + 1))
        group_stats.append({
            "label": g["label"],
            "pool": g["pool"],
            "pool_nums": pool_nums,
            "total": group_totals[i],
            "avg": avg,
            "expected": expected,
            "diff": round(avg - expected, 3),
            "best_count": best_count,
            "best_count_pct": round(group_dist[i][best_count] / total * 100, 1),
            "dist_list": dist_list,
        })

    most_idx = max(range(5), key=lambda i: group_totals[i])
    least_idx = min(range(5), key=lambda i: group_totals[i])

    # 최빈 조합 패턴: 5개 그룹 각각 몇 개씩 나왔는지 튜플
    pattern_counter: Counter = Counter()
    for draw in draws:
        per_group = [0] * 5
        for n in draw.numbers():
            for i, g in enumerate(GROUPS):
                if g["min"] <= n <= g["max"]:
                    per_group[i] += 1
                    break
        pattern_counter[tuple(per_group)] += 1

    top_patterns = [
        {"pattern": list(p), "count": c, "pct": round(c / total * 100, 1)}
        for p, c in pattern_counter.most_common(10)
    ]

    recent = []
    for draw in reversed(draws[-20:]):
        nums = sorted(draw.numbers())
        per_group = [0] * 5
        for n in nums:
            for i, g in enumerate(GROUPS):
                if g["min"] <= n <= g["max"]:
                    per_group[i] += 1
                    break
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": nums,
            "per_group": per_group,
        })

    return {
        "total": total,
        "group_stats": group_stats,
        "most_label": GROUPS[most_idx]["label"],
        "most_total": group_totals[most_idx],
        "least_label": GROUPS[least_idx]["label"],
        "least_total": group_totals[least_idx],
        "top_patterns": top_patterns,
        "recent": recent,
    }


def get_prime_number_dist_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-139: 번호 소수(Prime Number) 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43}
    prime_count_dist: dict[int, int] = {k: 0 for k in range(7)}
    prime_freq: dict[int, int] = {p: 0 for p in PRIMES}
    prime_totals: list[int] = []

    for draw in draws:
        nums = set(draw.numbers())
        primes_in = nums & PRIMES
        cnt = len(primes_in)
        prime_count_dist[cnt] += 1
        prime_totals.append(cnt)
        for p in primes_in:
            prime_freq[p] += 1

    avg_primes = round(sum(prime_totals) / total, 3)
    expected = round(len(PRIMES) / 45 * 6, 3)
    best_count = max(prime_count_dist, key=lambda k: prime_count_dist[k])

    dist_list = [
        {"count": k, "draws": prime_count_dist[k],
         "pct": round(prime_count_dist[k] / total * 100, 1)}
        for k in range(7)
    ]

    freq_list = sorted(
        [{"number": p, "count": prime_freq[p],
          "pct": round(prime_freq[p] / total * 100, 1)}
         for p in PRIMES],
        key=lambda x: -x["count"],
    )

    recent = []
    for draw in reversed(draws[-20:]):
        nums = set(draw.numbers())
        primes_in = sorted(nums & PRIMES)
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "primes": primes_in,
            "prime_count": len(primes_in),
        })

    return {
        "total": total,
        "prime_count": len(PRIMES),
        "avg_primes": avg_primes,
        "expected": expected,
        "diff": round(avg_primes - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(prime_count_dist[best_count] / total * 100, 1),
        "zero_prime_pct": round(prime_count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_sum_distribution_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-140: 번호 합계 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    sums = [sum(draw.numbers()) for draw in draws]

    actual_min = min(sums)
    actual_max = max(sums)
    actual_avg = round(sum(sums) / total, 2)
    theoretical_avg = 138.0

    # Bucket distribution: 20~59, 60~79, 80~99, ..., 220~239, 240~259
    # Use buckets of width 20 starting from 20
    buckets: dict[str, int] = {}
    bucket_starts = list(range(20, 260, 20))
    for s in bucket_starts:
        label = f"{s}~{s+19}"
        buckets[label] = 0

    for s in sums:
        b = (s // 20) * 20
        if b < 20:
            b = 20
        if b > 240:
            b = 240
        label = f"{b}~{b+19}"
        buckets[label] = buckets.get(label, 0) + 1

    bucket_list = [
        {"range": k, "count": buckets[k], "pct": round(buckets[k] / total * 100, 1)}
        for k in sorted(buckets.keys(), key=lambda x: int(x.split("~")[0]))
    ]

    # Peak bucket
    peak = max(bucket_list, key=lambda x: x["count"])

    # Find mode sum
    sum_counter = Counter(sums)
    mode_sum = sum_counter.most_common(1)[0][0]
    mode_count = sum_counter.most_common(1)[0][1]

    # Top 10 most frequent sums
    top_sums = [
        {"sum": s, "count": c, "pct": round(c / total * 100, 1)}
        for s, c in sum_counter.most_common(10)
    ]

    # Recent 20 draws
    recent = []
    for draw in reversed(draws[-20:]):
        nums = sorted(draw.numbers())
        s = sum(nums)
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": nums,
            "sum": s,
        })

    return {
        "total": total,
        "actual_min": actual_min,
        "actual_max": actual_max,
        "actual_avg": actual_avg,
        "theoretical_avg": theoretical_avg,
        "avg_diff": round(actual_avg - theoretical_avg, 2),
        "mode_sum": mode_sum,
        "mode_count": mode_count,
        "mode_pct": round(mode_count / total * 100, 1),
        "peak_range": peak["range"],
        "peak_count": peak["count"],
        "peak_pct": peak["pct"],
        "bucket_list": bucket_list,
        "top_sums": top_sums,
        "recent": recent,
    }


def get_median_dist_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-141: 번호 중앙값 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    # median = (3rd + 4th) / 2 for sorted 6 numbers
    medians: list[float] = []
    for draw in draws:
        nums = sorted(draw.numbers())
        m = (nums[2] + nums[3]) / 2
        medians.append(m)

    actual_avg = round(sum(medians) / total, 3)
    theoretical_avg = 23.0
    actual_min = min(medians)
    actual_max = max(medians)

    # Distribution by bucket (width 5): 1~5, 6~10, ..., 41~45
    bucket_size = 5
    bucket_labels = [f"{s}~{s+bucket_size-1}" for s in range(1, 46, bucket_size)]
    bucket_counts: dict[str, int] = {label: 0 for label in bucket_labels}
    for m in medians:
        idx = int((m - 1) // bucket_size)
        if idx < 0:
            idx = 0
        if idx >= len(bucket_labels):
            idx = len(bucket_labels) - 1
        bucket_counts[bucket_labels[idx]] += 1

    bucket_list = [
        {"range": label, "count": bucket_counts[label],
         "pct": round(bucket_counts[label] / total * 100, 1)}
        for label in bucket_labels
    ]

    peak = max(bucket_list, key=lambda x: x["count"])

    # Count exact half-integers vs integers separately
    int_count = sum(1 for m in medians if m == int(m))
    half_count = total - int_count

    # Most frequent median values (top 10)
    med_counter = Counter(medians)
    top_medians = [
        {"median": m, "count": c, "pct": round(c / total * 100, 1)}
        for m, c in med_counter.most_common(10)
    ]

    # Recent 20 draws
    recent = []
    for draw in reversed(draws[-20:]):
        nums = sorted(draw.numbers())
        m = (nums[2] + nums[3]) / 2
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": nums,
            "n3": nums[2],
            "n4": nums[3],
            "median": m,
        })

    return {
        "total": total,
        "actual_avg": actual_avg,
        "theoretical_avg": theoretical_avg,
        "avg_diff": round(actual_avg - theoretical_avg, 3),
        "actual_min": actual_min,
        "actual_max": actual_max,
        "int_count": int_count,
        "int_pct": round(int_count / total * 100, 1),
        "half_count": half_count,
        "half_pct": round(half_count / total * 100, 1),
        "peak_range": peak["range"],
        "peak_pct": peak["pct"],
        "bucket_list": bucket_list,
        "top_medians": top_medians,
        "recent": recent,
    }


def get_fibonacci_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-142: 피보나치 번호 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    fibonacci = {1, 2, 3, 5, 8, 13, 21, 34}
    expected = round(len(fibonacci) / 45 * 6, 3)

    fib_count_dist: dict[int, int] = dict.fromkeys(range(7), 0)
    fib_freq: dict[int, int] = dict.fromkeys(fibonacci, 0)
    fib_totals: list[int] = []

    for draw in draws:
        nums = set(draw.numbers())
        fibs_in = nums & fibonacci
        cnt = len(fibs_in)
        fib_count_dist[cnt] += 1
        fib_totals.append(cnt)
        for f in fibs_in:
            fib_freq[f] += 1

    avg_fib = round(sum(fib_totals) / total, 3)
    best_count = max(fib_count_dist, key=lambda k: fib_count_dist[k])

    dist_list = [
        {"count": k, "draws": fib_count_dist[k],
         "pct": round(fib_count_dist[k] / total * 100, 1)}
        for k in range(7)
    ]

    freq_list = sorted(
        [{"number": f, "count": fib_freq[f],
          "pct": round(fib_freq[f] / total * 100, 1)}
         for f in fibonacci],
        key=lambda x: -x["count"],
    )

    recent = []
    for draw in reversed(draws[-20:]):
        nums = set(draw.numbers())
        fibs_in = sorted(nums & fibonacci)
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "fibs": fibs_in,
            "fib_count": len(fibs_in),
        })

    return {
        "total": total,
        "fib_count": len(fibonacci),
        "fib_numbers": sorted(fibonacci),
        "avg_fib": avg_fib,
        "expected": expected,
        "diff": round(avg_fib - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(fib_count_dist[best_count] / total * 100, 1),
        "zero_fib_pct": round(fib_count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_composite_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-143: 합성수(Composite Number) 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    # 1~45 내 합성수 (1도 아니고 소수도 아닌 수)
    PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43}
    COMPOSITES = {n for n in range(1, 46) if n != 1 and n not in PRIMES}
    expected = round(len(COMPOSITES) / 45 * 6, 3)

    comp_count_dist: dict[int, int] = {k: 0 for k in range(7)}
    comp_freq: dict[int, int] = {c: 0 for c in COMPOSITES}
    comp_totals: list[int] = []

    for draw in draws:
        nums = set(draw.numbers())
        comps_in = nums & COMPOSITES
        cnt = len(comps_in)
        comp_count_dist[cnt] += 1
        comp_totals.append(cnt)
        for c in comps_in:
            comp_freq[c] += 1

    avg_comp = round(sum(comp_totals) / total, 3)
    best_count = max(comp_count_dist, key=lambda k: comp_count_dist[k])

    dist_list = [
        {"count": k, "draws": comp_count_dist[k],
         "pct": round(comp_count_dist[k] / total * 100, 1)}
        for k in range(7)
    ]

    # 상위 15개 최빈 합성수
    freq_list = sorted(
        [{"number": c, "count": comp_freq[c],
          "pct": round(comp_freq[c] / total * 100, 1)}
         for c in COMPOSITES],
        key=lambda x: -x["count"],
    )[:15]

    # 하위 5개 최저 빈도 합성수
    bottom_list = sorted(
        [{"number": c, "count": comp_freq[c],
          "pct": round(comp_freq[c] / total * 100, 1)}
         for c in COMPOSITES],
        key=lambda x: x["count"],
    )[:5]

    recent = []
    for draw in reversed(draws[-20:]):
        nums = set(draw.numbers())
        comps_in = sorted(nums & COMPOSITES)
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "composites": comps_in,
            "comp_count": len(comps_in),
        })

    return {
        "total": total,
        "composite_count": len(COMPOSITES),
        "avg_comp": avg_comp,
        "expected": expected,
        "diff": round(avg_comp - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(comp_count_dist[best_count] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "bottom_list": bottom_list,
        "recent": recent,
    }


def get_multiples3_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-144: 3의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    MULT3 = {n for n in range(1, 46) if n % 3 == 0}
    expected = round(len(MULT3) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(7)}
    freq: dict[int, int] = {m: 0 for m in MULT3}
    totals: list[int] = []

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT3
        cnt = len(in_draw)
        count_dist[cnt] += 1
        totals.append(cnt)
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(totals) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {"count": k, "draws": count_dist[k],
         "pct": round(count_dist[k] / total * 100, 1)}
        for k in range(7)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m],
          "pct": round(freq[m] / total * 100, 1)}
         for m in MULT3],
        key=lambda x: -x["count"],
    )

    recent = []
    for draw in reversed(draws[-20:]):
        nums = set(draw.numbers())
        in_draw = sorted(nums & MULT3)
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult3": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult3_count": len(MULT3),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples5_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-145: 5의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    MULT5 = {n for n in range(1, 46) if n % 5 == 0}
    expected = round(len(MULT5) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(7)}
    freq: dict[int, int] = {m: 0 for m in MULT5}
    totals: list[int] = []

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT5
        cnt = len(in_draw)
        count_dist[cnt] += 1
        totals.append(cnt)
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(totals) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {"count": k, "draws": count_dist[k],
         "pct": round(count_dist[k] / total * 100, 1)}
        for k in range(7)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m],
          "pct": round(freq[m] / total * 100, 1)}
         for m in MULT5],
        key=lambda x: -x["count"],
    )

    recent = []
    for draw in reversed(draws[-20:]):
        nums = set(draw.numbers())
        in_draw = sorted(nums & MULT5)
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult5": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult5_count": len(MULT5),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples7_analysis() -> dict[str, Any] | None:
    """SPEC-LOTTO-146: 7의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    total = len(draws)

    MULT7 = {n for n in range(1, 46) if n % 7 == 0}
    expected = round(len(MULT7) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(7)}
    freq: dict[int, int] = {m: 0 for m in MULT7}
    totals: list[int] = []

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT7
        cnt = len(in_draw)
        count_dist[cnt] += 1
        totals.append(cnt)
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(totals) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {"count": k, "draws": count_dist[k],
         "pct": round(count_dist[k] / total * 100, 1)}
        for k in range(7)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m],
          "pct": round(freq[m] / total * 100, 1)}
         for m in MULT7],
        key=lambda x: -x["count"],
    )

    recent = []
    for draw in reversed(draws[-20:]):
        nums = set(draw.numbers())
        in_draw = sorted(nums & MULT7)
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult7": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult7_count": len(MULT7),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples11_analysis() -> dict | None:
    """SPEC-LOTTO-147: 11의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT11 = {n for n in range(1, 46) if n % 11 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT11) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT11) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT11}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT11
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT11) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT11],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT11
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult11": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult11_count": len(MULT11),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples13_analysis() -> dict | None:
    """SPEC-LOTTO-148: 13의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT13 = {n for n in range(1, 46) if n % 13 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT13) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT13) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT13}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT13
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT13) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT13],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT13
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult13": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult13_count": len(MULT13),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples17_analysis() -> dict | None:
    """SPEC-LOTTO-149: 17의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT17 = {n for n in range(1, 46) if n % 17 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT17) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT17) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT17}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT17
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT17) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT17],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT17
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult17": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult17_count": len(MULT17),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples19_analysis() -> dict | None:
    """SPEC-LOTTO-150: 19의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT19 = {n for n in range(1, 46) if n % 19 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT19) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT19) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT19}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT19
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT19) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT19],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT19
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult19": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult19_count": len(MULT19),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples23_analysis() -> dict | None:
    """SPEC-LOTTO-151: 23의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT23 = {n for n in range(1, 46) if n % 23 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT23) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT23) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT23}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT23
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT23) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT23],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT23
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult23": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult23_count": len(MULT23),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples29_analysis() -> dict | None:
    """SPEC-LOTTO-152: 29의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT29 = {n for n in range(1, 46) if n % 29 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT29) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT29) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT29}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT29
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT29) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT29],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT29
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult29": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult29_count": len(MULT29),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples31_analysis() -> dict | None:
    """SPEC-LOTTO-153: 31의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT31 = {n for n in range(1, 46) if n % 31 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT31) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT31) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT31}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT31
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT31) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT31],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT31
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult31": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult31_count": len(MULT31),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples37_analysis() -> dict | None:
    """SPEC-LOTTO-154: 37의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT37 = {n for n in range(1, 46) if n % 37 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT37) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT37) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT37}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT37
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT37) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT37],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT37
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult37": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult37_count": len(MULT37),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples41_analysis() -> dict | None:
    """SPEC-LOTTO-155: 41의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT41 = {n for n in range(1, 46) if n % 41 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT41) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT41) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT41}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT41
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT41) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT41],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT41
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult41": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult41_count": len(MULT41),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_multiples43_analysis() -> dict | None:
    """SPEC-LOTTO-156: 43의 배수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    MULT43 = {n for n in range(1, 46) if n % 43 == 0}  # noqa: N806
    total = len(draws)
    expected = round(len(MULT43) / 45 * 6, 3)

    count_dist: dict[int, int] = {k: 0 for k in range(len(MULT43) + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in MULT43}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & MULT43
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(len(MULT43) + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in MULT43],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & MULT43
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "mult43": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "mult43_count": len(MULT43),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_perfect_square_analysis() -> dict | None:
    """SPEC-LOTTO-157: 완전제곱수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    import math  # noqa: PLC0415

    SQUARES = {n for n in range(1, 46) if math.isqrt(n) ** 2 == n}  # noqa: N806
    total = len(draws)
    expected = round(len(SQUARES) / 45 * 6, 3)

    max_k = len(SQUARES)
    count_dist: dict[int, int] = {k: 0 for k in range(max_k + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in SQUARES}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & SQUARES
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(max_k + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in SQUARES],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & SQUARES
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "squares": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "square_count": len(SQUARES),
        "squares_list": sorted(SQUARES),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_triangular_number_analysis() -> dict | None:
    """SPEC-LOTTO-158: 삼각수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    TRIANGULAR = {n * (n + 1) // 2 for n in range(1, 20) if n * (n + 1) // 2 <= 45}  # noqa: N806
    total = len(draws)
    expected = round(len(TRIANGULAR) / 45 * 6, 3)

    max_k = len(TRIANGULAR)
    count_dist: dict[int, int] = {k: 0 for k in range(max_k + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in TRIANGULAR}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & TRIANGULAR
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(max_k + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in TRIANGULAR],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & TRIANGULAR
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "triangular": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "tri_count": len(TRIANGULAR),
        "tri_list": sorted(TRIANGULAR),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_perfect_cube_analysis() -> dict | None:
    """SPEC-LOTTO-159: 세제곱수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    CUBES = {n ** 3 for n in range(1, 10) if n ** 3 <= 45}  # noqa: N806
    total = len(draws)
    expected = round(len(CUBES) / 45 * 6, 3)

    max_k = len(CUBES)
    count_dist: dict[int, int] = {k: 0 for k in range(max_k + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in CUBES}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & CUBES
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(max_k + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in CUBES],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & CUBES
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "cubes": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "cube_count": len(CUBES),
        "cubes_list": sorted(CUBES),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_fibonacci_analysis() -> dict | None:
    """SPEC-LOTTO-160: 피보나치 수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    fib_set: set[int] = set()
    a, b = 1, 1
    while a <= 45:
        fib_set.add(a)
        a, b = b, a + b
    FIBONACCI = fib_set  # noqa: N806

    total = len(draws)
    expected = round(len(FIBONACCI) / 45 * 6, 3)

    max_k = len(FIBONACCI)
    count_dist: dict[int, int] = {k: 0 for k in range(max_k + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in FIBONACCI}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & FIBONACCI
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(max_k + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in FIBONACCI],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & FIBONACCI
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "fibonacci": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "fib_count": len(FIBONACCI),
        "fib_list": sorted(FIBONACCI),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_prime_analysis() -> dict | None:
    """SPEC-LOTTO-161: 소수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    def _is_prime(n: int) -> bool:
        if n < 2:
            return False
        for i in range(2, int(n ** 0.5) + 1):
            if n % i == 0:
                return False
        return True

    PRIMES = {n for n in range(1, 46) if _is_prime(n)}  # noqa: N806

    total = len(draws)
    expected = round(len(PRIMES) / 45 * 6, 3)

    max_k = len(PRIMES)
    count_dist: dict[int, int] = {k: 0 for k in range(max_k + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in PRIMES}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & PRIMES
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(max_k + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in PRIMES],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & PRIMES
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "primes": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "prime_count": len(PRIMES),
        "primes_list": sorted(PRIMES),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_even_analysis() -> dict | None:
    """SPEC-LOTTO-162: 짝수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    EVENS = {n for n in range(1, 46) if n % 2 == 0}  # noqa: N806

    total = len(draws)
    expected = round(len(EVENS) / 45 * 6, 3)

    max_k = 6
    count_dist: dict[int, int] = {k: 0 for k in range(max_k + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in EVENS}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & EVENS
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(max_k + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in EVENS],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & EVENS
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "evens": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "even_count": len(EVENS),
        "evens_list": sorted(EVENS),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }


def get_odd_analysis() -> dict | None:
    """SPEC-LOTTO-163: 홀수 분포 분석."""
    draws = get_draws()
    if not draws:
        return None

    ODDS = {n for n in range(1, 46) if n % 2 == 1}  # noqa: N806

    total = len(draws)
    expected = round(len(ODDS) / 45 * 6, 3)

    max_k = 6
    count_dist: dict[int, int] = {k: 0 for k in range(max_k + 1)}  # noqa: C420
    freq: dict[int, int] = {m: 0 for m in ODDS}  # noqa: C420

    for draw in draws:
        nums = set(draw.numbers())
        in_draw = nums & ODDS
        count_dist[len(in_draw)] = count_dist.get(len(in_draw), 0) + 1
        for m in in_draw:
            freq[m] += 1

    avg = round(sum(k * v for k, v in count_dist.items()) / total, 3)
    best_count = max(count_dist, key=lambda k: count_dist[k])

    dist_list = [
        {
            "count": k,
            "draws": count_dist[k],
            "pct": round(count_dist[k] / total * 100, 1),
        }
        for k in range(max_k + 1)
    ]

    freq_list = sorted(
        [{"number": m, "count": freq[m], "pct": round(freq[m] / total * 100, 1)} for m in ODDS],
        key=lambda x: x["number"],
    )

    recent: list[dict] = []
    for draw in sorted(draws, key=lambda d: d.drwNo, reverse=True)[:20]:
        nums = set(draw.numbers())
        in_draw = nums & ODDS
        recent.append({
            "drwNo": draw.drwNo,
            "numbers": sorted(draw.numbers()),
            "odds": in_draw,
            "count": len(in_draw),
        })

    return {
        "total": total,
        "odd_count": len(ODDS),
        "odds_list": sorted(ODDS),
        "avg": avg,
        "expected": expected,
        "diff": round(avg - expected, 3),
        "best_count": best_count,
        "best_count_pct": round(count_dist[best_count] / total * 100, 1),
        "zero_pct": round(count_dist[0] / total * 100, 1),
        "dist_list": dist_list,
        "freq_list": freq_list,
        "recent": recent,
    }
