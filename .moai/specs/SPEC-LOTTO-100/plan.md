# SPEC-LOTTO-100 구현 계획

## 개요

통계 기반 번호 조합 적합도 점수(Fitness Score) 기능을 TDD 방법론(RED-GREEN-REFACTOR)으로 구현한다.
기존 50개 분포 통계 데이터를 재활용하여 새로운 데이터 수집 없이 구현 가능하다.

---

## 기술 스택

- Python 3.9 (match/case 미사용, zip strict 미사용)
- FastAPI (기존 라우터 패턴 유지)
- Jinja2 템플릿 (기존 base.html 확장)
- 기존 `lotto/web/data.py` 통계 함수 재활용

---

## 적합도 알고리즘 상세

### 1단계: 6개 번호에서 특성값 계산

각 통계 항목에 대해 6개 번호(정렬 불필요, 내부에서 처리)로부터 버킷 키를 계산한다.

```python
# 예시 (의사코드, Python 3.9 호환)
def _calc_odd_even_bucket(numbers: list[int]) -> str:
    odd_count = sum(1 for n in numbers if n % 2 != 0)
    return str(odd_count)  # "0"~"6"

def _calc_high_low_bucket(numbers: list[int]) -> str:
    low_count = sum(1 for n in numbers if n <= 22)
    return str(low_count)  # "0"~"6"

def _calc_total_sum_bucket(numbers: list[int]) -> str:
    # get_total_sum_stats의 sum_distribution 버킷 구간과 일치하도록
    total = sum(numbers)
    # 기존 sum_range_cache 버킷 키 결정 로직과 동일하게 처리
    ...

def _calc_span_bucket(numbers: list[int]) -> str:
    span = max(numbers) - min(numbers)
    # get_span_stats의 span_distribution 버킷 키 결정 로직과 동일
    if span <= 10: return "10 이하"
    elif span <= 20: return "11-20"
    ...

def _calc_quartile_bucket(numbers: list[int]) -> str:
    # Q1(1-11), Q2(12-22), Q3(23-33), Q4(34-45) 각각의 개수
    q1 = sum(1 for n in numbers if n <= 11)
    q2 = sum(1 for n in numbers if 12 <= n <= 22)
    q3 = sum(1 for n in numbers if 23 <= n <= 33)
    q4 = sum(1 for n in numbers if n >= 34)
    return f"{q1}-{q2}-{q3}-{q4}"

def _calc_zone_coverage_bucket(numbers: list[int]) -> str:
    zones = len(set((n - 1) // 5 for n in numbers))
    return str(zones)  # "1"~"6"
```

### 2단계: 버킷 pct 조회

각 통계 함수를 호출(캐시 활용)하여 버킷 pct를 가져온다.

```python
# 예시 (의사코드)
stats = get_odd_even_stats(draws)
bucket_key = _calc_odd_even_bucket(numbers)
pct = stats["distribution"].get(int(bucket_key), {}).get("pct", 0.0)
```

### 3단계: 평균 산출

```python
total_pct = sum(item_pcts)
fitness_score = round(total_pct / len(item_pcts), 2)
```

### 4단계: 등급 결정

```python
def _grade(score: float) -> str:
    if score >= 80.0:
        return "매우 높음"
    elif score >= 60.0:
        return "높음"
    elif score >= 40.0:
        return "보통"
    elif score >= 20.0:
        return "낮음"
    else:
        return "매우 낮음"
```

---

## 각 통계 함수의 버킷 키 타입 매핑

| 항목 | 함수 반환 구조 내 버킷 키 | 키 타입 |
|------|------------------------|---------|
| odd_even | `distribution[int]` | int (0~6) |
| high_low | `distribution[int]` | int (0~6) |
| total_sum | `sum_distribution[str]` | str (구간 라벨) |
| span | `span_distribution[str]` | str (구간 라벨) |
| consecutive | `pair_distribution[int]` | int (0~5) |
| ac_value | `ac_distribution[int]` | int (0~10) |
| last_digit | `distribution[str]` | str ("0"~"9") → 6개 번호 각각 pct 평균 |
| quartile | `quartile_distribution[str]` | str ("q1-q2-q3-q4") |
| zone_coverage | `zone_coverage_distribution[str]` | str ("1"~"6") |
| min_gap | `min_gap_distribution[str]` | str (구간 라벨) |
| gap_median | `gap_median_distribution[str]` | str (구간 라벨) |
| decade | `distribution[str]` | str (10단위 조합 패턴) |
| prime | `prime_distribution[int]` | int (0~6) |
| last_digit_sum | `sum_distribution[str]` | str (low/mid/high) |
| sum_last_digit | `distribution[str]` | str ("0"~"9") |

---

## 작업 분해 (TDD 사이클)

### 우선순위 High — 핵심 로직

