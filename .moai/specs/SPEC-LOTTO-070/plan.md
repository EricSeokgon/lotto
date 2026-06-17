---
id: SPEC-LOTTO-070
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-070 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR), 브라운필드 보강. 기존 동작을 보존하며 읽기 전용
통계 분석 계층만 추가한다. 데이터 계층(`get_ac_value_stats`) → API 계층
(`/api/stats/ac_value`) → 페이지/템플릿 계층(`/stats/ac-value`) 순으로 각 계층마다
실패 테스트 작성 후 최소 구현.

핵심 재사용: `data.py`의 캐시 패턴
(SPEC-067: `get_total_sum_stats`, SPEC-068: `get_range_dist_stats`,
SPEC-069: `get_consecutive_pairs_stats`). 응답은 SPEC-068·069와 같은 **중첩
딕셔너리(`ac_distribution`)** 구조이며, 분포 키는 0~14 전 구간 15개로 zero-fill 한다.

신규 심볼은 모두 비중복 검증 완료:
`get_ac_value_stats`, `_ac_value_cache`, `/api/stats/ac_value`, `/stats/ac-value`,
`ac_value.html`, `tests/test_ac_value_analysis.py`.

## 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `_ac_value_cache`, `_AC_KEYS`, `_AC_DIVERSITY_THRESHOLD`, `compute_ac_value()`, `get_ac_value_stats()`, `invalidate_cache()` 수정 | +~55 LOC |
| `lotto/web/routes/api.py` | `get_ac_value()` 핸들러 (`GET /api/stats/ac_value`) | +~15 LOC |
| `lotto/web/routes/pages.py` | `stats_ac_value_page()` 핸들러 (`GET /stats/ac-value`) | +~15 LOC |
| `lotto/web/templates/ac_value.html` | 통계 페이지 템플릿 | NEW (~85 LOC) |
| `lotto/web/templates/base.html` | nav 링크 "AC값" 추가 (데스크탑+모바일+모바일메뉴, 3개소) | +3 LOC |
| `tests/test_ac_value_analysis.py` | 테스트 파일 (24+ 케이스) | NEW (~140 LOC) |

## 불변 파일

`lotto/analyzer.py`, `lotto/models.py`, `lotto/recommender.py`, `lotto/simulator.py`
및 기타 코어 모듈 (`lotto/*.py`). 코어 로직은 수정하지 않고 `lotto/web/` 계층만 확장한다.

## 구현 단계

### 단계 1: data.py — 통계 계산 함수 (REQ-AC-001, 004~007, NF-001~005)

```
1-1. _ac_value_cache 딕셔너리 변수 선언 (키: str(len(draws)))
1-2. _AC_KEYS 상수 정의: [str(i) for i in range(15)]  # "0".."14"
1-3. _AC_DIVERSITY_THRESHOLD = 9  (high diversity 임계값)
1-4. compute_ac_value(numbers) 헬퍼 함수: 6개 번호 → distinct 차이 개수
     · len({abs(a-b) for i,a in enumerate(nums) for b in nums[i+1:]})
     · 테스트 가능성을 위해 별도 추출
1-5. get_ac_value_stats(draws) 구현
     - 캐시 히트 체크 (key: str(len(draws)))
     - draws 빈 경우 → 0-값 딕셔너리 반환 (15 키 zero-fill, most_common_ac=0)
     - 각 draw.numbers()의 AC값을 compute_ac_value로 산출
     - dist_counts[str(ac)] += 1 로 15개 키에 집계
     - most_common_ac 산출 (count 최댓값, 동점 시 더 작은 AC값)
     - avg_ac_value / high_diversity_pct / 키별 pct 계산 (2자리 반올림)
     - high_diversity = sum(count for ac>=9)
     - 결과 캐시 저장 후 반환
1-6. invalidate_cache()에 _ac_value_cache.clear() 추가
```

### 단계 2: routes/api.py, routes/pages.py — 라우트 핸들러

```
2-1. api.py에 get_ac_value() 추가
     GET /api/stats/ac_value → wd.get_ac_value_stats(wd.get_draws())
2-2. pages.py에 stats_ac_value_page() 추가
     GET /stats/ac-value → _render(request, "ac_value.html",
         {"active_tab": "ac_value", "stats": ...})
```

### 단계 3: templates — HTML 페이지

```
3-1. ac_value.html 생성 (SPEC-068 range_dist.html / SPEC-069 패턴 참조)
     - 빈 상태 처리: {% if stats.total_draws == 0 %}
     - 요약 카드: 총 회차, 평균 AC값(avg_ac_value),
       최다 AC값(most_common_ac), 고다양성 비율(high_diversity_pct)
     - 분포 테이블: 15개 행 (ac_distribution 중첩 dict 순회, "0".."14")
       · 컬럼: AC값 / count / pct
     - 제목·헤딩에 "AC" 텍스트 포함
     - Tailwind CSS 다크모드 지원
3-2. base.html nav에 "AC값" 링크 추가 (데스크탑 + 모바일 + 모바일메뉴, 3개소)
     · href="/stats/ac-value", active_tab=ac_value
```

