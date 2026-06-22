---
id: SPEC-LOTTO-106
version: 1.0.0
status: completed
created: 2026-06-22
updated: 2026-06-22
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-106: 홀짝·고저 조합 매트릭스 분석 (Odd-Even × High-Low Cross Matrix Analysis)

## 1. 개요 (Overview)

각 회차 당첨 본번호 6개에 대해 홀수 개수(odd_count, 0~6)와 고번호 개수(high_count, 0~6)를
동시에 집계하여 (odd_count, high_count) 2차원 교차 빈도 매트릭스를 생성한다. 기존 홀짝 분석
(odd-even)과 고저 분석(high-low)이 각 축을 독립적으로 보던 것과 달리, 본 기능은 두 축의
결합 분포를 하나의 매트릭스로 제시하여 회차별 번호 구성 패턴을 교차로 관찰한다.

- "고번호(high)"는 23보다 큰 번호(24~45)를 의미한다. 23 이하(1~23)는 저번호(low)다.
- 분석은 통계 관찰용이며 당첨 예측력을 보장하지 않는다.

## 2. 용어 정의 (Definitions)

- `odd_count`: 한 회차 본번호 6개 중 홀수의 개수 (0~6)
- `high_count`: 한 회차 본번호 6개 중 고번호(번호 > 23)의 개수 (0~6)
- `matrix`: (odd_count, high_count) 조합별 회차 수. 키는 `"odd_{i}_high_{j}"` 형식, 7×7=49개
- `top_combinations`: 빈도 상위 top_n개 (odd_count, high_count) 조합
- `marginal_odd` / `marginal_high`: odd_count / high_count 각 값(0~6)의 주변 빈도
- `avg_odd` / `avg_high`: 전체 회차에 대한 odd_count / high_count 평균

## 3. 기능 요구사항 (EARS Requirements)

### REQ-CROSS-001 (Ubiquitous)
The SYSTEM SHALL provide a function `get_cross_pattern_stats(draws, top_n=10)` that
analyzes the cross distribution of odd-number count and high-number count per draw.

### REQ-CROSS-002 (Event-driven)
When the SYSTEM receives draws data, it SHALL compute for each draw `odd_count`
(number of odd numbers among the 6 main numbers, range 0-6) and `high_count`
(number of high numbers — numbers greater than 23 — among the 6 main numbers, range 0-6).

### REQ-CROSS-003 (Event-driven)
When odd_count and high_count are computed for all draws, the SYSTEM SHALL produce a
cross-frequency `matrix`: for each (odd_count, high_count) pair the count of draws that
had that combination. The matrix SHALL contain all 49 keys `"odd_{i}_high_{j}"`
for i in 0..6 and j in 0..6, with absent combinations set to 0.

### REQ-CROSS-004 (Event-driven)
When the matrix is computed, the SYSTEM SHALL produce `top_combinations`: the top_n most
frequent (odd_count, high_count) pairs, sorted by count descending, with ties broken by
smaller odd_count first, then smaller high_count first. Each item SHALL include
`odd_count`, `high_count`, `count`, and `pct` (percentage of total_draws, rounded 2dp).

### REQ-CROSS-005 (Event-driven)
When draws are processed, the SYSTEM SHALL compute `marginal_odd`: the frequency of each
odd_count value (0-6), as a mapping with string keys "0".."6".

### REQ-CROSS-006 (Event-driven)
When draws are processed, the SYSTEM SHALL compute `marginal_high`: the frequency of each
high_count value (0-6), as a mapping with string keys "0".."6".

### REQ-CROSS-007 (Event-driven)
When draws are processed, the SYSTEM SHALL compute `avg_odd` (mean odd_count across all
draws, rounded to 2 decimal places) and `avg_high` (mean high_count across all draws,
rounded to 2 decimal places).

### REQ-CROSS-008 (Unwanted)
If the input is None or empty, the SYSTEM SHALL return a zero-filled structure
(total_draws=0, 49 matrix keys all 0, empty top_combinations, marginal maps all 0,
avg_odd=0.0, avg_high=0.0) and SHALL NOT raise.

### REQ-CROSS-009 (Ubiquitous)
The result SHALL include a `disclaimer` string indicating the analysis is for
statistical reference only and does not guarantee predictive power.

### REQ-CROSS-010 (Ubiquitous)
The SYSTEM SHALL expose `GET /api/stats/cross-pattern?top_n=10` returning the analysis
result as JSON. `top_n` SHALL be validated as an integer in the range 1..49 (default 10);
out-of-range values SHALL yield HTTP 422.

### REQ-CROSS-011 (Ubiquitous)
The SYSTEM SHALL expose `GET /stats/cross-pattern` rendering the `cross_pattern.html`
template server-side with `active_tab` = `cross_pattern`.

### REQ-CROSS-012 (Ubiquitous)
The navigation SHALL include a tab `('/stats/cross-pattern', 'cross_pattern', '조합 매트릭스')`.

## 4. 반환 구조 (Return Structure)

```
{
  "total_draws": int,
  "top_n": int,
  "matrix": {                  # 키는 "odd_{i}_high_{j}" (i,j in 0..6), 49개
    "odd_0_high_0": int,
    ...
  },
  "top_combinations": [        # 상위 top_n개
    {"odd_count": int, "high_count": int, "count": int, "pct": float}
  ],
  "marginal_odd": {"0": int, "1": int, ..., "6": int},
  "marginal_high": {"0": int, "1": int, ..., "6": int},
  "avg_odd": float,
  "avg_high": float,
  "disclaimer": str
}
```

## 5. 비기능 요구사항 (Non-Functional Requirements)

- NFR-CROSS-001: Python 3.9 호환 (match/case, zip(strict=True) 미사용)
- NFR-CROSS-002: 본번호는 `draw.numbers()` 메서드 호출로 취득 (오름차순 list[int])
- NFR-CROSS-003: 코어 모듈(lotto.core/models/config 등) 미수정
- NFR-CROSS-004: 동일 입력에 대해 결정적(deterministic) 결과
- NFR-CROSS-005: 서버 렌더링(JS 비의존), Tailwind CSS, 다크 모드 지원

## 6. 면책 고지 (Disclaimer)

본 분석은 과거 당첨 데이터의 홀짝·고저 결합 분포를 통계적으로 관찰하기 위한 참고 자료이며,
미래 당첨 번호의 예측력을 보장하지 않습니다. 로또는 매 회차 독립적인 무작위 추첨입니다.
