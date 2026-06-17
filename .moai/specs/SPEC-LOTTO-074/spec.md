---
id: SPEC-LOTTO-074
version: 1.0.0
status: Completed
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-074: 짝수 포함 개수 분포 분석

## HISTORY

- 2026-06-12 (v1.0.0): 구현 완료. 29개 테스트 추가. commit 96fad7e
- 2026-06-12 (v0.1.0): 최초 작성 (Planned). 회차별 본번호 6개(보너스 제외) 중
  **짝수(2, 4, 6, ..., 44)에 해당하는 번호의 개수**(0~6)를 산출하고, 전체 이력에
  대해 7개 구간(`"0"`~`"6"`)의 분포를 분석하는 읽기 전용 통계 기능으로 정의.
  SPEC-073(3의 배수 개수)의 `data.py` 확장 패턴을 그대로 따른다. SPEC-061
  (`get_odd_even_stats`, 홀짝 비율)과는 별개 기능이다(아래 "SPEC-061과의 관계" 참조).

## 개요

각 회차의 당첨번호 6개(보너스 제외)에 대해 각 번호가 **짝수인지**(`n % 2 == 0`)
판별한 뒤, 한 회차 안에 짝수가 **몇 개** 포함되어 있는지를 센다. 이 "짝수 개수"는
0(짝수가 하나도 없음)부터 6(여섯 번호가 모두 짝수)까지의 정수 값을 가진다. 전체
이력에 대해 이 개수가 0~6 중 어디에 분포하는지를 분석하여, 번호 조합이 짝수를
얼마나 포함하는 경향이 있는지를 한 값으로 요약한다.

### 1~45 범위의 짝수

1~45 범위에서 짝수는 다음 22개이다(전체 45개 중 약 48.9%):

```
2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44
```

따라서 한 회차의 본번호 6개가 무작위라면 짝수 개수의 기대값은 약
`6 * 22/45 ≈ 2.93` 부근이다.

### 짝수 개수 정의와 예시

한 회차의 짝수 개수는 `sum(1 for n in draw.numbers() if n % 2 == 0)` 이다.
6개 번호 각각에 대해 2로 나누어떨어지는지 검사하고 그 개수를 센다.

- 예시: 번호 `[3, 7, 12, 20, 33, 44]`
  - 짝수 = `{12, 20, 44}` → **3개**
- 예시: 번호 `[1, 3, 5, 7, 9, 11]`
  - 짝수 없음 → **0개**
- 예시: 번호 `[2, 4, 6, 8, 10, 12]`
  - 여섯 번호 모두 짝수 → **6개**

### 값의 범위 (0~6, 7개 버킷)

[HARD] 짝수 개수는 항상 **0 이상 6 이하**이다. 번호가 6개이므로 최소 0개
(짝수 전무), 최대 6개(모두 짝수)이다. 따라서 분포 키는 `"0"`, `"1"`, `"2"`,
`"3"`, `"4"`, `"5"`, `"6"` 의 **7개로 고정**하며, 미관측 구간은 `count=0` /
`pct=0.0` 으로 zero-fill 한다. 빈 회차의 기본 최빈값도 `0` 이다.

### high_even_pct (짝수 다수 비율)

`high_even_pct` 는 짝수 개수가 **3 이상**(즉 6개 번호의 절반 이상이 짝수)인
회차의 비율(%)이다. 짝수에 "치우친" 조합이 얼마나 자주 나오는지를 측정한다.

### SPEC-061과의 관계 (병합 금지)

[HARD] 본 SPEC은 SPEC-061의 `get_odd_even_stats`(홀짝 **비율** 분포)와는
**별개의 독립 기능**이며 두 기능을 통합하지 않는다.

- SPEC-061(`get_odd_even_stats`): 홀수 개수·짝수 개수를 함께 다루는 **비율 중심**
  통합 분석. `even_distribution`(짝수 개수 분포), `most_common_even_count`,
  `avg_even`, `balanced_*`(3:3 균형) 등을 한 응답에 묶어 제공하며, 전용 페이지는
  홀짝 비율(`odd_even.html`)을 보여준다.
