---
id: SPEC-LOTTO-103
version: 0.1.0
status: implemented
created: 2026-06-18
updated: 2026-06-18
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-103: 보너스 번호 분석 (Bonus Number Analysis)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 0.1.0 | 2026-06-18 | 최초 작성 | ircp |

---

## 개요

한국 로또 6/45의 **보너스 번호(bonus ball)** 에 대한 역대 패턴을 분석하는 기능이다. 기존 통계 분석 SPEC 계열은 모두 본번호 6개(n1~n6)만 다루고 보너스 번호는 명시적으로 제외해 왔으나, 이 SPEC은 **보너스 번호 자체를 분석 대상으로 삼는** 최초의 기능이다.

다음 5가지 관점을 제공한다.

1. **전체 보너스 빈도(bonus frequency)** — 1~45 각 번호가 보너스 볼로 등장한 횟수와 비율.
2. **번호별 보너스 출현율(appearance rate)** — 전체 회차 대비 각 번호가 보너스 볼이었던 비율(%).
3. **본번호와의 동시 출현(co-occurrence)** — 특정 보너스 번호가 등장한 회차에서, 같은 회차의 본번호 중 가장 자주 함께 나온 번호.
4. **최근 보너스 추세(recent trend)** — 최근 N회차(예: 50/100/200)의 보너스 번호 분포로, 특정 번호가 최근 비정상적으로 자주 나오거나 전혀 안 나왔는지 파악.
5. **본번호·보너스 중복도(overlap)** — 본번호로도 보너스로도 자주 나오는 번호 vs 한쪽으로만 치우치는 번호.

결과는 API 엔드포인트(`GET /api/stats/bonus`)와 서버 렌더링 웹 페이지(`GET /stats/bonus`)로 제공한다.

이 기능은 과거 추첨 데이터에 대한 **회고적(retrospective) 빈도 분석**이며, 미래 보너스 번호를 예측하지 않는다.

---

## 배경

`lotto/web/data.py`에는 역대 추첨 데이터를 반환하는 `get_draws() -> list[DrawResult] | None`가 구현되어 있고, `from __future__ import annotations`가 선언되어 있다. 이 파일에는 SPEC-LOTTO-100의 `get_fitness_score`, SPEC-LOTTO-102의 `get_combo_simulation` 등 분석 함수들이 누적되어 있다.

`lotto/models.py`의 `DrawResult` 모델은 다음 필드를 가진다.

- `n1, n2, n3, n4, n5, n6: int` — 본번호 6개
- `bonus: int` — 보너스 번호
- `draw_no: int` — 회차 번호
- `date: datetime.date` — 추첨일
- `numbers()` — 본번호 6개 `[n1, n2, n3, n4, n5, n6]`를 반환하는 **메서드**(property 아님)

기존 통계 SPEC들은 `draw.numbers()` 만 사용하고 `draw.bonus`는 사용하지 않았다(보너스 제외 원칙). SPEC-103은 이 원칙의 **명시적 예외**로서 `draw.bonus`를 1차 분석 대상으로, `draw.numbers()`를 보조(동시 출현) 분석에 사용한다.

기존 API 라우트(`lotto/web/routes/api.py`)는 GET 메서드에서 nullable 쿼리 파라미터에 `Optional[T] = Query(...)  # noqa: UP045` 패턴을, 범위 검증에 `Query(default=N, ge=, le=)`(위반 시 FastAPI가 자동 HTTP 422)를 사용한다. SPEC-103도 동일 패턴을 따른다.

### 보너스 번호 규칙 (참고)

한국 로또는 매 회차 본번호 6개와 별도로 보너스 번호 1개를 추첨한다. 보너스 번호는 본번호 6개와 중복되지 않으며, 2등 판정(본번호 5개 일치 + 보너스 일치)에만 사용된다. 따라서 한 회차당 보너스 번호는 정확히 1개이다.

---

## 용어 정의

| 용어 | 정의 |
|------|------|
| 보너스 빈도(bonus_frequency) | 1~45 각 번호가 보너스 볼로 등장한 총 횟수 |
| 보너스 비율(bonus_percentage) | (해당 번호 보너스 횟수 / 전체 회차) × 100 (소수 2자리) |
| 동시 출현(cooccurrence) | 특정 보너스 번호가 나온 회차에서 같은 회차의 본번호로 함께 등장한 횟수 |
| 최근 보너스(recent_bonus) | 가장 최근 N회차로 한정한 보너스 빈도 분포 |
| Hot 번호 | 전체 평균 보너스 빈도보다 높은(혹은 최근 비율이 전체 비율보다 높은) 번호 |
| Cold 번호 | 전체 평균 보너스 빈도보다 낮은(혹은 최근 비율이 전체 비율보다 낮은) 번호 |
| Normal 번호 | Hot/Cold 어느 쪽에도 뚜렷하게 속하지 않는 번호 |

