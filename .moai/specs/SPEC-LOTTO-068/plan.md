---
id: SPEC-LOTTO-068
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-068 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR), 브라운필드 보강. 기존 동작을 보존하며 읽기 전용
통계 분석 계층만 추가한다. 데이터 계층(`get_range_dist_stats`) → API 계층
(`/api/stats/range_dist`) → 페이지/템플릿 계층(`/stats/range_dist`) 순으로
각 계층마다 실패 테스트 작성 후 최소 구현.

핵심 재사용: `data.py`의 캐시 패턴
(SPEC-066: `get_prime_sum_stats`, SPEC-067: `get_total_sum_stats`).
단, 본 SPEC은 응답이 **중첩 딕셔너리(`range_stats`)** 구조라는 점이 다르다.

## 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `_range_dist_cache`, `_RANGES`, `_number_range()`, `get_range_dist_stats()`, `invalidate_cache()` 수정 | +60 LOC |
| `lotto/web/routes/pages.py` | `stats_range_dist_page()` 핸들러 | +10 LOC |
| `lotto/web/routes/api.py` | `get_range_dist()` 핸들러 | +8 LOC |
| `lotto/web/templates/range_dist.html` | 통계 페이지 템플릿 | +95 LOC |
| `lotto/web/templates/base.html` | nav 링크 추가 (데스크탑+모바일) | +2 LOC |
| `tests/test_range_dist_analysis.py` | 테스트 파일 (20+ 케이스) | +220 LOC |

## 구현 단계

### 단계 1: data.py — 통계 계산 함수 (REQ-068-F-001, F-004, F-005, F-006, NF-001~004)

```
1-1. _range_dist_cache 딕셔너리 변수 선언 (키: str(len(draws)))
1-2. _RANGES 상수 정의: ["1-9", "10-19", "20-29", "30-39", "40-45"]
1-3. _number_range(n) 헬퍼 함수: 번호 → 구간 키 분류
1-4. get_range_dist_stats(draws) 구현
     - 캐시 히트 체크 (key: str(len(draws)))
     - draws 빈 경우 → 0-값 딕셔너리 반환 (5 구간 zero-fill, most_covered_range="")
     - 각 draw.numbers()의 6개 번호를 구간별로 분류·집계
       · total_count[r] += 1 (번호당)
       · seen_ranges 집합으로 회차당 1회만 draw_count[r] += 1
     - most_covered_range 산출 (draw_count 최댓값, 동점 시 _RANGES 앞선 구간)
     - avg_per_draw / pct_of_numbers / draw_pct 계산 (2자리 반올림)
     - 결과 캐시 저장 후 반환
1-5. invalidate_cache()에 _range_dist_cache.clear() 추가
```

### 단계 2: routes/pages.py, routes/api.py — 라우트 핸들러

```
2-1. pages.py에 stats_range_dist_page() 추가
     GET /stats/range_dist → _render(request, "range_dist.html", {...})
2-2. api.py에 get_range_dist() 추가
     GET /api/stats/range_dist → wd.get_range_dist_stats(wd.get_draws())
```

### 단계 3: templates — HTML 페이지

```
3-1. range_dist.html 생성 (SPEC-067 total_sum.html 패턴 참조)
     - 빈 상태 처리: {% if stats.total_draws == 0 %}
     - 요약 카드: 총 회차, 최다 커버 구간(most_covered_range)
     - 구간 분포 테이블: 5개 행 (range_stats 중첩 dict 순회)
       · 컬럼: 구간 / total_count / draw_count / avg_per_draw / pct_of_numbers / draw_pct
     - 제목·헤딩에 "구간" 텍스트 포함
     - Tailwind CSS 다크모드 지원
3-2. base.html nav에 "구간" 링크 추가 (데스크탑 + 모바일 드롭다운)
```

### 단계 4: tests — 테스트 (20+ 케이스)