- SPEC-074(`get_even_count_stats`): **짝수 개수 단일 지표**에 집중한 전용 분석.
  SPEC-073(3의 배수 개수)과 동일한 단일 지표 형식의 응답 구조(`high_even_pct`
  포함, 각 버킷이 `{count, pct}` 중첩)와 **전용 라우트/페이지/네비 탭**
  (`/api/stats/even_count`, `/stats/even-count`, `even_count.html`, "짝수개수")을
  제공한다.

차이점 요약: (1) SPEC-074는 `high_even_pct`(짝수 개수 >= 3 비율)를 추가 제공하나
SPEC-061에는 없다. (2) 응답 형태가 다르다(SPEC-074는 버킷별 `{count, pct}` 중첩
dict, SPEC-061은 분포 dict와 분포 pct dict를 병렬로 보유). (3) UI 진입점이 다르다
(SPEC-074 전용 "짝수개수" 탭 vs SPEC-061 홀짝 비율 탭). 신규 심볼은 모두 비중복으로
검증되었다.

### 응답 구조

```python
{
    "total_draws": int,
    "avg_even_count": float,     # 전체 회차 짝수 개수 평균, 2자리 반올림
    "most_common_count": int,    # 가장 자주 등장한 개수(0~6); 동률 시 더 작은 값 우선
    "high_even_pct": float,      # 짝수 개수 >= 3 회차 비율(%), 2자리 반올림
    "even_count_distribution": {
        "0": {"count": int, "pct": float},
        "1": {"count": int, "pct": float},
        "2": {"count": int, "pct": float},
        "3": {"count": int, "pct": float},
        "4": {"count": int, "pct": float},
        "5": {"count": int, "pct": float},
        "6": {"count": int, "pct": float},
    },
}
```

`even_count_distribution` 은 항상 7개 키를 모두 포함한다(누락 구간은 `count=0`,
`pct=0.0` 으로 zero-fill). 빈 draws → 모든 값 0, 7개 키 존재,
`most_common_count=0`, `avg_even_count=0.0`, `high_even_pct=0.0`.

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·기존 통계 로직을 변경하지 않고
`lotto/web/data.py` 의 확장 패턴(SPEC-073)을 그대로 따른다. 결과는 메모리에
캐시하며 DB에 영속화하지 않는다.

## 용어 정의

| 용어 | 정의 |
|------|------|
| 짝수 (even number) | `n % 2 == 0` 인 번호 (1~45 범위에서 22개: 2,4,...,44) |
| 짝수 개수 (even count) | 한 회차 6개 본번호 중 짝수인 번호의 개수 `sum(1 for n in numbers if n % 2 == 0)` (0~6) |
| 개수 키 (count key) | 짝수 개수가 속하는 7개 고정 키 중 하나 (`"0"`~`"6"`) |
| high_even | 짝수 개수가 3 이상인 상태 (6개 중 절반 이상이 짝수) |
| 본번호 (main numbers) | `draw.numbers()` 가 반환하는 6개 번호 (보너스 제외) |

## 요구사항 (EARS)

### 기능 요구사항

**REQ-EC-001** [Ubiquitous]
The system SHALL compute, for each historical draw, the even count defined as
the number of main numbers (the bonus number excluded) that are divisible by 2:
`even_count = sum(1 for n in draw.numbers() if n % 2 == 0)`.

**REQ-EC-002** [Event-Driven]
WHEN the `/api/stats/even_count` endpoint is called THEN the system SHALL return
a JSON response containing `total_draws`, `avg_even_count`, `most_common_count`,
`high_even_pct`, and `even_count_distribution` — where `even_count_distribution`
is a nested dict keyed by the 7 string keys `"0"`, `"1"`, `"2"`, `"3"`, `"4"`,
`"5"`, `"6"`, each mapping to `count` and `pct`.

**REQ-EC-003** [Event-Driven]
WHEN the `/stats/even-count` page is requested THEN the system SHALL render an
HTML page whose navigation/heading contains the Korean text "짝수개수", using the
same stats dict.

