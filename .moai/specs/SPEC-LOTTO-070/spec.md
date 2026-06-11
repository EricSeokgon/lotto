---
id: SPEC-LOTTO-070
version: 1.0.0
status: Completed
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-070: AC값(산술 복잡도) 분포 분석

## HISTORY

- 2026-06-11 (v1.0.0): 구현 완료. 35 tests 추가 (1629→1664). 커밋 c24747c.
- 2026-06-11 (v0.1.0): 최초 작성 (Planned). 회차별 본번호 6개(보너스 제외)의
  모든 쌍 C(6,2)=15개에 대한 절대 차이 중 **서로 다른(distinct) 값의 개수** 를
  AC값(Arithmetic Complexity)으로 정의하고, 전체 이력에 대해 AC값 0~14의 전 구간
  분포를 산출하는 읽기 전용 통계 기능으로 정의. SPEC-065·066·067·068·069의
  `data.py` 확장 패턴을 그대로 따른다.

## 개요

각 회차의 당첨번호 6개(보너스 제외)에 대해 **AC값(산술 복잡도, Arithmetic
Complexity)** 을 계산한 뒤, 전체 이력에 대해 AC값 0~14 전 구간의 분포를 분석한다.
AC값은 한 회차 번호 조합이 얼마나 "다양한 간격"으로 구성되어 있는지를 나타내는
지표로, 한국 로또 전략에서 조합의 분산도를 평가할 때 널리 쓰인다.

### AC값(Arithmetic Complexity) 정의와 예시

한 회차의 6개 번호에서 만들 수 있는 모든 쌍은 C(6,2)=15개다. 각 쌍의 절대 차이
`|a-b|` 를 구한 뒤, **서로 다른 차이값의 개수** 를 센 것이 AC값이다.

차이값의 최댓값은 (1부터 45 사이) 최대 44이다. 6개 번호의 distinct 차이 개수는
대부분 0~14 구간에 들어가지만, 매우 넓게 흩어진 일부 조합(예: `[5,8,9,17,32,37]`,
`[1,2,4,8,16,32]`)은 distinct 차이가 **15개**까지 나올 수 있다.

[HARD] 분포 키 범위 결정 (range clamping): 본 SPEC의 응답 구조는 `"0"`~`"14"`
**15개 키로 고정**한다. AC값이 14를 초과(=15)하는 회차는 마지막 키 `"14"` 에
합산하는 **오버플로 버킷** 으로 처리한다. 즉 분포 집계 시 `bucket = min(ac, 14)`
규칙을 적용한다. 단, `avg_ac_value` 와 `high_diversity_pct`(AC>=9 판정)는 clamp
이전의 **원본 AC값** 으로 계산한다.

근거: 요청 명세가 `"0".."14"` 15개 키를 고정 구조로 규정하므로 키 집합을 늘리지
않되, `dist_counts[str(15)]` KeyError 를 방지하기 위해 14를 오버플로 버킷으로
사용한다 (Agent "Verify, Don't Assume": 실제 1~45 범위에서 AC=15 발생을 코드로
검증함).

예시: 번호 `[1, 2, 3, 10, 11, 12]`

| 쌍 | 차이 | 쌍 | 차이 | 쌍 | 차이 |
|------|------|------|------|------|------|
| (1,2)   | 1 | (2,3)   | 1 | (3,11) | 8 |
| (1,3)   | 2 | (2,10)  | 8 | (3,12) | 9 |
| (1,10)  | 9 | (2,11)  | 9 | (10,11)| 1 |
| (1,11)  | 10| (2,12)  | 10| (10,12)| 2 |
| (1,12)  | 11| (3,10)  | 7 | (11,12)| 1 |

distinct 차이 집합 = `{1, 2, 7, 8, 9, 10, 11}` → 7개 → **AC = 7**

### AC값 범위 (0~14, 전 구간)

| AC값 (key) | 의미 |
|------------|------|
| `"0"` ~ `"8"`  | 상대적으로 간격이 단조로운(중복 차이가 많은) 조합 |
| `"9"` ~ `"13"` | 간격이 다양한(distinct 차이가 많은) 조합 — "고다양성" |
| `"14"`         | distinct 차이 14개 **이상** (AC>=15 오버플로 포함) |

`high_diversity_pct` 는 AC값 `>= 9` 인 회차의 비율로, 한국 로또 분석에서 널리
쓰이는 임계값(9)을 사용한다.

### 응답 구조

```python
{
    "total_draws": int,
    "avg_ac_value": float,          # 전체 회차 AC값 평균, 2자리 반올림
    "most_common_ac": int,          # 가장 자주 등장한 AC값 (정수)
    "high_diversity_pct": float,    # AC값 >= 9 회차 비율(%), 2자리 반올림
    "ac_distribution": {
        "0":  {"count": int, "pct": float},
        "1":  {"count": int, "pct": float},
        ...
        "14": {"count": int, "pct": float},
    },
}
```