---

## 요구사항 (EARS 형식)

### U (Ubiquitous — 항상 적용)

- **REQ-BON-U01**: 시스템은 `get_bonus_analysis(draws, recent_n)` 함수를 제공하며, 반환 dict는 `bonus_frequency`, `bonus_percentage`, `top_bonus`, `recent_bonus`, `cooccurrence`, `total_draws`, `recent_n` 키를 포함해야 한다.
- **REQ-BON-U02**: `bonus_frequency`는 1~45 **모든 45개 키**를 포함해야 하며, 한 번도 보너스로 나오지 않은 번호도 `0`으로 포함되어야 한다(키 누락 금지).
- **REQ-BON-U03**: `bonus_percentage`는 1~45 모든 키를 포함하며, 각 값은 `round(bonus_frequency[k] / total_draws * 100, 2)`(소수 2자리)로 계산한다. `total_draws`가 0이면 모든 값은 `0.0`이다.
- **REQ-BON-U04**: `top_bonus`는 보너스 빈도 내림차순 상위 10개 번호의 리스트(각 항목 `{"number", "count", "percentage"}`)여야 한다. 동률 시 더 작은 번호를 우선한다.
- **REQ-BON-U05**: `recent_bonus`는 가장 최근 `recent_n` 회차로 한정한 보너스 빈도 분포(`dict[int, int]`, 등장한 번호만 포함 또는 1~45 전체 키 — 본 SPEC은 1~45 전체 키 0채움 채택)와 해당 구간 회차 수(`recent_count`)를 포함해야 한다.
- **REQ-BON-U06**: `cooccurrence`는 각 보너스 번호(키)에 대해, 그 보너스가 나온 회차들의 본번호 중 가장 자주 함께 나온 **상위 5개** 본번호 리스트(각 항목 `{"number", "count"}`, 내림차순, 동률 시 작은 번호 우선)를 값으로 가져야 한다.
- **REQ-BON-U07**: 시스템은 각 번호에 대해 본번호 출현 빈도와 보너스 출현 빈도를 비교하여 본번호·보너스 중복도(overlap) 판정에 필요한 데이터를 제공해야 한다. 본 SPEC에서는 `cooccurrence`와 `bonus_frequency`로 이 비교가 가능하므로 별도 overlap 키는 선택 사항(REQ-BON-O02)으로 둔다.
- **REQ-BON-U08**: 동일한 입력 데이터에 대해 결과는 결정적(deterministic)이어야 한다(난수·시간 의존 금지).

### E (Event-driven — 이벤트 발생 시)

- **REQ-BON-E01**: When `GET /api/stats/bonus?recent_n=50` is called, the system shall return JSON containing `bonus_frequency`, `bonus_percentage`, `top_bonus`, `recent_bonus`, `cooccurrence`, `total_draws`, and `recent_n` fields with HTTP 200.
- **REQ-BON-E02**: When the bonus API is called without a `recent_n` query parameter, the system shall default `recent_n` to `50`.
- **REQ-BON-E03**: When `GET /stats/bonus` page is requested, the system shall render `bonus_analysis.html` showing a bonus-frequency representation (top 10 highlighted), a `recent_n` selector, and a per-number table (number | total count | percentage | recent count | status).
- **REQ-BON-E04**: When the bonus page is requested with a `recent_n` query parameter, the page shall reflect that window in the recent-count column and status calculation.

### S (State-driven — 상태 조건)

- **REQ-BON-S01**: While `get_draws()` returns None or an empty list, the bonus API shall return `total_draws = 0`, all `bonus_frequency` values `0`, all `bonus_percentage` values `0.0`, empty `top_bonus`, empty/zero-filled `recent_bonus`, and empty `cooccurrence` (HTTP 200, 에러 아님).
- **REQ-BON-S02**: While the number of available draws is fewer than `recent_n`, the system shall use all available draws as the recent window and set `recent_count` to the actual draw count (no error).
- **REQ-BON-S03**: While computing per-number status, a number whose overall percentage exceeds the average bonus percentage (= 100/45 ≈ 2.22%) shall be classified "hot"; below shall be "cold"; otherwise "normal". (또는 최근 비율 vs 전체 비율 비교 방식 — 구현은 둘 중 하나를 일관되게 채택하고 문서화한다.)

### N (Negative — 금지 사항)

