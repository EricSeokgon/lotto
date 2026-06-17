---
id: SPEC-LOTTO-073
version: 1.0.0
status: completed
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-073: 3의 배수 포함 개수 분포 분석

## HISTORY

- 2026-06-12 (v1.0.0): 구현 완료. 30개 테스트 추가. commit a91d73e
- 2026-06-12 (v0.1.0): 최초 작성 (Planned). 회차별 본번호 6개(보너스 제외) 중
  **3의 배수(3, 6, 9, ..., 45)에 해당하는 번호의 개수**(0~6)를 산출하고, 전체
  이력에 대해 7개 구간(`"0"`~`"6"`)의 분포를 분석하는 읽기 전용 통계 기능으로
  정의. SPEC-071(중앙값)·SPEC-072(끝자리 유니크)의 `data.py` 확장 패턴을 그대로
  따른다.

## 개요

각 회차의 당첨번호 6개(보너스 제외)에 대해 각 번호가 **3의 배수인지**(`n % 3 == 0`)
판별한 뒤, 한 회차 안에 3의 배수가 **몇 개** 포함되어 있는지를 센다. 이 "3의 배수
개수"는 0(3의 배수가 하나도 없음)부터 6(여섯 번호가 모두 3의 배수)까지의 정수 값을
가진다. 전체 이력에 대해 이 개수가 0~6 중 어디에 분포하는지를 분석하여, 번호 조합이
3의 배수를 얼마나 포함하는 경향이 있는지를 한 값으로 요약한다.

### 1~45 범위의 3의 배수

1~45 범위에서 3의 배수는 다음 15개이다(전체 45개 중 33.3%):

```
3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45
```

따라서 한 회차의 본번호 6개가 무작위라면 3의 배수 개수의 기대값은 약
`6 * 15/45 = 2.0` 부근이다.

### 3의 배수 개수 정의와 예시

한 회차의 3의 배수 개수는 `sum(1 for n in draw.numbers() if n % 3 == 0)` 이다.
6개 번호 각각에 대해 3으로 나누어떨어지는지 검사하고 그 개수를 센다.

- 예시: 번호 `[3, 7, 12, 20, 33, 44]`
  - 3의 배수 = `{3, 12, 33}` → **3개**
- 예시: 번호 `[1, 2, 4, 5, 7, 8]`
  - 3의 배수 없음 → **0개**
- 예시: 번호 `[3, 6, 9, 12, 15, 18]`
  - 여섯 번호 모두 3의 배수 → **6개**

### 값의 범위 (0~6, 7개 버킷)

[HARD] 3의 배수 개수는 항상 **0 이상 6 이하**이다. 번호가 6개이므로 최소 0개
(3의 배수 전무), 최대 6개(모두 3의 배수)이다. 따라서 분포 키는 `"0"`, `"1"`,
`"2"`, `"3"`, `"4"`, `"5"`, `"6"` 의 **7개로 고정**하며, 미관측 구간은
`count=0` / `pct=0.0` 으로 zero-fill 한다.

- 끝자리 유니크(SPEC-072, 1~6 / 6키)와 달리 본 SPEC은 **0을 포함한 0~6 / 7키**
  임에 유의한다. 빈 회차의 기본 최빈값도 `0`(072의 `1` 아님)이다.

### high_mult3_pct (3의 배수 다수 비율)

`high_mult3_pct` 는 3의 배수 개수가 **3 이상**(즉 6개 번호의 절반 이상이 3의
배수)인 회차의 비율(%)이다. 3의 배수에 "치우친" 조합이 얼마나 자주 나오는지를
측정한다.

### 응답 구조

