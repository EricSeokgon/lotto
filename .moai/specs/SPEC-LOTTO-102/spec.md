---
id: SPEC-LOTTO-102
version: 0.1.0
status: draft
created: 2026-06-18
updated: 2026-06-18
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-102: 번호 조합 시뮬레이션 (회차별 백테스트)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 0.1.0 | 2026-06-18 | 최초 작성 | ircp |

---

## 개요

사용자가 직접 선택한 6개 번호(1~45)를 역대 모든 로또 추첨 회차에 대입하여, 각 회차에서 몇 개가 일치하고 어떤 등수에 해당했을지를 백테스트(backtest)하는 기능이다.

전체 회차에 대한 일치 개수·등수를 집계하여 등급별 횟수와 비율을 요약하고, 회차별 상세 결과를 함께 제공한다. 또한 SPEC-LOTTO-100의 적합도 점수(Fitness Score)를 동일 조합에 대해 계산하여 시뮬레이션 결과와 나란히 표시한다.

이 기능은 "만약 매주 이 번호를 샀다면 역대 결과가 어땠을까"라는 질문에 답하는 회고적(retrospective) 분석이며, 미래 당첨 가능성을 예측하지 않는다.

---

## 배경

`lotto/web/data.py`에는 역대 추첨 데이터를 반환하는 `get_draws() -> list[DrawResult] | None`와, 임의 6개 번호의 통계적 적합도를 0~100점으로 평가하는 `get_fitness_score(numbers, draws) -> dict`(SPEC-LOTTO-100)가 구현되어 있다.

기존 `/simulate` 페이지는 "회차 수 × 예산" 기반으로 **무작위 번호를 반복 구매**하는 몬테카를로 ROI 시뮬레이션으로, 사용자가 지정한 특정 번호를 다루지 않는다. SPEC-LOTTO-102는 이와 명확히 구별되는 **사용자 지정 조합의 회차별 백테스트** 기능을 새 경로(`/api/stats/simulate`, `/stats/simulate`)로 추가한다.

`DrawResult`는 `draw_no: int`, `date: datetime.date`, `numbers: list[int]`(본번호 6개), `bonus: int` 필드를 가진다. 각 회차에 대해 사용자 조합과 `numbers`의 교집합 크기와 보너스 번호 일치 여부를 계산하여 한국 로또 당첨 등수 규칙으로 등급을 판정한다.

### 한국 로또 6/45 당첨 등수 규칙

| 등급 | 조건 |
|------|------|
| 1등 | 본번호 6개 모두 일치 |
| 2등 | 본번호 5개 일치 + 보너스 번호 일치 |
| 3등 | 본번호 5개 일치 (보너스 불일치) |
| 4등 | 본번호 4개 일치 |
| 5등 | 본번호 3개 일치 |
| 꽝(낙첨) | 본번호 일치 3개 미만 |

---

## 요구사항 (EARS 형식)

### U (Ubiquitous — 항상 적용)

- **REQ-SIM-U01**: 시스템은 사용자 조합과 각 회차 본번호의 일치 개수(`match_count`, 0~6)와 보너스 번호 일치 여부(`bonus_match`, bool)를 계산해야 한다.
- **REQ-SIM-U02**: 시스템은 일치 개수와 보너스 일치 여부로부터 한국 로또 등수 규칙(1~5등, 꽝)에 따라 등급을 판정해야 한다.
- **REQ-SIM-U03**: 2등 판정은 본번호 5개 일치이면서 보너스 번호가 사용자 조합에 포함된 경우에만 성립한다. 3등은 본번호 5개 일치이되 보너스 불일치인 경우이다.
- **REQ-SIM-U04**: 요약 통계(summary)는 `total_rounds`, 등급별 횟수(`grade_counts`), 등급별 비율(`grade_percentages`, 소수 2자리, 합 100% 근사)를 포함해야 한다.
- **REQ-SIM-U05**: 등급 키는 `"1등"`, `"2등"`, `"3등"`, `"4등"`, `"5등"`, `"꽝"` 6종으로 고정하며, 발생 횟수가 0인 등급도 `grade_counts`에 0으로 포함되어야 한다.
- **REQ-SIM-U06**: 시스템은 동일 조합에 대해 `get_fitness_score(numbers, draws)`를 호출하여 `fitness_score`(0~100 실수)와 `grade`(S/A/B/C/D)를 시뮬레이션 결과에 포함해야 한다.
- **REQ-SIM-U07**: 입력 번호의 순서는 결과에 영향을 주지 않아야 한다(정렬 후 처리).