- **REQ-BON-N01**: The system shall NOT accept `recent_n` outside the range 1–500; out-of-range values shall return HTTP 422 (FastAPI `Query(ge=1, le=500)`).
- **REQ-BON-N02**: The system shall NOT count a bonus number toward main-number frequency, and shall NOT count main numbers toward bonus frequency; the two distributions are kept separate.
- **REQ-BON-N03**: The system shall NOT claim the analysis predicts future bonus numbers; the API response and UI must include a retrospective disclaimer.
- **REQ-BON-N04**: The system shall NOT use `zip(strict=True)` (필요 시 `# noqa: B905`) nor `match`/`case` syntax (use `if/elif/else`).
- **REQ-BON-N05**: The system shall NOT modify core modules under `lotto/*.py` (except adding the function in `lotto/web/data.py`); analysis logic lives in `lotto/web/data.py`.
- **REQ-BON-N06**: The web page shall NOT rely on client-side JavaScript for the core table rendering; the page must render server-side (JS는 선택적 향상에 한함).

### O (Optional — 선택 사항)

- **REQ-BON-O01**: Where the recent window and overall distribution diverge for a number, the page may flag "최근 급증"(recent surge) or "최근 부재"(recently absent) badges for readability.
- **REQ-BON-O02**: Where useful, the analysis may include an explicit `overlap` key mapping each number to `{"main_count", "bonus_count"}` so the UI can directly contrast main-vs-bonus tendency.
- **REQ-BON-O03**: The `recent_n` selector may offer preset options (50, 100, 200) in addition to the default.

---

## 기술적 접근 방법

### 핵심 분석 함수

`lotto/web/data.py`에 다음 함수를 추가한다.

```python
# SPEC-LOTTO-103: 보너스 번호 분석
def get_bonus_analysis(
    draws: list[DrawResult] | None,
    recent_n: int = 50,
) -> dict[str, Any]:
    """역대 보너스 번호의 빈도·비율·동시출현·최근추세를 분석한다.

    Returns:
        {
          "total_draws", "recent_n", "recent_count",
          "bonus_frequency", "bonus_percentage",
          "top_bonus", "recent_bonus", "cooccurrence", "disclaimer"
        }
    """
    ...
```

처리 흐름:

1. `draws`가 None/빈 리스트면 빈 분석 반환(REQ-BON-S01): 1~45 키를 0/0.0으로 채우고 나머지는 빈 값.
2. `total_draws = len(draws)`.
3. `bonus_frequency = {n: 0 for n in range(1, 46)}` 초기화 후 각 `draw.bonus`로 `+= 1`.
4. `bonus_percentage[n] = round(bonus_frequency[n] / total_draws * 100, 2)`.
5. `top_bonus`: 빈도 내림차순·번호 오름차순 정렬 후 상위 10개를 `{"number","count","percentage"}` 리스트로.
6. `recent_bonus`: `draws[-recent_n:]`(또는 회차 정렬 기준 최근 N개)에 대해 동일 빈도 집계, `recent_count = min(recent_n, total_draws)`.
7. `cooccurrence`: 각 보너스 번호별로, 그 보너스가 나온 회차들의 `draw.numbers()` 본번호를 카운트하여 상위 5개.
8. `disclaimer` 포함.

### 동시 출현(cooccurrence) 계산 (Python 3.9 호환)

```python
from collections import Counter

cooc_counters: dict[int, Counter] = {n: Counter() for n in range(1, 46)}
for draw in draws:
    b = draw.bonus
    for main in draw.numbers():  # numbers()는 메서드
        cooc_counters[b][main] += 1

cooccurrence: dict[int, list[dict[str, int]]] = {}
for b in range(1, 46):
    # 동률 시 작은 번호 우선: (-count, number) 키로 정렬
    items = sorted(cooc_counters[b].items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    cooccurrence[b] = [{"number": num, "count": cnt} for num, cnt in items]
```

### 최근 추세 슬라이싱

`get_draws()`가 회차 오름차순으로 정렬되어 있다고 가정하면 `draws[-recent_n:]`가 최근 구간이다. 정렬 가정이 불확실하면 `sorted(draws, key=lambda d: d.draw_no)[-recent_n:]`로 안전하게 처리한다. `recent_count = len(recent_slice)`.

### 상태(hot/cold/normal) 판정

평균 보너스 비율은 `100 / 45 ≈ 2.2222%`. 구현은 다음 중 하나를 일관되게 채택한다.

- 방식 A(전체 기준): `bonus_percentage[n] > 평균` → "hot", `< 평균` → "cold", 그 외 "normal".
- 방식 B(최근 vs 전체): 최근 구간 비율 > 전체 비율 → "hot", 반대면 "cold".

본 SPEC은 **방식 A**를 1차 채택(단순·결정적)하되, 방식 B 부가 표시는 REQ-BON-O01의 선택 배지로 둔다. (구현 단계에서 어느 방식을 채택했는지 `data.py` docstring에 명시한다.)

