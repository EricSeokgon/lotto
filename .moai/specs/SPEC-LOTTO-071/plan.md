---
id: SPEC-LOTTO-071
version: 0.1.0
status: Planned
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-071 구현 계획

## 방법론

TDD (RED → GREEN → REFACTOR), 브라운필드 보강. 기존 동작을 보존하며 읽기 전용
통계 분석 계층만 추가한다. 데이터 계층(`get_median_stats`) → API 계층
(`/api/stats/median`) → 페이지/템플릿 계층(`/stats/median`) 순으로 각 계층마다
실패 테스트 작성 후 최소 구현.

핵심 재사용: `data.py`의 캐시 패턴 (SPEC-065: `get_std_stats`,
SPEC-070: `get_ac_value_stats`). 응답은 SPEC-070과 같은 **중첩 딕셔너리
(`median_distribution`)** 구조이며, 분포 키는 9개 고정으로 zero-fill 한다.
AC값과 달리 오버플로 버킷이 불필요하다 (모든 중앙값이 9개 구간에 들어감).

신규 심볼은 모두 비중복 검증 완료:
`get_median_stats`, `_median_cache`, `/api/stats/median`, `/stats/median`,
`median.html`, `tests/test_median_analysis.py`.

## 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `_median_cache`, `_MEDIAN_KEYS`, `_MEDIAN_CENTER`, `compute_median()`, `_median_bucket()`, `get_median_stats()`, `invalidate_cache()` 수정 | +~60 LOC |
| `lotto/web/routes/api.py` | `get_median()` 핸들러 (`GET /api/stats/median`) | +~15 LOC |
| `lotto/web/routes/pages.py` | `stats_median_page()` 핸들러 (`GET /stats/median`) | +~15 LOC |
| `lotto/web/templates/median.html` | 통계 페이지 템플릿 | NEW (~85 LOC) |
| `lotto/web/templates/base.html` | nav 링크 "중앙값" 추가 (데스크탑+모바일+모바일메뉴, 3개소) | +3 LOC |
| `tests/test_median_analysis.py` | 테스트 파일 (22+ 케이스) | NEW (~140 LOC) |

## 불변 파일

`lotto/analyzer.py`, `lotto/models.py`, `lotto/recommender.py`, `lotto/simulator.py`
및 기타 코어 모듈 (`lotto/*.py`). 코어 로직은 수정하지 않고 `lotto/web/` 계층만 확장한다.

## 구현 단계

### 단계 1: data.py — 통계 계산 함수 (REQ-MED-001, 004~008, NF-001~005)

```
1-1. _median_cache 딕셔너리 변수 선언 (키: str(len(draws)))
1-2. _MEDIAN_KEYS 상수 정의 (9개 고정, 순서 = 오름차순):
     ["1-5","6-10","11-15","16-20","21-25","26-30","31-35","36-40","41-45"]
1-3. _MEDIAN_CENTER = 23.0  (low median 판정 임계값)
1-4. compute_median(numbers) 헬퍼: 6개 번호 → (c+d)/2.0
     · nums = sorted(numbers); return (nums[2] + nums[3]) / 2.0
     · 테스트 가능성을 위해 별도 추출
1-5. _median_bucket(median) 헬퍼: median 값 → 9개 키 중 하나
     · 경계는 .5 단위, >= 하한 / < 상한, 경계값은 상위 구간
1-6. get_median_stats(draws) 구현
     - 캐시 히트 체크 (key: str(len(draws)))
     - draws 빈 경우 → 0-값 딕셔너리 반환 (9 키 zero-fill,
       most_common_range="1-5")
     - 각 draw.numbers()의 median을 compute_median로 산출
     - dist_counts[_median_bucket(m)] += 1 로 9개 키에 집계
     - most_common_range 산출 (count 최댓값, 동점 시 키 순서상 앞 구간)
     - avg_median / low_median_pct / 키별 pct 계산 (2자리 반올림)
     - low = sum(1 for m in medians if m < 23.0)
     - 결과 캐시 저장 후 반환
1-7. invalidate_cache()에 _median_cache.clear() 추가
```

### 단계 2: routes/api.py, routes/pages.py — 라우트 핸들러

```
2-1. api.py에 get_median() 추가
     GET /api/stats/median → wd.get_median_stats(wd.get_draws())
2-2. pages.py에 stats_median_page() 추가
     GET /stats/median → _render(request, "median.html",
         {"active_tab": "median", "stats": ...})
```

### 단계 3: templates — HTML 페이지

```
3-1. median.html 생성 (SPEC-070 ac_value.html 패턴 참조)
     - 빈 상태 처리: {% if stats.total_draws == 0 %}
     - 요약 카드: 총 회차, 평균 중앙값(avg_median),
       최다 구간(most_common_range), 중심 미만 비율(low_median_pct)
     - 분포 테이블: 9개 행 (median_distribution 중첩 dict 순회)
       · 컬럼: 구간 / count / pct
     - 제목·헤딩에 "중앙값" 텍스트 포함
     - Tailwind CSS 다크모드 지원, 클라이언트 JS 없음
3-2. base.html nav에 "중앙값" 링크 추가 (데스크탑 + 모바일 + 모바일메뉴, 3개소)
     · href="/stats/median", active_tab=median
```

### 단계 4: tests — 테스트 (22+ 케이스)

