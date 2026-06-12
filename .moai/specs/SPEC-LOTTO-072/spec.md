---
id: SPEC-LOTTO-072
version: 0.1.0
status: Planned
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-072: 끝자리 유니크 수 분포 분석

## HISTORY

- 2026-06-12 (v0.1.0): 최초 작성 (Planned). 회차별 본번호 6개(보너스 제외)의
  **서로 다른 끝자리(units digit) 값의 개수**(1~6)를 산출하고, 전체 이력에 대해
  6개 구간(`"1"`~`"6"`)의 분포를 분석하는 읽기 전용 통계 기능으로 정의.
  SPEC-070(AC값)·071(중앙값)의 `data.py` 확장 패턴을 그대로 따른다.

## 개요

각 회차의 당첨번호 6개(보너스 제외)에 대해 각 번호의 **끝자리(units digit,
`n % 10`)** 를 구한 뒤, 한 회차 안에서 **서로 다른 끝자리 값이 몇 종류**나
나타나는지를 센다. 이 "유니크 끝자리 개수"는 1(여섯 번호의 끝자리가 모두 같음,
매우 희귀)부터 6(여섯 번호의 끝자리가 모두 다름)까지의 정수 값을 가진다. 전체
이력에 대해 이 개수가 1~6 중 어디에 분포하는지를 분석하여, 번호 조합이 끝자리
관점에서 얼마나 다양한지를 한 값으로 요약한다.

### SPEC-055 / SPEC-063 과의 구분 (중요)

[HARD] 본 SPEC은 기존 끝자리 SPEC들과 **계산 대상이 다른 별개 기능**이다.
혼동을 막기 위해 명시한다:

| SPEC | 함수 | 무엇을 세는가 |
|------|------|---------------|
| SPEC-055 | `get_last_digit_stats` | 전체 이력에서 각 끝자리(0~9)의 **출현 빈도** |
| SPEC-063 | `get_last_digit_sum_stats` | 회차별 끝자리들의 **합계** 분포 |
| **SPEC-072** | **`get_last_digit_unique_stats`** | **회차 안에서 서로 다른 끝자리 값의 개수**(1~6) |

SPEC-055는 "끝자리 3이 역대 몇 번 나왔나"를 묻고, SPEC-072는 "이번 회차의 여섯
번호가 끝자리 기준 몇 종류로 이뤄졌나"를 묻는다. 따라서 SPEC-055/063과 병합하지
않고 신규 함수로 구현한다.

### 유니크 끝자리 개수 정의와 예시

한 회차의 유니크 끝자리 개수는 `len(set(n % 10 for n in draw.numbers()))` 이다.
6개 번호의 끝자리를 집합(set)으로 모은 뒤 원소 개수를 센다.

- 예시: 번호 `[3, 13, 23, 31, 42, 5]`
  - 끝자리 = `{3, 3, 3, 1, 2, 5}` → 집합 `{1, 2, 3, 5}` → **4종**
- 예시: 번호 `[1, 11, 21, 31, 41, 45]`
  - 끝자리 = `{1, 1, 1, 1, 1, 5}` → 집합 `{1, 5}` → **2종**
- 예시: 번호 `[3, 7, 12, 25, 38, 44]`
  - 끝자리 = `{3, 7, 2, 5, 8, 4}` → 집합 `{2, 3, 4, 5, 7, 8}` → **6종**(모두 다름)

### 값의 범위 (1~6, 6개 버킷)

[HARD] 유니크 끝자리 개수는 항상 **1 이상 6 이하**이다. 번호가 6개이고 각
번호는 최소 1개의 끝자리를 가지므로 최소 1종(모두 같은 끝자리), 최대 6종(모두
다른 끝자리)이다. 0은 불가능하다(번호가 0개일 때만 0이며, 그 경우는 회차가
아니다). 따라서 분포 키는 `"1"`, `"2"`, `"3"`, `"4"`, `"5"`, `"6"` 의 **6개로
고정**하며, 미관측 구간은 `count=0` / `pct=0.0` 으로 zero-fill 한다.

- 실무상 대부분의 회차는 **5~6종**에 분포한다(45개 번호 중 6개를 뽑으면 끝자리가
  겹칠 확률이 낮음). 1~2종은 매우 희귀하다.

### all_different_pct (모두 다른 비율)

`all_different_pct` 는 유니크 끝자리 개수가 **정확히 6**(모든 끝자리가 서로
다름)인 회차의 비율(%)이다. 끝자리 관점에서 "완전 분산된" 조합이 얼마나 자주
나오는지를 측정한다.

### 응답 구조

```python
{
    "total_draws": int,
    "avg_unique_count": float,      # 전체 회차 유니크 끝자리 개수 평균, 2자리 반올림
    "most_common_count": int,       # 가장 자주 등장한 개수(1~6); 동률 시 더 작은 값 우선
    "all_different_pct": float,      # 유니크 개수 == 6 회차 비율(%), 2자리 반올림
    "unique_distribution": {
        "1": {"count": int, "pct": float},
        "2": {"count": int, "pct": float},
        "3": {"count": int, "pct": float},
        "4": {"count": int, "pct": float},
        "5": {"count": int, "pct": float},
        "6": {"count": int, "pct": float},
    },
}
```

`unique_distribution` 은 항상 6개 키를 모두 포함한다(누락 구간은 `count=0`,
`pct=0.0` 으로 zero-fill). 빈 draws → 모든 값 0, 6개 키 존재,
`most_common_count=1`, `avg_unique_count=0.0`, `all_different_pct=0.0`.

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·기존 통계 로직을 변경하지 않고
`lotto/web/data.py` 의 확장 패턴(SPEC-070·071)을 그대로 따른다. 결과는 메모리에
캐시하며 DB에 영속화하지 않는다.

