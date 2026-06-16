---
id: SPEC-LOTTO-069
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-069 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR), 브라운필드 보강. 기존 동작을 보존하며 읽기 전용
통계 분석 계층만 추가한다. 데이터 계층(`get_consecutive_pairs_stats`) → API 계층
(`/api/stats/consecutive-pairs`) → 페이지/템플릿 계층(`/stats/consecutive-pairs`)
순으로 각 계층마다 실패 테스트 작성 후 최소 구현.

핵심 재사용: `data.py`의 캐시 패턴
(SPEC-066: `get_prime_sum_stats`, SPEC-067: `get_total_sum_stats`,
SPEC-068: `get_range_dist_stats`). 응답은 SPEC-068과 같은 **중첩 딕셔너리
(`consecutive_distribution`)** 구조다.

[HARD] 네이밍 충돌 회피: `_consecutive_cache`/`get_consecutive_pattern_stats`/
`/stats/consecutive-pattern`/`consecutive_pattern.html` 는 SPEC-062가 점유 중이고,
`_consecutive_count`(지역 헬퍼)는 api.py에 이미 존재한다. 따라서 본 SPEC은
`consecutive_pairs` 네임스페이스를 사용한다. SPEC-043/062 코드는 수정하지 않는다.

## 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `_consecutive_pairs_cache`, `_CONSECUTIVE_BUCKETS`, `_consecutive_bucket()`, `count_consecutive_pairs()`, `get_consecutive_pairs_stats()`, `invalidate_cache()` 수정 | +~50 LOC |
| `lotto/web/routes/api.py` | `get_consecutive_pairs()` 핸들러 | +~15 LOC |
| `lotto/web/routes/pages.py` | `stats_consecutive_pairs_page()` 핸들러 | +~15 LOC |
| `lotto/web/templates/consecutive_pairs.html` | 통계 페이지 템플릿 | NEW (~80 LOC) |
| `lotto/web/templates/base.html` | nav 링크 추가 (데스크탑+모바일, 3개소) | +3 LOC |
| `tests/test_consecutive_pairs_analysis.py` | 테스트 파일 (22+ 케이스) | NEW (~120 LOC) |

## 구현 단계

### 단계 1: data.py — 통계 계산 함수 (REQ-069-F-001, F-004, F-005, F-006, NF-001~004)

```
1-1. _consecutive_pairs_cache 딕셔너리 변수 선언 (키: str(len(draws)))
1-2. _CONSECUTIVE_BUCKETS 상수 정의: ["0", "1", "2", "3+"]
1-3. _consecutive_bucket(count) 헬퍼 함수: 연속 쌍 개수 → 버킷 키 분류
1-4. count_consecutive_pairs(numbers) 헬퍼 함수: 회차 번호 리스트 → 연속 쌍 개수
     · 테스트 가능성을 위해 별도 추출 (set 멤버십으로 n+1 존재 여부 판정)
1-5. get_consecutive_pairs_stats(draws) 구현
     - 캐시 히트 체크 (key: str(len(draws)))
     - draws 빈 경우 → 0-값 딕셔너리 반환 (4 버킷 zero-fill, most_common_bucket="")
     - 각 draw.numbers()의 연속 쌍 개수를 count_consecutive_pairs로 산출
     - dist_counts[버킷] += 1 로 4개 버킷에 집계
     - most_common_bucket 산출 (count 최댓값, 동점 시 _CONSECUTIVE_BUCKETS 앞선 버킷)
     - avg_consecutive_pairs / no_consecutive_pct / has_consecutive_pct / 버킷 pct 계산 (2자리 반올림)
     - 결과 캐시 저장 후 반환
1-6. invalidate_cache()에 _consecutive_pairs_cache.clear() 추가
```

### 단계 2: routes/api.py, routes/pages.py — 라우트 핸들러

```
2-1. api.py에 get_consecutive_pairs() 추가
     GET /api/stats/consecutive-pairs → wd.get_consecutive_pairs_stats(wd.get_draws())
2-2. pages.py에 stats_consecutive_pairs_page() 추가
     GET /stats/consecutive-pairs → _render(request, "consecutive_pairs.html",
         {"active_tab": "consecutive_pairs", "stats": ...})
```

### 단계 3: templates — HTML 페이지

```
3-1. consecutive_pairs.html 생성 (SPEC-068 range_dist.html 패턴 참조)
     - 빈 상태 처리: {% if stats.total_draws == 0 %}
     - 요약 카드: 총 회차, 평균 연속 쌍(avg_consecutive_pairs),
       최다 버킷(most_common_bucket), 연속 없음 비율(no_consecutive_pct)
     - 분포 테이블: 4개 행 (consecutive_distribution 중첩 dict 순회)
       · 컬럼: 버킷("0"/"1"/"2"/"3+") / count / pct
     - 제목·헤딩에 "연속" 텍스트 포함
     - Tailwind CSS 다크모드 지원
3-2. base.html nav에 "연속 쌍" 링크 추가 (데스크탑 + 모바일, active_tab=consecutive_pairs)
     · 라벨은 SPEC-043 "연속 번호", SPEC-062 "연속 패턴"과 구분되도록 "연속 쌍" 사용
```

### 단계 4: tests — 테스트 (22+ 케이스)

