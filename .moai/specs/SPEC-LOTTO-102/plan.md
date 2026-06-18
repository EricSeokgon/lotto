# SPEC-LOTTO-102 구현 계획

## 개요

번호 조합 회차별 백테스트(시뮬레이션) 기능을 TDD 방법론(RED-GREEN-REFACTOR)으로 구현한다. 기존 `get_draws()`와 `get_fitness_score()`(SPEC-100)를 재활용하므로 새로운 데이터 수집은 필요하지 않다.

---

## 기술 스택

- Python 3.9 (`match`/`case` 미사용, `zip(strict=True)` 미사용)
- FastAPI (기존 라우터 패턴 유지, POST + Pydantic body)
- Pydantic v2 (`SimulateRequest` 모델)
- Jinja2 템플릿 (기존 `base.html` 확장)
- 기존 `lotto/web/data.py` 함수 재활용 (`get_draws`, `get_fitness_score`)

---

## 시뮬레이션 알고리즘 상세

### 1단계: 입력 검증

```python
def _validate_combo(numbers: list[int]) -> None:
    if len(numbers) != 6:
        raise ValueError(f"번호는 정확히 6개여야 합니다. 현재: {len(numbers)}개")
    if any(n < 1 or n > 45 for n in numbers):
        raise ValueError("번호는 1~45 범위여야 합니다.")
    if len(set(numbers)) != 6:
        raise ValueError("중복 번호가 있습니다.")
```

### 2단계: 회차별 일치 계산

```python
user_set = set(numbers)
for draw in draws:
    match_count = len(user_set & set(draw.numbers))
    bonus_match = draw.bonus in user_set
    grade = _judge_grade(match_count, bonus_match)
```

### 3단계: 등급 판정 (if/elif 체인, Python 3.9 호환)

```python
def _judge_grade(match_count: int, bonus_match: bool) -> str:
    if match_count == 6:
        return "1등"
    if match_count == 5 and bonus_match:
        return "2등"
    if match_count == 5:
        return "3등"
    if match_count == 4:
        return "4등"
    if match_count == 3:
        return "5등"
    return "꽝"
```

### 4단계: 요약 집계

```python
_GRADES = ["1등", "2등", "3등", "4등", "5등", "꽝"]
grade_counts = {g: 0 for g in _GRADES}
# ... 루프에서 grade_counts[grade] += 1
total = len(draws)
grade_percentages = {
    g: round(grade_counts[g] / total * 100, 2) if total else 0.0
    for g in _GRADES
}
```

### 5단계: 적합도 통합

```python
fitness_raw = get_fitness_score(numbers, draws)
fitness = {
    "fitness_score": fitness_raw["fitness_score"],
    "grade": fitness_raw["grade"],
}
```

---

## 작업 분해 (TDD 사이클)

### 우선순위 High — 핵심 로직

**작업 1: 입력 검증 (`_validate_combo`)**
- RED: `test_validate_combo_exact_6` — 6개가 아니면 ValueError
- RED: `test_validate_combo_out_of_range` — 0, 46 포함 시 ValueError
- RED: `test_validate_combo_duplicates` — 중복 시 ValueError
- GREEN: `_validate_combo` 구현
- REFACTOR: 한국어 에러 메시지 정리

**작업 2: 등급 판정 (`_judge_grade`)**
- RED: `test_judge_grade_1st` — (6, False) → "1등"
- RED: `test_judge_grade_2nd` — (5, True) → "2등"
- RED: `test_judge_grade_3rd` — (5, False) → "3등"
- RED: `test_judge_grade_4th` — (4, ?) → "4등"
- RED: `test_judge_grade_5th` — (3, ?) → "5등"
- RED: `test_judge_grade_miss` — (0~2, ?) → "꽝"
- GREEN: `_judge_grade` 구현
- REFACTOR: 분기 순서 검증 (2등이 3등보다 먼저 평가되는지)

**작업 3: `get_combo_simulation` 핵심 함수**
- RED: `test_simulation_returns_required_fields` — numbers/summary/rounds/fitness/disclaimer 키
- RED: `test_simulation_summary_has_6_grades` — grade_counts에 6개 등급 키 모두 존재
- RED: `test_simulation_zero_grades_included` — 미발생 등급도 0으로 포함
- RED: `test_simulation_percentages_sum_approx_100` — 비율 합 ≈ 100 (회차 존재 시)
- RED: `test_simulation_empty_draws_returns_zero_summary` — None/빈 리스트 시 total_rounds=0
- RED: `test_simulation_rounds_detail_structure` — 각 round에 draw_no/date/match_count/bonus_match/grade
- RED: `test_simulation_match_count_excludes_bonus` — match_count는 본번호만 집계
- RED: `test_simulation_order_independence` — 입력 순서 무관 동일 결과
- RED: `test_simulation_includes_fitness` — fitness.fitness_score, fitness.grade 포함
- GREEN: `get_combo_simulation` 구현
- REFACTOR: 헬퍼 분리, 타입 힌트 완비

### 우선순위 High — API 엔드포인트

**작업 4: `POST /api/stats/simulate`**
- RED: `test_api_simulate_valid` — 200 + summary/rounds/fitness
- RED: `test_api_simulate_invalid_count` — 5개/7개 → 422
- RED: `test_api_simulate_out_of_range` — 0/46 포함 → 422
- RED: `test_api_simulate_duplicates` — 중복 → 422
- RED: `test_api_simulate_response_grade_keys` — 응답 grade_counts 6개 키
- GREEN: `SimulateRequest` 모델 + 엔드포인트 구현 (ValueError → HTTP 422 변환)

