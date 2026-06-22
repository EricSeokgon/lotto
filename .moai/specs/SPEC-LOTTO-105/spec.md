---
id: SPEC-LOTTO-105
version: 0.1.0
status: completed
created: 2026-06-22
updated: 2026-06-22
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-105: 번호 위치별 분포 분석 (Number Position Distribution Analysis)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 0.1.0 | 2026-06-22 | 최초 작성 | ircp |

---

## 개요

한국 로또 6/45의 당첨번호 본번호 6개를 오름차순으로 정렬했을 때, 각 **위치(position)** — 1번째(가장 작은 수)부터 6번째(가장 큰 수)까지 — 에는 통계적으로 어떤 번호 구간이 자주 나타나는지에 대한 고유한 분포가 존재한다. 예를 들어 1번째 위치(최소값)에는 20보다 큰 번호가 거의 나타나지 않고, 6번째 위치(최대값)에는 26보다 작은 번호가 거의 나타나지 않는다.

이 SPEC은 전체 회차의 정렬된 당첨번호로부터 **위치별 통계 요약**을 계산하여 제공한다.

다음 관점을 제공한다.

1. **위치별 빈도표(position frequency table)** — 6개 위치 각각에 대해, 번호 1~45가 그 위치에 나타난 횟수.
2. **위치별 평균/중앙값(avg / median)** — 각 위치에 나타난 번호들의 산술평균과 중앙값(소수 2자리).
3. **위치별 범위(min_ever / max_ever)** — 각 위치에서 역대 관측된 최소/최대 번호.
4. **위치별 최빈 번호(most common number per position)** — 각 위치에서 빈도 상위 N개 번호.
5. **위치별 분산 지표(std)** — 각 위치 분포의 표본 표준편차(소수 2자리). 분포가 얼마나 넓은지/좁은지를 나타낸다.

결과는 API 엔드포인트(`GET /api/stats/position`)와 서버 렌더링 웹 페이지(`GET /stats/position`)로 제공한다.

이 기능은 과거 추첨 데이터에 대한 **회고적(retrospective) 위치 분포 분석**이며, 미래 출현을 예측하지 않는다. "1번째 위치는 보통 작은 수가 나오니 작은 수를 골라야 한다"는 식의 도박사의 오류를 주장하지 않는다.

---

## 배경

기존에 `number_stats(number)`(SPEC-LOTTO-030) 함수가 **특정 번호 1개에 대해** "그 번호가 6개 위치 각각에 몇 번 나왔는지(by_position)"를 제공한다. 이는 번호를 고정하고 위치를 펼쳐 보는 **번호 중심(per-number)** 관점이다.

SPEC-105는 그 역방향인 **위치 중심(per-position)** 관점을 제공한다. 즉 위치를 고정하고, 그 위치에 어떤 번호들이 어떤 분포로 나타났는지를 통계 요약(평균·중앙값·최소·최대·표준편차·최빈 번호)과 함께 보여준다. 두 기능은 같은 원자료(정렬된 당첨번호)를 사용하지만 집계 축(axis)이 다른 별개의 분석이다.

이 분석은 로또 번호 조합이 정렬되었을 때의 자연스러운 구조적 특성을 드러내며, 사용자가 자신이 선택한 조합의 위치별 분포가 역대 패턴과 얼마나 부합하는지를 직관적으로 파악하도록 돕는다.

---

## 용어 정의

| 용어 | 정의 |
|------|------|
| 위치(position) | 한 회차의 본번호 6개를 오름차순 정렬했을 때의 순번. 1=가장 작은 수, 6=가장 큰 수. |
| 정렬된 당첨번호 | `draw.numbers()`가 반환하는 본번호 6개를 오름차순으로 정렬한 리스트(보너스 제외). |
| avg | 한 위치에 나타난 모든 번호의 산술평균(소수 2자리). |
| median | 한 위치에 나타난 모든 번호의 중앙값(소수 2자리). |
| min_ever / max_ever | 한 위치에서 역대 관측된 최소/최대 번호(정수). |
| std | 한 위치에 나타난 번호들의 **표본 표준편차**(sample standard deviation, `statistics.stdev`, 소수 2자리). 표본이 1개면 계산 불가하여 `0.0`. |
| top_numbers | 한 위치에서 빈도 상위 `top_n`개 번호 목록. 각 항목은 `{number, count, pct}`. |
| pct | `round(count / total_draws * 100, 2)`. |
| top_n | 위치별로 반환할 최빈 번호 개수. 기본 5, 범위 1~45. |

---

## 요구사항 (EARS)

### Ubiquitous (상시)

- **REQ-POS-001**: 시스템은 `get_position_distribution(draws, top_n=5)` 함수를 제공하여 `dict[str, Any]` 구조를 반환해야 한다(shall).
- **REQ-POS-002**: 시스템은 분석에 각 회차의 본번호 6개만 사용해야 하며(shall) 보너스 번호는 절대 포함하지 않아야 한다.
- **REQ-POS-003**: 시스템은 각 회차의 본번호를 오름차순으로 정렬한 뒤 위치 인덱스(0~5)에 매핑해야 한다(shall).
- **REQ-POS-004**: 반환 dict는 `total_draws`(int), `top_n`(int), `positions`(길이 6 리스트), `disclaimer`(str) 키를 항상 포함해야 한다(shall).
- **REQ-POS-005**: `positions` 리스트의 각 항목은 `position`(1~6, 인덱스 0이 위치 1), `avg`, `median`, `min_ever`, `max_ever`, `std`, `top_numbers` 키를 포함해야 한다(shall).
- **REQ-POS-006**: 시스템은 `avg`, `median`, `std`를 소수 둘째 자리로 반올림해야 한다(shall).
- **REQ-POS-007**: 시스템은 각 위치의 `top_numbers`를 빈도(count) 내림차순으로 정렬해야 하며(shall), 빈도가 동률이면 더 작은 번호를 우선해야 한다.
- **REQ-POS-008**: 시스템은 각 `top_numbers` 항목의 `pct`를 `round(count / total_draws * 100, 2)`로 계산해야 한다(shall).
- **REQ-POS-009**: 시스템은 결과를 결정적(deterministic)으로 산출해야 하며(shall), 동일 입력에 대해 항상 동일 출력을 보장해야 한다.