### E (Event-driven — 이벤트 발생 시)

- **REQ-SIM-E01**: When `POST /api/stats/simulate` is called with JSON body `{"numbers": [n1, n2, n3, n4, n5, n6]}` containing a valid 6-number set, the system shall return JSON with `numbers`, `summary`, `rounds`, and `fitness` fields.
- **REQ-SIM-E02**: When the simulation API returns, the `summary` object shall contain `total_rounds`, `grade_counts`(6개 등급 키), and `grade_percentages`(6개 등급 키).
- **REQ-SIM-E03**: When the simulation API returns, the `rounds` array shall contain per-draw detail objects, each with `draw_no`, `date`, `match_count`, `bonus_match`, and `grade`.
- **REQ-SIM-E04**: When the simulation API returns, the `fitness` object shall contain `fitness_score` and `grade` derived from `get_fitness_score`.
- **REQ-SIM-E05**: When `GET /stats/simulate` page is requested, the system shall render `simulate_combo.html` with a 6-number input form; when valid numbers are supplied via query params, the page shall additionally display the grade-distribution table and fitness score.
- **REQ-SIM-E06**: When the user submits 6 numbers on the web page form, the system shall call the simulation API via JavaScript fetch and display the grade distribution and fitness score without full page reload.

### S (State-driven — 상태 조건)

- **REQ-SIM-S01**: While `get_draws()` returns None or an empty list, the simulation API shall return `summary.total_rounds = 0`, all `grade_counts` zero, all `grade_percentages` 0.0, and an empty `rounds` array (HTTP 200, 에러 아님).
- **REQ-SIM-S02**: While historical draw data is available, the system shall simulate against every draw returned by `get_draws()` without sampling or truncation in the API response summary.

### N (Negative — 금지 사항)

- **REQ-SIM-N01**: The system shall NOT accept a number set whose length is not exactly 6; invalid count shall return HTTP 422.
- **REQ-SIM-N02**: The system shall NOT accept numbers outside the range 1–45; out-of-range numbers shall return HTTP 422.
- **REQ-SIM-N03**: The system shall NOT accept duplicate numbers in the input; duplicates shall return HTTP 422.
- **REQ-SIM-N04**: The system shall NOT include the bonus ball when counting `match_count`; bonus is only used for 2등 판정.
- **REQ-SIM-N05**: The system shall NOT claim the simulation predicts future winning probability; the API response and UI must include a disclaimer.
- **REQ-SIM-N06**: The system shall NOT use `zip(strict=True)` (Python 3.9 호환, 필요 시 `# noqa: B905`) nor `match`/`case` syntax (use `if/elif/else`).
- **REQ-SIM-N07**: The system shall NOT modify the existing `/simulate` (몬테카를로 ROI) route or `/simulation-history` route; SPEC-102 uses distinct paths.

### O (Optional — 선택 사항)

- **REQ-SIM-O01**: Where the per-round `rounds` array would be very large, the web page may sample or paginate the detail rows for display; the API summary statistics must remain based on the full draw set.
- **REQ-SIM-O02**: Where any prize-winning grade (1~5등) occurred at least once, the page should highlight the highest grade achieved (최고 등수) for readability.
- **REQ-SIM-O03**: The grade distribution table should display grades in fixed order (1등 → 2등 → 3등 → 4등 → 5등 → 꽝).

---

## 기술적 접근 방법

### 핵심 시뮬레이션 함수

`lotto/web/data.py`에 다음 함수를 추가한다.

```python
# SPEC-LOTTO-102: 번호 조합 회차별 백테스트
def get_combo_simulation(
    numbers: list[int],
    draws: list[DrawResult] | None,
) -> dict[str, Any]:
    """사용자 지정 6개 번호를 역대 회차에 백테스트한다.

    Returns:
        {"numbers", "summary", "rounds", "fitness", "disclaimer"}
    """
    ...
```

처리 흐름:

1. 입력 검증: 6개·범위(1~45)·중복 검사. 위반 시 `ValueError`(라우터에서 HTTP 422로 변환).
2. `draws`가 None/빈 리스트면 빈 요약 반환(REQ-SIM-S01).
3. 사용자 조합을 `set`으로 변환.
4. 각 회차마다 `match_count = len(user_set & set(draw.numbers))`, `bonus_match = draw.bonus in user_set` 계산.
5. `_judge_grade(match_count, bonus_match)`로 등급 판정.
6. 등급별 횟수 집계, 비율 계산(`round(count / total * 100, 2)`).
7. `get_fitness_score(numbers, draws)` 호출하여 `fitness` 구성.