## 용어 정의

| 용어 | 정의 |
|------|------|
| 끝자리 (last/units digit) | 번호 `n` 의 일의 자리 값 `n % 10` (0~9) |
| 유니크 끝자리 개수 (unique count) | 한 회차 6개 본번호의 끝자리 집합 크기 `len(set(n % 10 ...))` (1~6) |
| 개수 키 (count key) | 유니크 개수가 속하는 6개 고정 키 중 하나 (`"1"`~`"6"`) |
| all_different | 유니크 끝자리 개수가 6인 상태 (여섯 끝자리가 모두 다름) |
| 본번호 (main numbers) | `draw.numbers()` 가 반환하는 6개 번호 (보너스 제외) |

## 요구사항 (EARS)

### 기능 요구사항

**REQ-LDU-001** [Ubiquitous]
The system SHALL compute, for each historical draw, the unique last-digit count
defined as the number of distinct units digits among the 6 main numbers (the bonus
number excluded): `unique_count = len(set(n % 10 for n in draw.numbers()))`.

**REQ-LDU-002** [Event-Driven]
WHEN the `/api/stats/last_digit_unique` endpoint is called THEN the system SHALL
return a JSON response containing `total_draws`, `avg_unique_count`,
`most_common_count`, `all_different_pct`, and `unique_distribution` — where
`unique_distribution` is a nested dict keyed by the 6 string keys `"1"`, `"2"`,
`"3"`, `"4"`, `"5"`, `"6"`, each mapping to `count` and `pct`.

**REQ-LDU-003** [Event-Driven]
WHEN the `/stats/last-digit-unique` page is requested THEN the system SHALL render
an HTML page whose navigation/heading contains the Korean text "끝자리유니크", using
the same stats dict.

**REQ-LDU-004** [Ubiquitous]
The system SHALL always include all 6 count keys (`"1"`..`"6"`) in
`unique_distribution` (zero-filled when a count is absent from the data). Each draw's
unique count SHALL be assigned to exactly one bucket equal to its computed count.

**REQ-LDU-005** [Event-Driven]
WHEN `invalidate_cache()` is called THEN `_last_digit_unique_cache` SHALL be cleared.

**REQ-LDU-006** [Ubiquitous]
The system SHALL determine `most_common_count` as the count key with the highest
`count`; on a tie, the smaller unique count (earlier in the fixed key order
`"1"`..`"6"`) SHALL win.

**REQ-LDU-007** [Ubiquitous]
The system SHALL compute `all_different_pct` as the percentage of draws whose unique
last-digit count is exactly 6.

**REQ-LDU-008** [Ubiquitous]
The system SHALL compute `avg_unique_count` as the arithmetic mean of all per-draw
unique last-digit counts.

### 비기능 요구사항

**REQ-LDU-NF-001** [State-Driven]
IF the draws list is empty THEN the system SHALL return all-zero stats with all 6
keys present (each `count=0`, `pct=0.0`), `most_common_count=1`,
`avg_unique_count=0.0`, and `all_different_pct=0.0` without raising an exception.

**REQ-LDU-NF-002** [Unwanted]
The system SHALL NOT include the bonus number in the unique last-digit computation.

**REQ-LDU-NF-003** [Unwanted]
The system SHALL NOT modify `analyzer.py`, `models.py`, `recommender.py`, or
`simulator.py`. Only `lotto/web/` layer files are extended. In particular, the system
SHALL NOT modify the existing `get_last_digit_stats` (SPEC-055) or
`get_last_digit_sum_stats` (SPEC-063) functions.

**REQ-LDU-NF-004** [Ubiquitous]
Numeric ratio/average fields (`avg_unique_count`, `all_different_pct`, and each
bucket `pct`) SHALL be rounded to 2 decimal places.

**REQ-LDU-NF-005** [Ubiquitous]
The implementation SHALL be Python 3.9 compatible (no walrus `:=`,
no `zip(strict=True)`, no `match-case`) and server-rendered only (no client JS).

## 인수 기준

상세 인수 기준은 [acceptance.md](acceptance.md) 참조 (AC-072-001 ~ AC-072-020).

## Exclusions (What NOT to Build)

- 기존 SPEC-055(`get_last_digit_stats`, 끝자리별 출현 빈도)·SPEC-063
  (`get_last_digit_sum_stats`, 끝자리 합계) 기능과의 병합·수정 — 별개 함수 신규 추가
- 추천 엔진 연동 (유니크 끝자리 개수 기반 가중치·필터 추가 금지)
- 어떤 끝자리(0~9)가 중복되었는지에 대한 세부 분해 (중복 끝자리 값 목록 등)
- 끝자리 외 다른 자릿수(십의 자리 등) 기준 유니크 분석 — 별도 SPEC 대상
- 유니크 개수 예측 모델·시계열 추세 분석
- DB 영속화 (메모리 캐시만 사용)
- 윈도(recent_n) 기반 부분 집계
- 보너스 번호를 포함한 7개 조합의 유니크 끝자리 계산

## 전제조건

- Python 3.9+ 환경 (walrus `:=`, `zip(strict=True)`, `match-case` 사용 금지)
- SPEC-070, SPEC-071 패턴이 `lotto/web/data.py` 에 존재함
- 유니크 끝자리 산출에 `draw.numbers()` (6개 메인 번호) 사용
- 신규 심볼(`get_last_digit_unique_stats`, `_last_digit_unique_cache`,
  `/api/stats/last_digit_unique`, `/stats/last-digit-unique`,
  `last_digit_unique.html`)은 모두 비중복으로 검증됨 (기존
  `get_last_digit_unique_stats` 부재 확인 완료)