```
테스트 파일: tests/test_consecutive_pairs_analysis.py

필수 케이스 (acceptance.md AC-069-001~022 대응):
- 빈 데이터: 모든 0, 4 버킷 존재, most_common_bucket=""
- [1,2,3,4,5,6] → count=5 → 버킷 "3+"
- [1,3,5,7,9,11] → count=0 → 버킷 "0"
- [1,2,10,20,30,40] → count=1 → 버킷 "1"
- [1,2,10,11,20,30] → count=2 → 버킷 "2"
- 보너스 제외 검증
- 4 버킷 항상 존재
- avg_consecutive_pairs / no_consecutive_pct / has_consecutive_pct 정확성
- most_common_bucket 및 동점 처리
- pct 합계 ≈ 100.0 / count 합 = total_draws
- 캐시 히트 / 미스 / 무효화
- API 엔드포인트 200 + JSON 구조
- 페이지 엔드포인트 200 ("연속" 포함)
- 실 데이터 smoke test
- wrap-around 비검증: [44,45,1,2,3,30] → (1,2),(2,3),(44,45) = 3
```

## 핵심 알고리즘

```python
_CONSECUTIVE_BUCKETS = ["0", "1", "2", "3+"]
_consecutive_pairs_cache: dict[str, Any] = {}


def _consecutive_bucket(count: int) -> str:
    if count == 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    return "3+"


def count_consecutive_pairs(numbers: list) -> int:
    """Count how many (n, n+1) pairs exist among the numbers."""
    num_set = set(numbers)
    return sum(1 for n in numbers if n + 1 in num_set)


def get_consecutive_pairs_stats(draws: list) -> dict:
    key = str(len(draws))
    if key in _consecutive_pairs_cache:
        return _consecutive_pairs_cache[key]
    if not draws:
        result = {
            "total_draws": 0,
            "avg_consecutive_pairs": 0.0,
            "most_common_bucket": "",
            "no_consecutive_pct": 0.0,
            "has_consecutive_pct": 0.0,
            "consecutive_distribution": {
                b: {"count": 0, "pct": 0.0} for b in _CONSECUTIVE_BUCKETS
            },
        }
        _consecutive_pairs_cache[key] = result
        return result

    n = len(draws)
    counts = [count_consecutive_pairs(list(draw.numbers())) for draw in draws]
    dist_counts = {b: 0 for b in _CONSECUTIVE_BUCKETS}
    for c in counts:
        dist_counts[_consecutive_bucket(c)] += 1

    total_pairs = sum(counts)
    no_consecutive = dist_counts["0"]
    most_common = max(_CONSECUTIVE_BUCKETS, key=lambda b: dist_counts[b])

    result = {
        "total_draws": n,
        "avg_consecutive_pairs": round(total_pairs / n, 2),
        "most_common_bucket": most_common,
        "no_consecutive_pct": round(no_consecutive / n * 100, 2),
        "has_consecutive_pct": round((n - no_consecutive) / n * 100, 2),
        "consecutive_distribution": {
            b: {"count": dist_counts[b], "pct": round(dist_counts[b] / n * 100, 2)}
            for b in _CONSECUTIVE_BUCKETS
        },
    }
    _consecutive_pairs_cache[key] = result
    return result
```

핵심 주의:
- `max(_CONSECUTIVE_BUCKETS, key=...)`는 동점 시 **iterable에서 먼저 나오는 원소**를
  반환하므로 `_CONSECUTIVE_BUCKETS` 순서가 그대로 tie-break 규칙(앞선 버킷 우선)이
  된다 (REQ-069-F-006).
- `count_consecutive_pairs`는 `set` 멤버십으로 `n+1` 존재 여부를 판정한다. 정렬·인접
  비교가 아니라 집합 포함 방식이므로 입력 정렬 여부와 무관하게 동작한다
  (예: `[44,45,1,2,3,30]` → (1,2),(2,3),(44,45) = 3). 45→1 같은 wrap-around는
  연속으로 보지 않는다(46이 집합에 없으므로 자연히 제외).
- `"3+"` 오버플로 버킷: 3개 이상 연속 쌍은 모두 `"3+"` 로 합산한다.

## 배경 통계 (기대 분포)

1~45에서 무작위로 6개를 뽑을 때 연속 쌍 개수의 기댓값:
- 인접 쌍 후보는 (1,2)…(44,45) 총 44개. 각 쌍이 동시에 뽑힐 확률은
  `C(43,4)/C(45,6) = 6/(45·44/(6·5)) ...` 근사적으로 한 쌍당 `30/(45·44)`.
- 기대 연속 쌍 개수 ≈ 44 × (6·5)/(45·44) = 30/45 = **5/9 ≈ 0.56**.
- 실제 한국 로또 이력에서는 **약 70~75% 회차가 최소 1개 이상의 연속 쌍**을 가진다.

→ 따라서 실 데이터에서 `has_consecutive_pct` 는 50%를 충분히 상회하고
   `most_common_bucket` 은 보통 `"0"` 또는 `"1"` 근처에 형성될 것으로 기대된다.

## 테스트 목표

- 현재 테스트 수: 1598개 (SPEC-068 완료 기준)
- 목표: +22 테스트 → 1620개 이상
- 모든 REQ 커버리지 달성 (REQ-069-F-001~F-006, NF-001~NF-004)