### Event-Driven (이벤트 기반)

- **REQ-POS-010**: `GET /api/stats/position` 요청을 받으면(when), 시스템은 HTTP 200과 함께 `get_position_distribution`의 결과를 JSON으로 반환해야 한다(shall).
- **REQ-POS-011**: `GET /stats/position` 요청을 받으면(when), 시스템은 `position_distribution.html`을 `active_tab="position"`으로 서버 렌더링하여 반환해야 한다(shall).
- **REQ-POS-012**: `top_n` 쿼리 파라미터가 주어지면(when), 시스템은 각 위치별로 그 개수만큼의 최빈 번호를 반환해야 한다(shall).

### State-Driven (상태 기반)

- **REQ-POS-013**: 특정 위치에 나타난 서로 다른 번호의 개수가 `top_n`보다 적은 동안(while), 시스템은 존재하는 번호만 `top_numbers`로 반환해야 한다(shall) — 부족분을 0 빈도 항목으로 채우지 않는다.

### Unwanted Behavior (비정상 동작 방지)

- **REQ-POS-014**: 만약(if) `draws`가 비어 있거나 `None`이면, 시스템은 예외를 발생시키지 않고(then) `total_draws=0`, 6개 위치 각각 `avg=0.0`, `median=0.0`, `min_ever=0`, `max_ever=0`, `std=0.0`, `top_numbers=[]`인 결과를 반환해야 한다(shall).
- **REQ-POS-015**: 만약(if) `top_n` 쿼리 파라미터가 1 미만 또는 45 초과이면, 시스템은(then) HTTP 422 검증 오류를 반환해야 한다(shall).
- **REQ-POS-016**: 시스템은 코어 모듈(`lotto/models.py`, `lotto/web/` 외부의 `lotto/*.py`)을 수정하지 않아야 한다(shall not).

### Optional (선택)

- **REQ-POS-017**: 가능한 경우(where) 웹 페이지는 위치별 분포를 시각적으로 비교할 수 있는 표 형태로 표현할 수 있다(may).

---

## 비기능 요구사항

- **NFR-POS-001 (호환성)**: Python 3.9와 호환되어야 한다. `match/case`, `zip(strict=True)`를 사용하지 않는다.
- **NFR-POS-002 (모델 접근)**: 본번호는 `draw.numbers()`(메서드 호출)로 접근하며, 속성 접근(`draw.numbers`)을 사용하지 않는다.
- **NFR-POS-003 (렌더링)**: 핵심 표는 서버 사이드 렌더링으로 제공하며, JavaScript 의존성 없이 동작해야 한다.
- **NFR-POS-004 (정확성)**: 모든 통계는 표본 기반 실제 계산이어야 하며, 추정치를 사용하지 않는다. 표준편차는 `statistics.stdev`(표본)를 사용한다.
- **NFR-POS-005 (면책)**: API 응답과 웹 UI 모두에 `disclaimer`(예측이 아님)를 포함해야 한다.
- **NFR-POS-006 (캐싱)**: 결과는 `str(len(draws))`를 키로 하는 프로세스 수명 캐시에 저장하며, `invalidate_cache()`에서 무효화되어야 한다.
- **NFR-POS-007 (테스트)**: `tests/test_position_distribution.py`로 검증하며, mypy 타입 검사를 통과해야 한다.

---

## 인수 기준

상세 인수 기준과 손계산 검증 픽스처는 [acceptance.md](acceptance.md)를 참조한다. 최소 픽스처(3개 회차)로 위치 1과 위치 6의 양 끝단 통계를 손계산으로 검증하며, 빈/단일 회차·`top_n` 경계·API 검증 동작을 포함한다.

---

## Exclusions (What NOT to Build)

- **번호 중심 by_position 중복 금지**: 기존 `number_stats(number)`(SPEC-LOTTO-030)의 `by_position` 필드(특정 번호가 각 위치에 나온 횟수)를 재구현하거나 수정하지 않는다. SPEC-105는 **위치 중심** 집계로 별개 기능이다.
- **당첨 주기 분석 재사용 금지**: SPEC-LOTTO-047의 `cycle_analysis`를 재사용하거나 수정하지 않는다.
- **출현 주기/간격 분석 중복 금지**: SPEC-LOTTO-104의 `recency`(출현 경과·간격) 분석과 무관하며 중복하지 않는다.
- **예측 기능 없음**: 다음 회차 번호나 "유망 위치 번호"를 예측·추천하지 않는다. 회고적 분포 요약만 제공한다.
- **보너스 번호 분석 없음**: 보너스 번호의 위치 분포는 다루지 않는다(보너스는 정렬 위치 개념이 없음).
- **클라이언트 사이드 차트 필수 아님**: 핵심 표는 서버 렌더링이며, 인터랙티브 차트는 범위 밖이다.
- **코어 모듈 수정 없음**: `lotto/models.py` 및 `lotto/web/` 외부 모듈은 수정하지 않는다.
