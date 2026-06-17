# SPEC-LOTTO-099: 번호 사분위 분포 분석 (Quartile Distribution)

## Status
Completed

## Overview
로또 6/45 각 회차에서 본번호 6개가 1-45 범위를 4개 사분위 구간(Q1: 1-11, Q2: 12-22, Q3: 23-33, Q4: 34-45)으로 나눌 때 각 구간에 속하는 번호 개수(q1_count, q2_count, q3_count, q4_count)를 계산하여 분포를 분석한다. 4개 구간 커버 조합 중 가장 빈번한 패턴, 균형 분포(각 구간 1~2개씩 배정) 비율, 특정 구간 집중 비율 등을 제공함으로써 번호 대역별 배분 전략을 파악한다. 웹 UI에서 사분위 분포 차트와 핵심 통계를 제공한다.

## 사분위 구간 정의

| 구간 | 번호 범위 | 번호 수 |
|------|----------|---------|
| Q1   | 1 ~ 11   | 11개    |
| Q2   | 12 ~ 22  | 11개    |
| Q3   | 23 ~ 33  | 11개    |
| Q4   | 34 ~ 45  | 12개    |

- 번호 n의 구간 결정 공식:
  - Q1: 1 <= n <= 11
  - Q2: 12 <= n <= 22
  - Q3: 23 <= n <= 33
  - Q4: 34 <= n <= 45

## Requirements (EARS Format)

### U (Ubiquitous)
- U1: 시스템은 본번호 6개(보너스 번호 제외)만을 사용하여 사분위 분포를 계산해야 한다.
- U2: 4개 사분위 구간은 Q1(1-11), Q2(12-22), Q3(23-33), Q4(34-45)로 고정되며 변경할 수 없다.
- U3: 각 회차의 q1_count + q2_count + q3_count + q4_count = 6이어야 한다.
- U4: 조합 키는 `"{q1}-{q2}-{q3}-{q4}"` 형식의 문자열이다 (예: `"2-1-2-1"`).
- U5: 분포 딕셔너리는 관측된 조합만 포함하며, 미관측 조합은 포함하지 않는다.
- U6: 각 조합 버킷은 `{"count": int, "pct": float}` 형태를 유지한다.
- U7: 균형 분포(balanced)는 q1, q2, q3, q4 각각이 1 또는 2인 회차로 정의한다.
- U8: 특정 구간 집중(skewed)은 어느 하나의 구간에 4개 이상의 번호가 몰린 회차로 정의한다.
- U9: 캐시 키는 `str(len(draws))`이며, `invalidate_cache()` 호출 시 무효화된다.
- U10: `most_common_combination`은 count 최댓값 조합이며, 동률 시 사전순(lexicographic) 정렬 기준 앞선 값을 선택한다.

### E (Event-driven)
- E1: When `GET /api/stats/quartile_dist` is called with optional `limit` query param, the system shall return JSON with `total_draws`, `avg_q1`, `avg_q2`, `avg_q3`, `avg_q4`, `most_common_combination`, `balanced_pct`, `skewed_pct`, and `quartile_distribution` fields.
- E2: When `GET /stats/quartile-dist` page is requested, the system shall render `quartile_dist.html` template with distribution data and Korean UI labels.
- E3: When `invalidate_cache()` is called, the system shall clear `_quartile_dist_cache`.
- E4: When `limit` query param is provided and valid (positive integer), the system shall use only the most recent `limit` draws for computation.
- E5: When `limit` query param is omitted or set to 0, the system shall use all available draws.

### S (State-driven)
- S1: While draws list is None or empty, the system shall return `total_draws=0`, `avg_q1=0.0`, `avg_q2=0.0`, `avg_q3=0.0`, `avg_q4=0.0`, `most_common_combination="0-0-0-0"`, `balanced_pct=0.0`, `skewed_pct=0.0`, and `quartile_distribution={}`.
- S2: While cache exists for the same draw count key, the system shall return the cached result without recomputation.

### N (Negative)
- N1: The system shall NOT include the bonus number in quartile calculations.
- N2: The system shall NOT expose combinations with count=0 in `quartile_distribution`.
- N3: The system shall NOT raise an exception when draws is None; it shall treat None as empty list.
- N4: The system shall NOT allow `limit` values less than 0; negative limit shall be treated as 0 (use all draws).

### O (Optional)
- O1: Where a `limit` parameter is provided, the system should apply it consistently across both the API endpoint and the data function.
- O2: The template should display the top-10 most frequent combinations in a ranked table.

## Technical Design

### 함수 시그니처
```python
def get_quartile_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
```

### 캐시 변수
```python
_quartile_dist_cache: dict[str, dict] = {}
```

### 반환 구조 예시
```json
{
  "total_draws": 1178,
  "avg_q1": 1.52,
  "avg_q2": 1.51,
  "avg_q3": 1.49,
  "avg_q4": 1.48,
  "most_common_combination": "2-1-2-1",
  "balanced_pct": 68.34,
  "skewed_pct": 5.21,
  "quartile_distribution": {
    "2-1-2-1": {"count": 87, "pct": 7.39},
    "1-2-2-1": {"count": 76, "pct": 6.45},
    "...": {}
  }
}
```

### 구간 계산 로직 (Python 3.9 호환)
```python
def _get_quartile(n: int) -> int:
    if n <= 11:
        return 1
    elif n <= 22:
        return 2
    elif n <= 33:
        return 3
    else:
        return 4
```

## Files to Modify / Create

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `lotto/web/data.py` | 수정 | `_quartile_dist_cache`, `get_quartile_dist_stats()` 추가; `invalidate_cache()` 내 캐시 초기화 추가 |
| `lotto/web/routes/api.py` | 수정 | `GET /api/stats/quartile_dist` 엔드포인트 추가 |
| `lotto/web/pages.py` | 수정 | `GET /stats/quartile-dist` 페이지 라우트 추가 |
| `lotto/web/templates/quartile_dist.html` | 신규 | 사분위 분포 페이지 템플릿 |
| `lotto/web/templates/base.html` | 수정 | 사이드바 내비게이션에 "사분위 분포" 링크 추가 |
| `tests/web/test_quartile_dist_stats.py` | 신규 | TDD 테스트 파일 (최소 35개 AC 검증) |

## Constraints

- Python 3.9 호환 (match/case 미사용, zip(strict=True) 미사용)
- `# noqa: B905` 주석 불필요 (zip strict 미사용)
- 기존 SPEC 패턴(SPEC-094~098) 일관성 유지
- 한국어 UI 라벨 사용
- ruff 린트 통과 필수
