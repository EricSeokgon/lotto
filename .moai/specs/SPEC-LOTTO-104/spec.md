---
id: SPEC-LOTTO-104
version: 0.1.0
status: completed
created: 2026-06-22
updated: 2026-06-22
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-104: 번호 출현 주기 분석 (Number Recency / Interval Analysis)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 0.1.0 | 2026-06-22 | 최초 작성 | ircp |

---

## 개요

한국 로또 6/45의 본번호 1~45 각각에 대해 **마지막 출현 이후 경과 회차(recency)** 와 **출현 간격(interval)** 통계를 분석하는 기능이다. "이 번호는 마지막으로 몇 회차 전에 나왔는가", "평균적으로 몇 회차 간격으로 나오는가(연속 출현 사이의 실제 간격 평균)", "그 간격의 최대/최소는 얼마인가"를 한눈에 제공한다.

다음 관점을 제공한다.

1. **마지막 출현 경과(last_seen_ago)** — 가장 최근 회차를 기준으로 각 번호가 마지막으로 등장한 시점이 몇 회차 전인지. 최근 회차에 나왔으면 `0`, 한 번도 안 나왔으면 `None`.
2. **평균 출현 간격(avg_interval)** — 연속된 두 출현 사이의 간격들의 산술평균(소수 2자리). 출현이 1회 이하라 간격을 계산할 수 없으면 `None`.
3. **최대/최소 간격(max_interval / min_interval)** — 역대 관측된 출현 간격의 최댓값/최솟값. 간격이 없으면 `None`.
4. **출현 횟수(appearance_count)** — 각 번호가 본번호로 등장한 총 횟수.
5. **연체 번호(overdue)** — `last_seen_ago` 내림차순(가장 오래 안 나온 번호 우선) 상위 N개.
6. **최근 출현 번호(recent)** — 가장 최근 회차에 등장한 본번호 목록.

결과는 API 엔드포인트(`GET /api/stats/recency`)와 서버 렌더링 웹 페이지(`GET /stats/recency`)로 제공한다.

이 기능은 과거 추첨 데이터에 대한 **회고적(retrospective) 빈도·간격 분석**이며, 미래 출현을 예측하지 않는다. "오래 안 나온 번호가 곧 나온다"는 식의 도박사의 오류를 주장하지 않는다.

---

## 배경

`lotto/web/data.py`에는 역대 추첨 데이터를 반환하는 `get_draws() -> list[DrawResult] | None`가 구현되어 있고, `from __future__ import annotations`가 선언되어 있다. 이 파일에는 SPEC-LOTTO-100의 `get_fitness_score`, SPEC-LOTTO-103의 `get_bonus_analysis` 등 분석 함수들이 누적되어 있다.

`lotto/models.py`의 `DrawResult` 모델 핵심 필드(읽기 확인 완료):

- `n1~n6: int` — 본번호 6개
- `bonus: int` — 보너스 번호
- `drwNo: int` — 추첨 회차 번호 (필드명은 `drwNo`이며, 외부 명세의 `draw_no`에 해당)
- `date: datetime.date` — 추첨일
- `numbers()` — 본번호 6개를 **오름차순 정렬**해 반환하는 **메서드**(property 아님)

### 기존 유사 기능과의 관계 (중요) — SPEC-LOTTO-047 `cycle_analysis`

`lotto/web/data.py`에는 이미 SPEC-LOTTO-047의 `cycle_analysis()`(웹 경로 `/numbers/cycle`, 탭 키 `cycle`, "당첨 주기")가 존재한다. SPEC-104는 이와 **별개 기능**이며, 병합·재구현하지 않는다. 차이는 다음과 같다.

| 항목 | SPEC-047 `cycle_analysis` | SPEC-104 `get_recency_analysis` (본 SPEC) |
|------|---------------------------|-------------------------------------------|
| 평균 지표 정의 | `avg_cycle = total_draws / appearances` (비율 기반 추정치) | `avg_interval = mean(연속 출현 사이 실제 간격들)` (간격 표본 평균) |
| 간격 분포 | 없음 | `max_interval`, `min_interval` 추가 제공 |
| 미출현 표현 | `current_gap = total_draws`, `status="never"` | `last_seen_ago = None`, `avg_interval = None` |
| 최근 회차 출현 목록 | 없음 | `recent` 키로 제공 |
| 파라미터 | 없음 | `top_n`(연체 상위 N, 기본 10, 1~45) |
| 경로/탭 | `/numbers/cycle`, `cycle` | `/stats/recency`, `recency` |