```
테스트 파일: tests/test_range_dist_analysis.py

필수 케이스:
- 빈 데이터: 모든 0, 5 구간 존재, most_covered_range=""
- 단일 구간 회차([1..6] 전부 "1-9"): total_count=6
- 단일 구간 회차([40..45] 전부 "40-45"): total_count=6
- 다중 구간 회차([5,15,25,35,42,43]): 5 구간 정확 집계
- 보너스 번호 제외 검증
- avg_per_draw / pct_of_numbers / draw_pct 정확성
- draw_count 정확성 및 draw_count <= total_draws 불변식
- most_covered_range 및 동점 처리
- pct_of_numbers 합계 ≈ 100.0
- 구간 경계값(9→"1-9", 10→"10-19")
- 캐시 히트 (동일 len)
- 캐시 미스 (다른 len)
- 캐시 무효화 (invalidate_cache)
- API 엔드포인트 200 + JSON 구조
- 페이지 엔드포인트 200 ("구간" 포함)
- 실제 데이터 smoke test
```

## 핵심 알고리즘

```python
_RANGES = ["1-9", "10-19", "20-29", "30-39", "40-45"]
_range_dist_cache: dict[str, Any] = {}

def _number_range(n: int) -> str:
    if n <= 9:   return "1-9"
    if n <= 19:  return "10-19"
    if n <= 29:  return "20-29"
    if n <= 39:  return "30-39"
    return "40-45"

def get_range_dist_stats(draws: list) -> dict:
    key = str(len(draws))
    if key in _range_dist_cache:
        return _range_dist_cache[key]
    if not draws:
        result = {
            "total_draws": 0,
            "most_covered_range": "",
            "range_stats": {
                r: {"total_count": 0, "draw_count": 0, "avg_per_draw": 0.0,
                    "pct_of_numbers": 0.0, "draw_pct": 0.0}
                for r in _RANGES
            },
        }
        _range_dist_cache[key] = result
        return result

    total_count = {r: 0 for r in _RANGES}
    draw_count = {r: 0 for r in _RANGES}
    n = len(draws)

    for draw in draws:
        seen_ranges = set()
        for num in draw.numbers():
            r = _number_range(num)
            total_count[r] += 1
            seen_ranges.add(r)
        for r in seen_ranges:
            draw_count[r] += 1

    most_covered = max(_RANGES, key=lambda r: draw_count[r])
    total_numbers = n * 6

    range_stats = {
        r: {
            "total_count": total_count[r],
            "draw_count": draw_count[r],
            "avg_per_draw": round(total_count[r] / n, 2),
            "pct_of_numbers": round(total_count[r] / total_numbers * 100, 2),
            "draw_pct": round(draw_count[r] / n * 100, 2),
        }
        for r in _RANGES
    }

    result = {
        "total_draws": n,
        "most_covered_range": most_covered,
        "range_stats": range_stats,
    }
    _range_dist_cache[key] = result
    return result
```

핵심 주의:
- `max(_RANGES, key=...)`는 동점 시 **iterable에서 먼저 나오는 원소**를 반환하므로
  `_RANGES` 순서가 그대로 tie-break 규칙(앞선 구간 우선)이 된다 (REQ-068-F-006).
- `seen_ranges` 집합으로 회차당 구간 중복 카운트를 방지한다 (draw_count 정확성).

## 배경 통계 (기대 분포)

각 구간이 균등하게 추출된다고 가정할 때 회차당 평균 개수(avg_per_draw) 기댓값:

| 구간 | 포함 개수 | 기대 avg_per_draw (= 6 × 개수/45) |
|------|-----------|-----------------------------------|
| "1-9"   | 9개  | 6 × 9/45 = 1.2 |
| "10-19" | 10개 | 6 × 10/45 ≈ 1.33 |
| "20-29" | 10개 | 6 × 10/45 ≈ 1.33 |
| "30-39" | 10개 | 6 × 10/45 ≈ 1.33 |
| "40-45" | 6개  | 6 × 6/45 = 0.8 |

→ 10개 폭의 중간 구간들이 9개·6개 구간보다 더 높은 평균을 가질 것으로 기대된다.

## 테스트 목표

- 현재 테스트 수: 1569개 (SPEC-067 완료 기준)
- 목표: +20 테스트 → 1589개 이상
- 모든 REQ 커버리지 달성