```python
{
    "total_draws": int,
    "avg_mult3_count": float,     # 전체 회차 3의 배수 개수 평균, 2자리 반올림
    "most_common_count": int,     # 가장 자주 등장한 개수(0~6); 동률 시 더 작은 값 우선
    "high_mult3_pct": float,      # 3의 배수 개수 >= 3 회차 비율(%), 2자리 반올림
    "mult3_distribution": {
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

`mult3_distribution` 은 항상 7개 키를 모두 포함한다(누락 구간은 `count=0`,
`pct=0.0` 으로 zero-fill). 빈 draws → 모든 값 0, 7개 키 존재,
`most_common_count=0`, `avg_mult3_count=0.0`, `high_mult3_pct=0.0`.

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·기존 통계 로직을 변경하지 않고
`lotto/web/data.py` 의 확장 패턴(SPEC-071·072)을 그대로 따른다. 결과는 메모리에
캐시하며 DB에 영속화하지 않는다.

## 용어 정의

| 용어 | 정의 |
|------|------|
| 3의 배수 (multiple of 3) | `n % 3 == 0` 인 번호 (1~45 범위에서 15개: 3,6,...,45) |
| 3의 배수 개수 (mult3 count) | 한 회차 6개 본번호 중 3의 배수인 번호의 개수 `sum(1 for n in numbers if n % 3 == 0)` (0~6) |
| 개수 키 (count key) | 3의 배수 개수가 속하는 7개 고정 키 중 하나 (`"0"`~`"6"`) |
| high_mult3 | 3의 배수 개수가 3 이상인 상태 (6개 중 절반 이상이 3의 배수) |
| 본번호 (main numbers) | `draw.numbers()` 가 반환하는 6개 번호 (보너스 제외) |

## 요구사항 (EARS)

### 기능 요구사항

**REQ-M3-001** [Ubiquitous]
The system SHALL compute, for each historical draw, the multiple-of-3 count
defined as the number of main numbers (the bonus number excluded) that are
divisible by 3: `mult3_count = sum(1 for n in draw.numbers() if n % 3 == 0)`.

**REQ-M3-002** [Event-Driven]
WHEN the `/api/stats/mult3` endpoint is called THEN the system SHALL return a
JSON response containing `total_draws`, `avg_mult3_count`, `most_common_count`,
`high_mult3_pct`, and `mult3_distribution` — where `mult3_distribution` is a
nested dict keyed by the 7 string keys `"0"`, `"1"`, `"2"`, `"3"`, `"4"`, `"5"`,
`"6"`, each mapping to `count` and `pct`.

**REQ-M3-003** [Event-Driven]
WHEN the `/stats/mult3` page is requested THEN the system SHALL render an HTML
page whose navigation/heading contains the Korean text "3배수", using the same
stats dict.

**REQ-M3-004** [Ubiquitous]
The system SHALL always include all 7 count keys (`"0"`..`"6"`) in
`mult3_distribution` (zero-filled when a count is absent from the data). Each
draw's mult3 count SHALL be assigned to exactly one bucket equal to its computed
count.

**REQ-M3-005** [Event-Driven]
WHEN `invalidate_cache()` is called THEN `_mult3_cache` SHALL be cleared.

**REQ-M3-006** [Ubiquitous]
The system SHALL determine `most_common_count` as the count key with the highest
`count`; on a tie, the smaller mult3 count (earlier in the fixed key order
`"0"`..`"6"`) SHALL win.

**REQ-M3-007** [Ubiquitous]
The system SHALL compute `high_mult3_pct` as the percentage of draws whose mult3
count is greater than or equal to 3.

**REQ-M3-008** [Ubiquitous]
The system SHALL compute `avg_mult3_count` as the arithmetic mean of all per-draw
mult3 counts.

### 비기능 요구사항

**REQ-M3-NF-001** [State-Driven]
IF the draws list is empty THEN the system SHALL return all-zero stats with all 7
keys present (each `count=0`, `pct=0.0`), `most_common_count=0`,
`avg_mult3_count=0.0`, and `high_mult3_pct=0.0` without raising an exception.

**REQ-M3-NF-002** [Unwanted]
The system SHALL NOT include the bonus number in the multiple-of-3 computation.

**REQ-M3-NF-003** [Unwanted]
The system SHALL NOT modify `analyzer.py`, `models.py`, `recommender.py`, or
`simulator.py`. Only `lotto/web/` layer files are extended.

**REQ-M3-NF-004** [Ubiquitous]
Numeric ratio/average fields (`avg_mult3_count`, `high_mult3_pct`, and each
bucket `pct`) SHALL be rounded to 2 decimal places.

**REQ-M3-NF-005** [Ubiquitous]
The implementation SHALL be Python 3.9 compatible (no walrus `:=`,
no `zip(strict=True)`, no `match-case`) and server-rendered only (no client JS).

## 인수 기준

상세 인수 기준은 [acceptance.md](acceptance.md) 참조 (AC-073-001 ~ AC-073-020).

## Exclusions (What NOT to Build)

- 다른 배수(2의 배수·5의 배수·7의 배수 등) 개수 분석 — 별도 SPEC 대상
- 어떤 3의 배수(3·6·9·... 중 무엇)가 포함되었는지에 대한 세부 분해 (포함된 3의
  배수 값 목록 등)
- 추천 엔진 연동 (3의 배수 개수 기반 가중치·필터 추가 금지)
- 3의 배수 개수 예측 모델·시계열 추세 분석
- DB 영속화 (메모리 캐시만 사용)
- 윈도(recent_n) 기반 부분 집계
- 보너스 번호를 포함한 7개 조합의 3의 배수 개수 계산
- 코어 모듈(`analyzer.py`/`models.py`/`recommender.py`/`simulator.py`) 수정

## 전제조건

- Python 3.9+ 환경 (walrus `:=`, `zip(strict=True)`, `match-case` 사용 금지)
- SPEC-071, SPEC-072 패턴이 `lotto/web/data.py` 에 존재함
- 3의 배수 개수 산출에 `draw.numbers()` (6개 메인 번호) 사용
- 신규 심볼(`get_mult3_stats`, `_mult3_cache`, `/api/stats/mult3`,
  `/stats/mult3`, `mult3.html`)은 모두 비중복으로 검증됨 (기존 `get_mult3_stats`
  부재 확인 완료)