**REQ-EC-004** [Ubiquitous]
The system SHALL always include all 7 count keys (`"0"`..`"6"`) in
`even_count_distribution` (zero-filled when a count is absent from the data).
Each draw's even count SHALL be assigned to exactly one bucket equal to its
computed count.

**REQ-EC-005** [Event-Driven]
WHEN `invalidate_cache()` is called THEN `_even_count_cache` SHALL be cleared.

**REQ-EC-006** [Ubiquitous]
The system SHALL determine `most_common_count` as the count key with the highest
`count`; on a tie, the smaller even count (earlier in the fixed key order
`"0"`..`"6"`) SHALL win.

**REQ-EC-007** [Ubiquitous]
The system SHALL compute `high_even_pct` as the percentage of draws whose even
count is greater than or equal to 3.

**REQ-EC-008** [Ubiquitous]
The system SHALL compute `avg_even_count` as the arithmetic mean of all per-draw
even counts.

### 비기능 요구사항

**REQ-EC-NF-001** [State-Driven]
IF the draws list is empty THEN the system SHALL return all-zero stats with all 7
keys present (each `count=0`, `pct=0.0`), `most_common_count=0`,
`avg_even_count=0.0`, and `high_even_pct=0.0` without raising an exception.

**REQ-EC-NF-002** [Unwanted]
The system SHALL NOT include the bonus number in the even count computation.

**REQ-EC-NF-003** [Unwanted]
The system SHALL NOT modify `analyzer.py`, `models.py`, `recommender.py`, or
`simulator.py`. Only `lotto/web/` layer files are extended.

**REQ-EC-NF-004** [Unwanted]
The system SHALL NOT modify or reuse the existing SPEC-061 `get_odd_even_stats`
function, `_odd_even_cache`, or the odd/even ratio page; SPEC-074 introduces its
own independent symbols.

**REQ-EC-NF-005** [Ubiquitous]
Numeric ratio/average fields (`avg_even_count`, `high_even_pct`, and each bucket
`pct`) SHALL be rounded to 2 decimal places.

**REQ-EC-NF-006** [Ubiquitous]
The implementation SHALL be Python 3.9 compatible (no walrus `:=`,
no `zip(strict=True)`, no `match-case`) and server-rendered only (no client JS).

## 인수 기준

상세 인수 기준은 [acceptance.md](acceptance.md) 참조 (AC-074-001 ~ AC-074-020).

## Exclusions (What NOT to Build)

- SPEC-061(`get_odd_even_stats`, 홀짝 비율 분포)과의 통합·병합 — 별개 기능으로 유지
- 홀수 개수 분포 분석 (짝수 개수만 다룸; 홀수는 SPEC-061 영역)
- 다른 배수(3의 배수·5의 배수 등) 개수 분석 — SPEC-073 등 별도 SPEC 대상
- 어떤 짝수(2·4·6·... 중 무엇)가 포함되었는지에 대한 세부 분해 (포함된 짝수 값 목록 등)
- 추천 엔진 연동 (짝수 개수 기반 가중치·필터 추가 금지)
- 짝수 개수 예측 모델·시계열 추세 분석
- DB 영속화 (메모리 캐시만 사용)
- 윈도(recent_n) 기반 부분 집계
- 보너스 번호를 포함한 7개 조합의 짝수 개수 계산
- 코어 모듈(`analyzer.py`/`models.py`/`recommender.py`/`simulator.py`) 수정

## 전제조건

- Python 3.9+ 환경 (walrus `:=`, `zip(strict=True)`, `match-case` 사용 금지)
- SPEC-073 패턴이 `lotto/web/data.py` 에 존재함
- 짝수 개수 산출에 `draw.numbers()` (6개 메인 번호) 사용
- 신규 심볼(`get_even_count_stats`, `_even_count_cache`, `/api/stats/even_count`,
  `/stats/even-count`, `even_count.html`)은 모두 비중복으로 검증됨 (기존
  `get_even_count_stats`·`_even_count_cache` 부재 확인 완료; SPEC-061
  `get_odd_even_stats` 는 별개 심볼로 충돌 없음)