예: 번호가 회차 인덱스 [3, 7, 12]에 등장하고 전체가 15회차일 때 —
- SPEC-047 `avg_cycle` = 15 / 3 = **5.0**
- SPEC-104 `avg_interval` = mean([7−3, 12−7]) = mean([4, 5]) = **4.5**

두 지표는 서로 다른 질문에 답하므로 공존한다. SPEC-104는 `cycle_analysis`를 호출하거나 수정하지 않고 독립 함수 `get_recency_analysis`를 신설한다.

### 기존 라우트 패턴

- API GET 라우트는 범위 검증에 `Query(default=N, ge=, le=)`(위반 시 FastAPI가 자동 HTTP 422)를 사용한다.
- 페이지 라우트는 `_render(request, "<template>.html", {"active_tab": "<key>", ...})` 패턴을 따른다. 테스트 patch 호환을 위해 라우트 내부에서 `from lotto.web import data as wd`로 동적 호출한다(SPEC-103 `bonus_page` 참조).
- `base.html`의 `desktop_nav_items` 리스트와 `active_tab` 헤딩 분기에 신규 탭을 추가한다.

---

## 용어 정의

| 용어 | 정의 |
|------|------|
| 출현 간격(interval) | 같은 번호가 연속해서 등장한 두 회차 사이의 거리(회차 수). 회차 인덱스 i, j(i<j, 그 사이 동일 번호 미출현)에 대해 `j - i` |
| last_seen_ago | 가장 최근 회차 인덱스 기준, 해당 번호의 마지막 출현까지 경과 회차 수. 최근 회차 출현=0, 미출현=None |
| avg_interval | 한 번호의 모든 출현 간격의 산술평균(소수 2자리). 출현 ≤ 1회면 None |
| max_interval / min_interval | 한 번호의 출현 간격 표본의 최댓값/최솟값. 간격 없음이면 None |
| appearance_count | 한 번호가 본번호로 등장한 총 횟수 |
| overdue | last_seen_ago가 큰(오래 미출현) 번호. None(미출현)은 가장 연체된 것으로 취급해 맨 앞에 정렬 |
| recent | 가장 최근 회차의 본번호 6개 목록 |

---

## 요구사항 (EARS 형식)

### U (Ubiquitous — 항상 적용)

- **REQ-REC-U01**: 시스템은 `get_recency_analysis(draws, top_n)` 함수를 제공하며, 반환 dict는 `numbers`, `overdue`, `recent`, `total_draws`, `top_n`, `disclaimer` 키를 포함해야 한다.
- **REQ-REC-U02**: `numbers`는 1~45 **모든 45개 항목**을 번호 오름차순으로 포함해야 하며, 각 항목은 `number`, `last_seen_ago`, `avg_interval`, `max_interval`, `min_interval`, `appearance_count` 키를 가져야 한다(키 누락 금지).
- **REQ-REC-U03**: 각 번호의 `last_seen_ago`는 가장 최근 회차(회차 오름차순 정렬 후 마지막 인덱스)를 기준으로, 해당 번호 마지막 출현까지의 경과 회차 수여야 한다. 최근 회차에 등장하면 `0`, 한 번도 등장하지 않으면 `None`이어야 한다.
- **REQ-REC-U04**: 각 번호의 `avg_interval`은 연속 출현 간격들의 산술평균을 `round(..., 2)`로 계산한다. 출현 횟수가 1 이하라 간격이 없으면 `None`이어야 한다(0이 아님).
- **REQ-REC-U05**: 각 번호의 `max_interval`/`min_interval`은 출현 간격 표본의 최댓값/최솟값(정수)이어야 하며, 간격이 없으면 둘 다 `None`이어야 한다.
- **REQ-REC-U06**: 각 번호의 `appearance_count`는 본번호(`draw.numbers()`)로 등장한 총 횟수여야 하며, 보너스 출현은 포함하지 않는다.
- **REQ-REC-U07**: `overdue`는 `last_seen_ago` 내림차순 상위 `top_n` 번호의 리스트여야 한다(가장 오래 미출현이 먼저). `last_seen_ago`가 `None`(미출현)인 번호는 가장 연체된 것으로 간주해 최상단에 위치한다. 동률 시 더 작은 번호를 우선한다.
- **REQ-REC-U08**: `recent`는 가장 최근 회차의 본번호 6개를 오름차순 리스트로 포함해야 한다.
- **REQ-REC-U09**: 동일한 입력 데이터에 대해 결과는 결정적(deterministic)이어야 한다(난수·시간 의존 금지).