### 우선순위 Medium — 웹 페이지

**작업 5: `GET /stats/simulate` 페이지 + 템플릿**
- RED: `test_page_simulate_returns_200`
- RED: `test_page_simulate_has_form` — 번호 입력 폼 포함
- RED: `test_page_simulate_has_disclaimer` — 면책 고지 포함
- GREEN: `GET /stats/simulate` 라우트(active_tab="combo_simulate") + `simulate_combo.html` 작성

### 우선순위 Medium — 내비게이션

**작업 6: `base.html` 내비게이션 추가**
- RED: `test_nav_has_combo_simulate_link` — `/stats/simulate` 링크 존재
- GREEN: desktop_nav_items / nav_items에 `('/stats/simulate', 'combo_simulate', '조합 시뮬레이션')` 추가
- GREEN: active_tab 헤딩 분기에 `combo_simulate` 케이스 추가

---

## 각 단계 검증 포인트

| 단계 | 검증 |
|------|------|
| match_count | 보너스 제외, 본번호 교집합만 |
| 2등 vs 3등 | 보너스 일치 여부로 분기, 2등이 먼저 평가 |
| 빈 데이터 | HTTP 200 + 빈 요약 (에러 아님) |
| fitness 통합 | get_fitness_score 반환의 fitness_score/grade만 추출 |
| 경로 충돌 | 기존 /simulate(몬테카를로)와 /stats/simulate(백테스트) 분리 |

---

## 위험 요소 및 대응

| 위험 | 설명 | 대응 방법 |
|------|------|----------|
| 경로/탭 충돌 | 기존 `/simulate`·"시뮬레이션" 탭과 혼동 | 신규는 `/stats/simulate`, tab=`combo_simulate`, label="조합 시뮬레이션"으로 분리 |
| 2등/3등 오판 | 본번호 5개 일치 시 보너스 분기 누락 | `_judge_grade`에서 2등(5+보너스)을 3등보다 먼저 평가, 전용 테스트 |
| match_count에 보너스 혼입 | 보너스를 일치 개수에 더하면 등수 왜곡 | match_count는 본번호 교집합만, 보너스는 bonus_match로 별도 |
| 대량 rounds 응답 크기 | 전체 회차 상세가 응답에 포함되어 페이로드 큼 | API는 전체 제공(요약은 전체 기준), 웹은 표시 시 샘플/페이지네이션 (REQ-SIM-O01) |
| 빈 데이터 처리 | get_draws()가 None일 때 ZeroDivision | total=0 분기로 비율 0.0, 빈 rounds 반환 (REQ-SIM-S01) |
| Python 3.9 호환 | match/case 사용 시 구문 오류 | if/elif 체인 사용 (REQ-SIM-N06) |

---

## 파일별 변경 사항

### `lotto/web/data.py`

```python
# SPEC-LOTTO-102: 등급 판정 헬퍼
def _judge_grade(match_count: int, bonus_match: bool) -> str: ...

# SPEC-LOTTO-102: 번호 조합 회차별 백테스트
def get_combo_simulation(
    numbers: list[int],
    draws: list[DrawResult] | None,
) -> dict[str, Any]: ...
```
- `data.py`는 `from __future__ import annotations`가 있으므로 `list[DrawResult] | None` 사용 가능.

### `lotto/web/routes/api.py`

```python
class SimulateRequest(BaseModel):
    numbers: list[int]

@router.post("/stats/simulate")
async def simulate_combo_route(req: SimulateRequest) -> dict[str, Any]:
    from lotto.web import data as wd
    try:
        return wd.get_combo_simulation(req.numbers, wd.get_draws())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)}) from exc
```
- POST + Pydantic body이므로 Python 3.9 `Optional` 이슈 없음.

### `lotto/web/routes/pages.py`

```python
@router.get("/stats/simulate")
async def simulate_combo_page(request: Request) -> TemplateResponse:
    # active_tab="combo_simulate"
    ...
```

### `lotto/web/templates/simulate_combo.html`

- `base.html` 확장
- 번호 6개 입력 폼 (+ "시뮬레이션 실행" 버튼)
- JavaScript fetch로 `POST /api/stats/simulate` 호출
- 등급 분포 테이블 (1등~꽝 고정 순서, 횟수+비율)
- 적합도 점수/등급 표시
- 최고 등수 강조 (REQ-SIM-O02)
- 면책 고지 문구

### `lotto/web/templates/base.html`

- `desktop_nav_items`, `nav_items`에 `('/stats/simulate', 'combo_simulate', '조합 시뮬레이션')` 추가
- active_tab 헤딩 분기에 `{% elif active_tab == 'combo_simulate' %}번호 조합 회차별 시뮬레이션` 추가

---

## 예상 테스트 수

| 영역 | 테스트 수 |
|------|---------|
| 입력 검증 | 4개 |
| 등급 판정 | 7개 |
| `get_combo_simulation` 핵심 로직 | 10개 |
| API 엔드포인트 | 6개 |
| 웹 페이지/내비게이션 | 5개 |
| 엣지 케이스 | 3개 |
| **합계** | **약 35개** |