### 단계 4: tests — 테스트 (24+ 케이스)

```
테스트 파일: tests/test_ac_value_analysis.py

필수 케이스 (acceptance.md AC-070-001~024 대응):
- 빈 데이터: 모든 0, 15 키 존재, most_common_ac=0
- [1,2,3,10,11,12] → AC=7 (distinct {1,2,7,8,9,10,11})
- [1,2,3,4,5,6] → 차이 {1,2,3,4,5} → AC=5
- [1,2,4,8,16,32] → distinct 차이 검증
- 등차수열·균등 간격 케이스
- 보너스 제외 검증
- 15 키 항상 존재
- avg_ac_value / high_diversity_pct 정확성
- most_common_ac 및 동점 처리 (더 작은 AC 우선)
- pct 합계 ≈ 100.0 / count 합 = total_draws
- 캐시 히트 / 미스 / 무효화
- API 엔드포인트 200 + JSON 구조
- 페이지 엔드포인트 200 ("AC" 포함)
- 실 데이터 smoke test
- AC값 경계: 0..14 범위 내 보장
```

## 핵심 알고리즘

```python
_AC_KEYS = [str(i) for i in range(15)]  # "0".."14"
_AC_DIVERSITY_THRESHOLD = 9
_ac_value_cache: dict[str, Any] = {}


def compute_ac_value(numbers: list) -> int:
    """Number of distinct absolute pairwise differences among the numbers."""
    nums = list(numbers)
    diffs = {
        abs(a - b)
        for i, a in enumerate(nums)
        for b in nums[i + 1:]
    }
    return len(diffs)


def get_ac_value_stats(draws: list) -> dict:
    key = str(len(draws))
    if key in _ac_value_cache:
        return _ac_value_cache[key]
    if not draws:
        result = {
            "total_draws": 0,
            "avg_ac_value": 0.0,
            "most_common_ac": 0,
            "high_diversity_pct": 0.0,
            "ac_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _AC_KEYS
            },
        }
        _ac_value_cache[key] = result
        return result

    n = len(draws)
    ac_values = [compute_ac_value(list(draw.numbers())) for draw in draws]
    dist_counts = {k: 0 for k in _AC_KEYS}
    for ac in ac_values:
        # overflow clamp: AC >= 14 counted under "14" (REQ-AC-004)
        dist_counts[str(min(ac, 14))] += 1

    # avg / high-diversity use RAW ac values (REQ-AC-007, REQ-AC-008)
    total_ac = sum(ac_values)
    high_diversity = sum(1 for ac in ac_values if ac >= _AC_DIVERSITY_THRESHOLD)
    # tie-break: smaller AC value wins → iterate _AC_KEYS in ascending order
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
    _ac_value_cache[key] = result
    return result
```

핵심 주의:
- `max(_AC_KEYS, key=...)`는 동점 시 **iterable에서 먼저 나오는 원소**를 반환한다.
  `_AC_KEYS` 는 `"0","1",...,"14"` 오름차순이므로, 그대로 "더 작은 AC값 우선"
  tie-break 규칙이 된다 (REQ-AC-006).
- `most_common_ac` 는 정수로 반환한다(`int(most_common)`). `ac_distribution` 의
  키는 문자열이지만 `most_common_ac` 는 정수 — 응답 구조 명세를 따른다.
- `compute_ac_value` 는 set comprehension 으로 distinct 차이를 직접 센다. 정렬
  여부와 무관하며 입력 순서에 영향받지 않는다.
- [HARD] AC값은 1~45 범위에서 **최대 15** 까지 발생할 수 있다(코드로 검증:
  `[5,8,9,17,32,37]`, `[1,2,4,8,16,32]` → AC=15). 분포 키는 `"0".."14"` 15개로
  고정하고 `min(ac, 14)` 오버플로 클램프로 `dist_counts[str(15)]` KeyError 를
  방지한다. 단 `avg_ac_value` 와 `high_diversity_pct` 는 clamp 이전 원본 AC값으로
  계산한다 (REQ-AC-007, REQ-AC-008).

## 배경 통계 (기대 분포)

1~45에서 6개를 뽑을 때, 15개 쌍 차이 중 일부가 겹치는 정도에 따라 AC값이 정해진다.
- 6개가 등차수열이면 차이 종류가 적어 AC값이 낮다 (예: `[1,2,3,4,5,6]` → AC=5).
- 번호가 흩어질수록 distinct 차이가 늘어 AC값이 높아진다.
- 실제 한국 로또 이력에서 AC값은 대체로 **7~10 구간**에 집중되며,
  `most_common_ac` 는 보통 **8 근처**, `high_diversity_pct`(AC>=9)는 상당한 비율을
  차지할 것으로 기대된다.

## 테스트 목표

- 현재 테스트 수: 1629개 (SPEC-069 완료 기준)
- 목표: +24 테스트 → 1653개 이상
- 모든 REQ 커버리지 달성 (REQ-AC-001~007, REQ-AC-NF-001~005)