### E (Event-driven — 이벤트 발생 시)

- **REQ-REC-E01**: When `GET /api/stats/recency?top_n=10` is called, the system shall return JSON containing `numbers`, `overdue`, `recent`, `total_draws`, `top_n`, and `disclaimer` with HTTP 200.
- **REQ-REC-E02**: When the recency API is called without a `top_n` query parameter, the system shall default `top_n` to `10`.
- **REQ-REC-E03**: When `GET /stats/recency` page is requested, the system shall render `recency_analysis.html` showing a 45-number table (number | last_seen_ago | avg_interval | appearance_count), an overdue highlight, and a recent-number badge group.
- **REQ-REC-E04**: When the recency page is requested with a `top_n` query parameter, the page shall reflect that value in the overdue list size.

### S (State-driven — 상태 조건)

- **REQ-REC-S01**: While `get_draws()` returns None or an empty list, the recency analysis shall return `total_draws = 0`, all 45 `numbers` items with `last_seen_ago = None`, `avg_interval = None`, `max_interval = None`, `min_interval = None`, `appearance_count = 0`, an empty `overdue`, an empty `recent`, and the `disclaimer` (HTTP 200, 에러 아님).
- **REQ-REC-S02**: While a number appears exactly once, the system shall set its `avg_interval`, `max_interval`, `min_interval` to `None` (간격 표본 없음) while keeping `appearance_count = 1` and a valid `last_seen_ago`.
- **REQ-REC-S03**: While the overdue page renders, a number whose `last_seen_ago` exceeds `avg_interval * 1.5` (avg_interval가 None이 아닐 때) shall be visually highlighted as overdue.

### N (Negative — 금지 사항)

- **REQ-REC-N01**: The system shall NOT accept `top_n` outside the range 1–45; out-of-range values shall return HTTP 422 (FastAPI `Query(ge=1, le=45)`).
- **REQ-REC-N02**: The system shall NOT count bonus-number appearances toward `appearance_count` or interval computation; only main numbers (`draw.numbers()`) are used.
- **REQ-REC-N03**: The system shall NOT claim the analysis predicts future numbers; the API response and UI must include a retrospective disclaimer (도박사의 오류 경계 포함).
- **REQ-REC-N04**: The system shall NOT use `zip(strict=True)` (필요 시 `# noqa: B905`) nor `match`/`case` syntax (use `if/elif/else`).
- **REQ-REC-N05**: The system shall NOT modify core modules under `lotto/*.py` (`get_recency_analysis`는 `lotto/web/data.py`에만 추가); SPEC-047 `cycle_analysis`도 수정·재구현하지 않는다.
- **REQ-REC-N06**: The web page shall NOT rely on client-side JavaScript for the core table rendering; the page must render server-side (JS는 선택적 향상에 한함).

### O (Optional — 선택 사항)

- **REQ-REC-O01**: Where useful, the per-number table may also surface `max_interval`/`min_interval` columns for fuller interval distribution context.
- **REQ-REC-O02**: Where a number is currently overdue, the page may show a "연체" 배지와 함께 `last_seen_ago / avg_interval` 비율을 표시할 수 있다.
- **REQ-REC-O03**: The `top_n` selector may offer preset options (5, 10, 20) in addition to the default.

---

## 기술적 접근 방법

### 핵심 분석 함수

`lotto/web/data.py`에 다음 함수를 추가한다.