### 등급 판정 로직 (Python 3.9 호환, match/case 미사용)

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

### API 입력 (POST + JSON body 채택 사유)

GET 쿼리 파라미터 반복(`?n=3&n=12&...`)보다 `POST` + JSON body가 더 RESTful하고 검증이 명확하므로 **POST 방식을 채택**한다. Pydantic 모델로 6개 번호를 받으므로 Python 3.9의 `Optional` 이슈도 발생하지 않는다.

```python
class SimulateRequest(BaseModel):
    numbers: list[int]
```

### API 응답 구조 예시

```json
{
  "numbers": [3, 12, 21, 30, 38, 45],
  "summary": {
    "total_rounds": 1180,
    "grade_counts": {"1등": 0, "2등": 0, "3등": 1, "4등": 18, "5등": 240, "꽝": 921},
    "grade_percentages": {"1등": 0.0, "2등": 0.0, "3등": 0.08, "4등": 1.53, "5등": 20.34, "꽝": 78.05}
  },
  "rounds": [
    {"draw_no": 1, "date": "2002-12-07", "match_count": 1, "bonus_match": false, "grade": "꽝"},
    {"draw_no": 2, "date": "2002-12-14", "match_count": 3, "bonus_match": false, "grade": "5등"}
  ],
  "fitness": {"fitness_score": 62.35, "grade": "A"},
  "disclaimer": "이 시뮬레이션은 과거 회차 결과에 대한 회고 분석이며 미래 당첨 가능성을 예측하지 않습니다."
}
```

---

## 수정 대상 파일

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `lotto/web/data.py` | 수정 | `get_combo_simulation(numbers, draws) -> dict[str, Any]` 및 `_judge_grade` 헬퍼 추가 |
| `lotto/web/routes/api.py` | 수정 | `POST /api/stats/simulate` 엔드포인트 추가 (Pydantic `SimulateRequest` body) |
| `lotto/web/routes/pages.py` | 수정 | `GET /stats/simulate` 페이지 라우트 추가 (active_tab=`combo_simulate`) |
| `lotto/web/templates/simulate_combo.html` | 신규 | 번호 입력 폼 + 등급 분포 테이블 + 적합도 점수 표시 |
| `lotto/web/templates/base.html` | 수정 | 내비게이션에 "조합 시뮬레이션"(`/stats/simulate`, tab=`combo_simulate`) 항목 추가 + active_tab 헤딩 분기 추가 |
| `tests/test_combo_simulation.py` | 신규 | TDD 테스트 파일 (최소 30개 AC 검증) |

---

## 제외 항목 (Exclusions / What NOT to Build)

- 미래 회차 당첨 예측 또는 확률 추정은 이 SPEC의 범위 밖이다.
- 예산/구매 비용/ROI(수익률) 계산은 포함하지 않는다 (기존 `/simulate` 몬테카를로 기능의 영역).
- 기존 `/simulate`(무작위 구매 몬테카를로) 및 `/simulation-history` 라우트의 수정·통합은 하지 않는다.
- 여러 조합 동시 비교(배치 시뮬레이션)는 포함하지 않는다.
- 시뮬레이션 결과의 영구 저장(DB 기록)이나 사용자별 히스토리 관리는 포함하지 않는다.
- 당첨금 금액(원 단위 상금) 산출은 포함하지 않는다 (등수까지만 판정).

---

## 제약사항

- Python 3.9 호환 (`match`/`case` 미사용, `zip(strict=True)` 미사용)
- 기존 SPEC 패턴(SPEC-100~101) 일관성 유지
- 한국어 UI 라벨 사용
- ruff 린트 통과 필수
- mypy 통과 필수 (신규 함수 타입 힌트 완비)
- 면책 고지(disclaimer) 필수 포함
- 기존 `/simulate` 기능과 경로·탭 키 충돌 금지 (신규는 `/stats/simulate`, tab=`combo_simulate`)

---

## 의존성

| 의존 SPEC | 관계 | 비고 |
|-----------|------|------|
| SPEC-LOTTO-100 | 필수 선행 | `get_fitness_score()` 함수 (반환 `fitness_score`, `grade`) 활용 |

`get_fitness_score(numbers: list[int], draws: list[DrawResult] | None) -> dict[str, Any]`가 정상 동작하는 환경이 전제된다. 반환값 중 `fitness_score`(실수)와 `grade`(S/A/B/C/D 문자열) 키를 사용한다.