`ac_distribution` 은 항상 `"0"`~`"14"` 15개 키를 모두 포함한다(누락 구간은
`count=0`, `pct=0.0` 으로 zero-fill). 빈 draws → 모든 값 0, 15개 키 존재,
`most_common_ac=0`.

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·통계 분석 로직을 변경하지 않고
`data.py`의 확장 패턴(SPEC-065·066·067·068·069)을 그대로 따른다. 결과는 메모리에
캐시하며 DB에 영속화하지 않는다.

## 용어 정의

| 용어 | 정의 |
|------|------|
| AC값 (Arithmetic Complexity) | 한 회차 6개 번호의 C(6,2)=15개 쌍에 대한 절대 차이 중 distinct 값의 개수 (0~14) |
| distinct 차이 | `{abs(a-b) for 모든 쌍 (a,b)}` 집합의 원소 |
| high diversity | AC값이 임계값 9 이상인 상태 |
| 본번호 (main numbers) | `draw.numbers()` 가 반환하는 6개 번호 (보너스 제외) |

## 요구사항 (EARS)

### 기능 요구사항

**REQ-AC-001** [Ubiquitous]
The system SHALL compute, for each historical draw, the AC value defined as the
number of distinct absolute pairwise differences among the 6 main numbers
(the bonus number excluded): `len({abs(a-b) for i,a in enumerate(nums) for b in nums[i+1:]})`.

**REQ-AC-002** [Event-Driven]
WHEN the `/api/stats/ac_value` endpoint is called THEN the system SHALL return a
JSON response containing `total_draws`, `avg_ac_value`, `most_common_ac`,
`high_diversity_pct`, and `ac_distribution` — where `ac_distribution` is a nested
dict keyed by the 15 string keys `"0"`..`"14"`, each mapping to `count` and `pct`.

**REQ-AC-003** [Event-Driven]
WHEN the `/stats/ac-value` page is requested THEN the system SHALL render an HTML
page whose title and heading contain the text "AC", using the same stats dict.

**REQ-AC-004** [Ubiquitous]
The system SHALL always include all 15 keys (`"0"` through `"14"`) in
`ac_distribution` (zero-filled when an AC value is absent from the data). The key
`"14"` SHALL act as an overflow bucket: any draw whose raw AC value is 14 or greater
(`min(ac, 14)`) is counted under `"14"`.

**REQ-AC-005** [Event-Driven]
WHEN `invalidate_cache()` is called THEN `_ac_value_cache` SHALL be cleared.

**REQ-AC-006** [Ubiquitous]
The system SHALL determine `most_common_ac` as the AC value with the highest `count`;
on a tie, the smaller AC value (integer) SHALL win.

**REQ-AC-007** [Ubiquitous]
The system SHALL compute `high_diversity_pct` as the percentage of draws whose
**raw** AC value (before overflow clamping) is greater than or equal to 9.

**REQ-AC-008** [Ubiquitous]
The system SHALL compute `avg_ac_value` from the **raw** AC values (before overflow
clamping to bucket `"14"`).

### 비기능 요구사항

**REQ-AC-NF-001** [State-Driven]
IF the draws list is empty THEN the system SHALL return all-zero stats with all 15
keys present (each `count=0`, `pct=0.0`), `most_common_ac=0`, `avg_ac_value=0.0`,
and `high_diversity_pct=0.0` without raising an exception.

**REQ-AC-NF-002** [Unwanted]
The system SHALL NOT include the bonus number in AC value computation.

**REQ-AC-NF-003** [Unwanted]
The system SHALL NOT modify `analyzer.py`, `models.py`, `recommender.py`, or
`simulator.py`. Only `lotto/web/` layer files are extended.

**REQ-AC-NF-004** [Ubiquitous]
Numeric ratio fields (`avg_ac_value`, `high_diversity_pct`, and each bucket `pct`)
SHALL be rounded to 2 decimal places.

**REQ-AC-NF-005** [Ubiquitous]
The implementation SHALL be Python 3.9 compatible (no walrus `:=`,
no `zip(strict=True)`, no `match-case`) and server-rendered only (no client JS).

## 인수 기준

상세 인수 기준은 [acceptance.md](acceptance.md) 참조 (AC-070-001 ~ AC-070-024).

## Exclusions (What NOT to Build)

- 추천 엔진 연동 (AC값 기반 가중치·필터 추가 금지)
- AC값 임계값(9)의 사용자 정의 (커스텀 임계값 설정 UI 금지)
- AC값 예측 모델·시계열 추세 분석
- DB 영속화 (메모리 캐시만 사용)
- 윈도(recent_n) 기반 부분 집계
- 보너스 번호를 포함한 7개 조합의 AC값 계산
- AC값 외 다른 복잡도 지표(분산, 표준편차 등) — 별도 SPEC 대상

## 전제조건

- Python 3.9+ 환경 (walrus `:=`, `zip(strict=True)`, `match-case` 사용 금지)
- SPEC-065, SPEC-066, SPEC-067, SPEC-068, SPEC-069 패턴이 `data.py`에 존재함
- AC값 산출에 `draw.numbers()` (6개 메인 번호) 사용
- 신규 심볼(`get_ac_value_stats`, `_ac_value_cache`, `/api/stats/ac_value`,
  `/stats/ac-value`, `ac_value.html`)은 모두 비중복으로 검증됨