```python
# SPEC-LOTTO-104: 번호 출현 주기(recency / interval) 분석
def get_recency_analysis(
    draws: list[DrawResult] | None,
    top_n: int = 10,
) -> dict[str, Any]:
    """번호 1~45의 마지막 출현 경과·출현 간격(평균/최대/최소) 통계를 분석한다.

    Returns:
        {
          "total_draws", "top_n",
          "numbers": [{number, last_seen_ago, avg_interval,
                       max_interval, min_interval, appearance_count}, ...] (45개),
          "overdue": [...], "recent": [...], "disclaimer": "..."
        }
    """
    ...
```

처리 흐름:

1. `draws`가 None/빈 리스트면 빈 분석 반환(REQ-REC-S01): 45개 항목을 None/0으로 채우고 `overdue`/`recent`는 빈 리스트.
2. 회차 오름차순 정렬: `sorted_draws = sorted(draws, key=lambda d: d.drwNo)`. `total_draws = len(sorted_draws)`, `last_idx = total_draws - 1`.
3. 단일 패스로 각 번호의 출현 인덱스 리스트를 수집:
   `occ_idx: dict[int, list[int]] = {n: [] for n in range(1, 46)}`,
   각 `idx, draw`에 대해 `for n in draw.numbers(): occ_idx[n].append(idx)`.
4. 각 번호별로:
   - `appearance_count = len(occ_idx[n])`
   - 출현이 없으면 `last_seen_ago=None, avg/max/min=None, count=0`.
   - 출현이 있으면 `last_seen_ago = last_idx - occ_idx[n][-1]`.
   - 간격: `gaps = [occ_idx[n][i+1] - occ_idx[n][i] for i in range(len(occ_idx[n]) - 1)]`.
     `gaps`가 비면(=1회 출현) `avg/max/min = None`, 아니면
     `avg_interval = round(sum(gaps)/len(gaps), 2)`, `max_interval = max(gaps)`, `min_interval = min(gaps)`.
5. `overdue`: `last_seen_ago`를 정렬 키로 사용하되 None을 최대값으로 취급.
   동률 시 작은 번호 우선: `key=lambda item: (-(inf if last is None else last), number)` 형태로 안정 정렬 후 상위 `top_n`.
6. `recent`: `sorted_draws[-1].numbers()` (빈 데이터면 `[]`).
7. `disclaimer` 포함.

### overdue 정렬 (None 최우선, Python 3.9 호환)

```python
import math

def _overdue_key(number: int, last_seen_ago: Optional[int]) -> tuple[float, int]:
    # None(미출현)을 가장 연체된 것으로: 정렬 시 last_seen_ago 내림차순이므로
    # -inf 대신 +inf를 "값"으로 두고 (-값, 번호) 오름차순 정렬한다.
    val = math.inf if last_seen_ago is None else float(last_seen_ago)
    return (-val, number)

overdue_sorted = sorted(per_number, key=lambda x: _overdue_key(x["number"], x["last_seen_ago"]))
overdue = overdue_sorted[:top_n]
```

> 동률(같은 last_seen_ago)에서는 (-val 동일) → 번호 오름차순으로 작은 번호 우선(REQ-REC-U07).

### API 응답 구조 예시

```json
{
  "total_draws": 1180,
  "top_n": 10,
  "numbers": [
    {"number": 1, "last_seen_ago": 3, "avg_interval": 6.42,
     "max_interval": 21, "min_interval": 1, "appearance_count": 184},
    {"number": 2, "last_seen_ago": 0, "avg_interval": 6.51,
     "max_interval": 25, "min_interval": 1, "appearance_count": 181}
  ],
  "overdue": [
    {"number": 9, "last_seen_ago": 28, "avg_interval": 6.6, "appearance_count": 178}
  ],
  "recent": [2, 11, 17, 28, 33, 40],
  "disclaimer": "이 분석은 과거 회차에 대한 회고 분석이며 미래 출현을 예측하지 않습니다. 오래 미출현한 번호가 곧 나올 확률이 높아지는 것은 아닙니다."
}
```