```
테스트 파일: tests/test_median_analysis.py

필수 케이스 (acceptance.md AC-071-001~022 대응):
- 빈 데이터: 모든 0, 9 키 존재, most_common_range="1-5"
- [1,2,3,4,5,6] → median 3.5 → "1-5"
- [10,20,30,40,42,45] → median 35.0 → "31-35"
- 최솟값 [1,2,3,4,44,45] → median 3.5 / 가능한 최소 median 1.5 검증
- 최댓값 median 44.5 → "41-45"
- 경계값 median=5.5 → "6-10" (상위 구간 포함)
- 경계값 median=23.0 → "21-25" + low_median_pct에서 제외
- 경계값 median=20.5 → "21-25" + low(<23) 포함
- 보너스 제외 검증
- 9 키 항상 존재
- avg_median / low_median_pct 정확성
- most_common_range 및 동점 처리 (앞 구간 우선)
- pct 합계 ≈ 100.0 / count 합 = total_draws
- 캐시 히트 / 미스 / 무효화
- API 엔드포인트 200 + JSON 구조 (9 키)
- 페이지 엔드포인트 200 ("중앙값" 포함)
- 실 데이터 smoke test
```

## 핵심 알고리즘

```python
_MEDIAN_KEYS = [
    "1-5", "6-10", "11-15", "16-20", "21-25",
    "26-30", "31-35", "36-40", "41-45",
]
_MEDIAN_CENTER = 23.0
_median_cache: dict[str, Any] = {}

# 각 키의 상한(<) 경계. "41-45"는 상한 없음(None).
_MEDIAN_BUCKET_BOUNDS = [
    ("1-5", 5.5), ("6-10", 10.5), ("11-15", 15.5), ("16-20", 20.5),
    ("21-25", 25.5), ("26-30", 30.5), ("31-35", 35.5), ("36-40", 40.5),
    ("41-45", None),
]


def compute_median(numbers: list) -> float:
    """Median of 6 numbers = average of the 3rd and 4th smallest."""
    nums = sorted(numbers)
    return (nums[2] + nums[3]) / 2.0


def _median_bucket(median: float) -> str:
    """Map a median value to one of the 9 fixed range keys."""
    for key, upper in _MEDIAN_BUCKET_BOUNDS:
        if upper is None or median < upper:
            return key
    return "41-45"  # unreachable safeguard


def get_median_stats(draws: list) -> dict:
    key = str(len(draws))
    if key in _median_cache:
        return _median_cache[key]
    if not draws:
        result = {
            "total_draws": 0,
            "avg_median": 0.0,
            "most_common_range": "1-5",
            "low_median_pct": 0.0,
            "median_distribution": {
                k: {"count": 0, "pct": 0.0} for k in _MEDIAN_KEYS
            },
        }
        _median_cache[key] = result
        return result

    n = len(draws)
    medians = [compute_median(list(draw.numbers())) for draw in draws]
    dist_counts = {k: 0 for k in _MEDIAN_KEYS}
    for m in medians:
        dist_counts[_median_bucket(m)] += 1

    total_median = sum(medians)
    low = sum(1 for m in medians if m < _MEDIAN_CENTER)
    # tie-break: earlier key in _MEDIAN_KEYS (smaller lower bound) wins
    most_common = max(_MEDIAN_KEYS, key=lambda k: dist_counts[k])

    result = {
        "total_draws": n,
        "avg_median": round(total_median / n, 2),
        "most_common_range": most_common,
        "low_median_pct": round(low / n * 100, 2),
        "median_distribution": {
            k: {"count": dist_counts[k], "pct": round(dist_counts[k] / n * 100, 2)}
            for k in _MEDIAN_KEYS
        },
    }
    _median_cache[key] = result
    return result
```

핵심 주의:
- `max(_MEDIAN_KEYS, key=...)`는 동점 시 **iterable에서 먼저 나오는 원소**를
  반환한다. `_MEDIAN_KEYS` 는 하한 오름차순이므로 그대로 "앞 구간 우선" tie-break
  규칙이 된다 (REQ-MED-006).
- `compute_median` 은 `sorted()` 로 정렬 후 인덱스 2·3을 사용한다. 입력 순서와
  무관하다. `draw.numbers()` 가 이미 정렬되어 있더라도 안전을 위해 명시 정렬한다.
- 경계값은 `< upper` 규칙으로 항상 상위 구간에 들어간다 (REQ-MED-004). 예:
  median=5.5 → `"1-5"`(< 5.5) 불성립 → `"6-10"`(< 10.5) 성립.
- `low_median_pct` 는 strict `< 23.0` 이다. median=23.0 은 제외 (REQ-MED-007).
- 모든 가능한 중앙값(1.5~44.5)은 9개 구간 안에 들어가므로 KeyError·오버플로
  처리가 불필요하다 (Agent "Verify, Don't Assume": 최솟값 1.5∈"1-5",
  최댓값 44.5∈"41-45" 코드로 검증).

## 배경 통계 (기대 분포)

1~45에서 6개를 뽑을 때 3·4번째 값의 평균(중앙값)은 대체로 번호 범위의 중심
부근에 분포한다.
- 번호가 고르게 분산되면 중앙값은 23 근처에 집중된다.
- 저번호대에 몰리면 중앙값이 낮아지고(`low_median` 증가), 고번호대에 몰리면
  높아진다.
- 실제 한국 로또 이력에서 중앙값은 대체로 **"16-20"·"21-25"·"26-30"** 구간에
  집중되며, `most_common_range` 는 보통 **"21-25"** 근처, `low_median_pct`(중심
  23 미만)는 대략 절반 안팎일 것으로 기대된다.

## 테스트 목표

- 현재 테스트 수: 1664개 (SPEC-070 완료 기준, 그 이후 SPEC 진행 시 갱신)
- 목표: +22 테스트 이상
- 모든 REQ 커버리지 달성 (REQ-MED-001~008, REQ-MED-NF-001~005)