**작업 1: 입력 검증 함수**
- RED: `test_validate_numbers_exact_6` — 6개 정확히 입력
- RED: `test_validate_numbers_out_of_range` — 범위 초과(0, 46)
- RED: `test_validate_numbers_duplicates` — 중복 번호
- GREEN: `_validate_fitness_numbers(numbers: list[int]) -> None` 구현 (예외 발생)
- REFACTOR: 에러 메시지 한국어화

**작업 2: 버킷 계산 헬퍼 함수들**
- RED: 각 항목별 버킷 키 계산 테스트
- GREEN: `_calc_*_bucket` 함수 구현 (15개 항목)
- REFACTOR: 중복 로직 추출

**작업 3: `get_fitness_score` 핵심 함수**
- RED: `test_fitness_score_returns_dict_with_required_fields`
- RED: `test_fitness_score_range_0_to_100`
- RED: `test_fitness_score_empty_draws_returns_zero`
- RED: `test_fitness_score_breakdown_has_15_items`
- RED: `test_fitness_score_grade_mapping`
- GREEN: `get_fitness_score(numbers, draws)` 구현
- REFACTOR: 명확한 함수 분리

### 우선순위 High — API 엔드포인트

**작업 4: API 엔드포인트**
- RED: `test_api_fitness_valid_numbers` — 200 응답
- RED: `test_api_fitness_invalid_count` — 400
- RED: `test_api_fitness_out_of_range` — 400
- RED: `test_api_fitness_duplicates` — 400
- RED: `test_api_fitness_missing_numbers` — 422
- GREEN: `GET /api/stats/fitness` 엔드포인트 구현

### 우선순위 Medium — 웹 페이지

**작업 5: 웹 페이지 라우트 및 템플릿**
- RED: `test_page_fitness_returns_200`
- RED: `test_page_fitness_with_numbers_query_param`
- GREEN: `GET /stats/fitness` 페이지 라우트 구현
- GREEN: `fitness.html` 템플릿 작성

### 우선순위 Medium — 네비게이션 업데이트

**작업 6: 사이드바 링크 추가**
- `base.html` 사이드바에 "적합도 점수" 링크 추가

---

## 위험 요소 및 대응

| 위험 | 설명 | 대응 방법 |
|------|------|----------|
| 버킷 키 불일치 | 통계 함수 반환 구조의 버킷 키 타입(int vs str)이 불일치할 수 있음 | 각 통계 함수의 실제 반환 구조 확인 후 타입 캐스팅 처리 |
| 미관측 패턴 | 6개 번호의 패턴이 역대 당첨 이력에 없을 경우 pct=0.0 | pct=0.0으로 처리 (fitness_score에 0 기여) |
| 캐시 미로드 | 서버 시작 직후 통계 캐시가 없을 경우 | `get_draws()` 호출 결과가 None이면 빈 결과 반환 (REQ-FS-S01) |
| last_digit 항목 복잡성 | last_digit 통계는 번호별 개별 분포로, 6개 번호에 대해 pct를 평균해야 함 | 각 번호의 끝자리(0~9) 중 해당 끝자리 버킷 pct 평균으로 처리 |
| total_sum 버킷 경계 | get_total_sum_stats의 구간 라벨이 복잡할 수 있음 | 기존 함수의 구간 분류 로직을 복사하여 일관성 유지 |

---

## 파일별 변경 사항

### `lotto/web/data.py`

추가 내용:
```python
# SPEC-LOTTO-100: 적합도 점수 계산 함수
def get_fitness_score(
    numbers: list[int],
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    ...
```

- `invalidate_cache()`에는 `# SPEC-LOTTO-100: fitness score는 캐시하지 않음` 주석 추가

### `lotto/web/routes/api.py`

추가 엔드포인트:
```python
@router.get("/stats/fitness")
async def get_fitness_score_endpoint(
    numbers: str = Query(..., description="쉼표로 구분된 6개 번호 (예: 1,2,3,4,5,6)")
) -> dict[str, Any]:
    ...
```

### `lotto/web/routes/pages.py`

추가 라우트:
```python
@router.get("/stats/fitness")
async def fitness_page(request: Request) -> TemplateResponse:
    ...
```

### `lotto/web/templates/fitness.html`

- base.html 확장
- 번호 6개 입력 폼
- JavaScript fetch로 API 호출
- 점수 표시 (0~100 게이지)
- 등급 표시
- 항목별 breakdown 테이블
- 면책 고지 문구

### `lotto/web/templates/base.html`

사이드바 통계 섹션에 추가:
```html
<a href="/stats/fitness">적합도 점수</a>
```

---

## 예상 테스트 수

| 영역 | 테스트 수 |
|------|---------|
| 입력 검증 | 8개 |
| 버킷 계산 헬퍼 | 15개 |
| `get_fitness_score` 핵심 로직 | 10개 |
| API 엔드포인트 | 8개 |
| 웹 페이지 라우트 | 4개 |
| 엣지 케이스 | 5개 |
| **합계** | **약 50개** |