> JSON 직렬화 시 정수 키 dict는 사용하지 않고 `numbers`/`overdue`를 **리스트(of dict)** 로 반환하므로 int/str 키 직렬화 모호성이 없다.

---

## 수정 대상 파일

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `lotto/web/data.py` | 수정 | `get_recency_analysis(draws, top_n) -> dict[str, Any]` 추가 (last_seen_ago / avg·max·min interval / appearance_count / overdue / recent) |
| `lotto/web/routes/api.py` | 수정 | `GET /api/stats/recency` 엔드포인트 추가 (`top_n: int = Query(default=10, ge=1, le=45)`) |
| `lotto/web/routes/pages.py` | 수정 | `GET /stats/recency` 페이지 라우트 추가 (active_tab=`recency`) |
| `lotto/web/templates/recency_analysis.html` | 신규 | 45번호 테이블 + overdue 강조 + recent 배지 + top_n 선택기 |
| `lotto/web/templates/base.html` | 수정 | `desktop_nav_items`에 `('/stats/recency', 'recency', '주기 분석')` 추가 + active_tab 헤딩 분기 추가 |
| `tests/test_recency_analysis.py` | 신규 | TDD 테스트 파일 (손계산 픽스처로 AC 검증) |

---

## 제외 항목 (Exclusions / What NOT to Build)

- 미래 번호 출현 예측 또는 "곧 나올 번호" 추정은 이 SPEC의 범위 밖이다(도박사의 오류 금지).
- SPEC-LOTTO-047 `cycle_analysis`(`/numbers/cycle`, "당첨 주기")의 재구현·병합·수정은 하지 않는다. 본 SPEC은 간격 표본 기반 지표(실제 gap의 평균/최대/최소)와 recent 목록을 제공하는 별개 함수다.
- 보너스 번호의 주기/간격 분석은 포함하지 않는다(본번호만 대상). 보너스 분석은 SPEC-LOTTO-103 범위.
- 번호 간 동시출현·궁합·쌍 분석은 포함하지 않는다(기존 SPEC들의 영역).
- 시계열 라인 차트 등 클라이언트 사이드 시각화 라이브러리 도입은 하지 않는다(서버 렌더링 테이블/배지로 한정).
- 분석 결과의 영구 저장(DB 기록)이나 사용자별 히스토리는 포함하지 않는다.
- 코어 모듈(`lotto/models.py`, `lotto/*.py`) 수정은 하지 않는다.

---

## 제약사항

- Python 3.9 호환 (`match`/`case` 미사용, `zip(strict=True)` 미사용 — 필요 시 `# noqa: B905`)
- `lotto/web/data.py`에만 분석 함수 추가, 코어 모듈 불변
- `DrawResult.numbers()`는 **메서드**이므로 `draw.numbers()`로 호출 (property 아님)
- 회차 식별 필드는 `drwNo` (외부 명세의 `draw_no`에 해당)
- API GET 라우트의 `top_n` 검증은 `Query(ge=1, le=45)`로 위임(위반 시 자동 HTTP 422)
- 서버 렌더링 전용(핵심 테이블), 한국어 UI 라벨 사용
- 결정적 결과(난수·시간 의존 금지)
- 면책 고지(disclaimer) API 응답·UI 모두 포함
- ruff 린트 통과 필수, mypy 통과 필수(신규 함수 타입 힌트 완비, `mypy.ini`에 테스트 override 등록)
- 기존 경로·탭 키와 충돌 금지 (신규는 `/stats/recency`, tab=`recency`; 기존 `cycle`과 구분)

---

## 의존성

| 의존 SPEC | 관계 | 비고 |
|-----------|------|------|
| SPEC-LOTTO-047 | 공존(별개 기능) | `cycle_analysis`와 지표 정의가 다름. 호출·수정하지 않음 |
| (그 외 없음) | — | `get_draws()`와 `DrawResult` 모델만 사용 |

`get_draws() -> list[DrawResult] | None`가 정상 동작하고 `DrawResult`가 `numbers()`, `drwNo`, `date` 필드를 제공하는 환경이 전제된다.

---

## 인수 기준

상세 인수 기준은 `acceptance.md`를 참조한다 (AC-REC-001 ~ AC-REC-020).