### API 응답 구조 예시

```json
{
  "total_draws": 1180,
  "recent_n": 50,
  "recent_count": 50,
  "bonus_frequency": {"1": 28, "2": 31, "...": 0, "45": 22},
  "bonus_percentage": {"1": 2.37, "2": 2.63, "...": 0.0, "45": 1.86},
  "top_bonus": [
    {"number": 27, "count": 38, "percentage": 3.22},
    {"number": 2, "count": 31, "percentage": 2.63}
  ],
  "recent_bonus": {"frequency": {"1": 1, "...": 0}, "recent_count": 50},
  "cooccurrence": {
    "27": [{"number": 13, "count": 9}, {"number": 40, "count": 8}]
  },
  "disclaimer": "이 분석은 과거 회차 보너스 번호에 대한 회고 분석이며 미래 보너스 번호를 예측하지 않습니다."
}
```

> JSON 키는 정수 dict를 직렬화하므로 문자열 키가 될 수 있다. 구현 시 응답 일관성(int vs str 키)은 기존 통계 SPEC의 직렬화 관례를 따른다(테스트는 `str(n)` 또는 `int(n)` 한쪽으로 일관되게 검증).

---

## 수정 대상 파일

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `lotto/web/data.py` | 수정 | `get_bonus_analysis(draws, recent_n) -> dict[str, Any]` 추가 (보너스 빈도/비율/top/recent/cooccurrence) |
| `lotto/web/routes/api.py` | 수정 | `GET /api/stats/bonus` 엔드포인트 추가 (`recent_n: int = Query(default=50, ge=1, le=500)`) |
| `lotto/web/routes/pages.py` | 수정 | `GET /stats/bonus` 페이지 라우트 추가 (active_tab=`bonus`) |
| `lotto/web/templates/bonus_analysis.html` | 신규 | 보너스 빈도 막대 표현(top10 강조) + recent_n 선택기 + 번호별 테이블 |
| `lotto/web/templates/base.html` | 수정 | `desktop_nav_items`에 `('/stats/bonus', 'bonus', '보너스 분석')` 추가 + active_tab 헤딩 분기 추가 |
| `tests/test_bonus_analysis.py` | 신규 | TDD 테스트 파일 (손계산 픽스처로 AC 검증) |

---

## 제외 항목 (Exclusions / What NOT to Build)

- 미래 보너스 번호 예측 또는 확률 추정은 이 SPEC의 범위 밖이다.
- 보너스 번호 기반 추천/생성(보너스를 활용한 번호 추천)은 포함하지 않는다.
- 본번호 6개 자체의 빈도 분석(기존 `/analyze`, `/numbers` 등)은 재구현하지 않는다. 본번호는 동시 출현 계산에만 사용한다.
- 보너스 번호의 시계열 그래프(라인 차트) 등 클라이언트 사이드 시각화 라이브러리 도입은 하지 않는다(서버 렌더링 막대 표현으로 한정).
- 보너스 번호 분석 결과의 영구 저장(DB 기록)이나 사용자별 히스토리는 포함하지 않는다.
- 코어 모듈(`lotto/models.py`, `lotto/*.py`) 수정은 하지 않는다.

---

## 제약사항

- Python 3.9 호환 (`match`/`case` 미사용, `zip(strict=True)` 미사용 — 필요 시 `# noqa: B905`)
- `lotto/web/data.py`에만 분석 함수 추가, 코어 모듈 불변
- `DrawResult.numbers()`는 **메서드**이므로 `draw.numbers()`로 호출 (property 아님)
- API GET 라우트의 `recent_n` 검증은 `Query(ge=1, le=500)`로 위임(위반 시 자동 HTTP 422)
- 서버 렌더링 전용(핵심 테이블), 한국어 UI 라벨 사용
- 결정적 결과(난수·시간 의존 금지)
- 면책 고지(disclaimer) API 응답·UI 모두 포함
- ruff 린트 통과 필수, mypy 통과 필수(신규 함수 타입 힌트 완비, `mypy.ini`에 테스트 override 등록)
- 기존 경로·탭 키와 충돌 금지 (신규는 `/stats/bonus`, tab=`bonus`)

---

## 의존성

| 의존 SPEC | 관계 | 비고 |
|-----------|------|------|
| (없음) | — | `get_draws()`와 `DrawResult` 모델만 사용. 다른 SPEC 함수 의존 없음 |

`get_draws() -> list[DrawResult] | None`가 정상 동작하고 `DrawResult`가 `bonus`, `numbers()`, `draw_no`, `date` 필드를 제공하는 환경이 전제된다.

---

## 인수 기준

상세 인수 기준은 `acceptance.md`를 참조한다 (AC-BON-001 ~ AC-BON-020).
