---
id: SPEC-LOTTO-015
version: 0.1.0
status: draft
created: 2026-05-26
updated: 2026-05-26
author: ircp
priority: high
issue_number: null
---

# SPEC-LOTTO-015: 구매 이력 당첨 자동 대조 및 ROI 요약

## HISTORY

- 2026-05-26 v0.1.0: 최초 작성 — `/api/history` 응답에 등수/일치 정보 자동 부착, 웹 UI에 ROI 요약 추가

## 메타데이터

| 항목       | 값                                                              |
| ---------- | --------------------------------------------------------------- |
| SPEC ID    | SPEC-LOTTO-015                                                  |
| 제목       | 구매 이력 당첨 자동 대조 및 ROI 요약                            |
| 상태       | draft                                                           |
| 작성일     | 2026-05-26                                                      |
| 작성자     | ircp                                                            |
| 우선순위   | high                                                            |
| 의존 SPEC  | SPEC-LOTTO-014 (구매 이력 모델·`calc_prize`), SPEC-WEB-001 (FastAPI 라우팅) |

## 개요 (Overview)

### 무엇을 (What)

구매 이력(`/api/history`, `/purchases`, `/history`)이 회차별 추첨 결과와 자동 대조되어 등수·일치 수·당첨금이 모든 응답·화면에 일관되게 노출되도록 통합하고, 누적 투자/당첨/ROI(투자수익률) 요약을 웹 UI 상단에 표시한다.

### 왜 (Why)

- `GET /api/history`는 현재 `lotto/web/data.py::compute_ticket_results()`를 통해 등수를 계산하지만, 응답 필드명·값 체계가 한국어 문자열("1등"/"낙첨"/"미추첨") 기준이며 **당첨금(`prize_amount`)이 포함되지 않는다**. 이미 등수 계산 로직(`lotto/purchase.py::calc_prize`)이 SPEC-LOTTO-014에서 정형화되어 있음에도 두 경로가 분기되어 있어, API 소비자가 등수만 받고 금액은 별도 매핑해야 한다.
- 웹 UI(`purchases.html`)는 건별 등수·당첨금은 표시하지만, "총 투자(1,000원/장)·총 당첨금·ROI%" 같은 **집계 요약이 없어** 사용자가 추천 전략의 실효성을 한눈에 평가할 수 없다.
- 회차 데이터가 아직 수집되지 않은 경우(`데이터 없음`)에도 "미추첨" 상태를 명시적으로 구분해 표시해야 데이터 누락과 낙첨이 혼동되지 않는다.

### 범위 (Scope)

#### 포함 (In Scope)

- `GET /api/history` 응답에 회차별 자동 대조 결과를 부착: `prize_rank`, `prize_amount`, `matched_count`, `matched_bonus`, `draw_numbers`, `draw_bonus`, `draw_date` 7개 필드
- `/api/history`의 등수 계산 로직을 `lotto.purchase.calc_prize()`로 단일화 (중복 함수 `lotto/web/data.py::_calc_prize` 제거 또는 위임)
- 회차 데이터가 없는 경우 `prize_rank="pending"`, `prize_amount=0`, `draw_numbers=[]`으로 일관 응답
- `purchases.html` 통계 요약 영역에 ROI 요약 카드 4종 추가: 총 매수(매), 총 투자(원), 총 당첨금(원), ROI%
- `history.html` 페이지에도 동일한 ROI 요약 카드 표시 (현재 `prize_counts`만 노출됨)
- 1매당 단가는 상수 `TICKET_PRICE_KRW = 1000` (원) 으로 고정
- ROI(%) 계산식: `(총 당첨금 - 총 투자) / 총 투자 * 100`, 총 투자 = 0이면 `0.0` 반환
- 미추첨(`pending`) 티켓은 ROI 계산의 분자/분모 모두에서 제외 (이미 추첨 완료된 회차의 ROI만 측정)

#### 제외 (Out of Scope)

- 1·2등 변동 당첨금(`prize_amount=0` 그대로 유지) — 별도 SPEC에서 외부 공시 데이터 연동 시 처리
- 회차별 ROI 추이 차트, 전략별 ROI 비교 — 후속 SPEC
- 구매 가격 사용자 입력(1매당 가격 가변화) — 1,000원 고정
- 데이터베이스 마이그레이션, 외부 PaymentGateway 연동
- `lotto/web/data.py::compute_ticket_results`의 응답 스키마를 PurchaseResponse로 완전 교체 (UUID 기반 `history.json`과 정수 ID 기반 `purchases.json`은 별도 저장소로 공존 유지)

## EARS 형식 요구사항 (Requirements)

### REQ-PRIZE-001 (Ubiquitous): /api/history 응답 자동 대조

The system **shall** include `prize_rank`, `prize_amount`, `matched_count`, `matched_bonus`, `draw_numbers`, `draw_bonus`, `draw_date` for every record returned by `GET /api/history`.

- `prize_rank` ∈ {`"1st"`, `"2nd"`, `"3rd"`, `"4th"`, `"5th"`, `"none"`, `"pending"`} (영문 코드 통일, 한국어 표시는 템플릿 책임)
- `prize_amount` is integer (원 단위), 1·2등은 `0`, 3등 `1_500_000`, 4등 `50_000`, 5등 `5_000`, 미당첨·미추첨 `0`
- `matched_count` ∈ [0, 6], `matched_bonus` is boolean
- 회차 추첨 데이터가 존재하지 않으면 `prize_rank="pending"`, `matched_count=0`, `matched_bonus=false`, `draw_numbers=[]`, `draw_bonus=0`, `draw_date=""`

### REQ-PRIZE-002 (Event-Driven): 추첨 데이터 미존재 시 명시 구분

**When** a purchase record references a `drwNo` that is not present in the loaded draws, the system **shall** set `prize_rank` to `"pending"` and **shall not** classify the record as `"none"` (낙첨).

### REQ-PRIZE-003 (Ubiquitous): ROI 요약 표시

The web UI (`purchases.html` and `history.html`) **shall** display an aggregate ROI summary block containing:
- 총 매수 (장): 전체 구매 레코드 수
- 총 투자 (원): `매수 수 × 1,000`
- 총 당첨금 (원): 추첨 완료된 레코드의 `prize_amount` 합계
- ROI (%): 소수점 첫째 자리까지, `(총 당첨금 − 총 투자_추첨완료분) / 총 투자_추첨완료분 × 100`. 추첨 완료 매수가 0이면 `0.0%` 표기

### REQ-PRIZE-004 (State-Driven): 미추첨 티켓 ROI 제외

**While** any purchased ticket has `prize_rank == "pending"`, the system **shall** exclude that ticket from both the numerator (당첨금) and denominator (투자) of the ROI calculation, so that uncollected draw rounds do not distort the realized return.

### REQ-PRIZE-005 (Unwanted): 중복 등수 계산 금지

The system **shall not** implement separate prize-classification logic in `lotto/web/data.py`; `compute_ticket_results()` **shall** delegate prize determination to `lotto.purchase.calc_prize()` (single source of truth).

### REQ-PRIZE-006 (Optional): 영문 코드 ↔ 한국어 라벨 매핑

**Where** a Jinja2 template renders `prize_rank`, the template **shall** map English codes to Korean labels using the existing `rank_label` dictionary (`1st→1등`, …, `none→낙첨`, `pending→미추첨`); raw English codes **shall not** appear in user-facing HTML.

## 인수 기준 (Acceptance Criteria)

### AC-PRIZE-001: /api/history 응답 필드 완비

**Given** `data/draws.csv`에 1123회 추첨 결과가 존재하고 사용자가 1123회 번호 `[1,2,3,4,5,6]`을 구매했을 때
**When** `GET /api/history`를 호출하면
**Then** 응답 배열의 해당 레코드에 다음 필드가 모두 포함된다:
- `prize_rank` (문자열, 예: `"1st"`)
- `prize_amount` (정수, 예: `0` for 1등 변동)
- `matched_count` (정수, 0~6)
- `matched_bonus` (bool)
- `draw_numbers` (정수 배열 6개)
- `draw_bonus` (정수, 1~45)
- `draw_date` (ISO 날짜 문자열)

### AC-PRIZE-002: 추첨 데이터 미존재 시 pending 응답

**Given** `data/draws.csv`에 9999회 추첨 결과가 존재하지 않고 사용자가 9999회 번호를 구매했을 때
**When** `GET /api/history`를 호출하면
**Then** 해당 레코드의 `prize_rank == "pending"`, `prize_amount == 0`, `draw_numbers == []`, `draw_date == ""`이며 응답 HTTP 상태는 `200 OK`이다.

### AC-PRIZE-003: ROI 요약 카드 렌더링

**Given** 사용자가 5매 구매(매당 1,000원, 총 투자 5,000원)했고 그 중 3매가 추첨 완료(3등 1매: 1,500,000원, 낙첨 2매)되었으며 2매는 미추첨일 때
**When** `/purchases` 페이지를 GET하면
**Then** HTML에 다음 4개 카드가 표시된다:
- 총 매수: `5`
- 총 투자: `5,000원` (전체 매수 기준)
- 총 당첨금: `1,500,000원`
- ROI: `+49900.0%` ( (1_500_000 − 3*1000) / (3*1000) * 100 = 49900.0 )

### AC-PRIZE-004: 미추첨만 있을 때 ROI 0%

**Given** 모든 구매 레코드의 `prize_rank == "pending"`일 때
**When** `/purchases` 페이지를 GET하면
**Then** ROI 카드는 `0.0%`로 표시되고 "총 당첨금" 카드는 `0원`으로 표시된다 (ZeroDivisionError 미발생).

### AC-PRIZE-005: 단일 등수 계산 함수 사용

**Given** `lotto/web/data.py::compute_ticket_results()`와 `lotto/purchase.py::build_responses()` 양쪽 코드 경로가 존재할 때
**When** 동일한 구매 번호·동일한 회차 대조를 수행하면
**Then** 두 경로 모두 `lotto.purchase.calc_prize()` 함수의 반환 등수와 일치하며, `lotto/web/data.py::_calc_prize` 사설 함수는 제거되거나 `calc_prize` 호출로 위임된다.

### AC-PRIZE-006: 기존 테스트 회귀 없음

**Given** 현재 511개의 테스트가 통과 중일 때
**When** SPEC-LOTTO-015 구현 후 `pytest` 전체 스위트를 실행하면
**Then** 511개 테스트가 모두 통과하고, 새로 추가된 테스트(REQ-PRIZE-001~006 검증)도 모두 통과한다. 커버리지는 현재 수준(>=98%) 이상을 유지한다.

### AC-PRIZE-007: 영문 코드 비노출

**Given** 임의의 구매 이력이 존재할 때
**When** `/purchases` 또는 `/history` 페이지의 렌더링된 HTML을 검사하면
**Then** 사용자에게 노출되는 등수 셀에는 `"1st"`, `"none"`, `"pending"` 같은 영문 코드가 **나타나지 않고** `"1등"`, `"낙첨"`, `"미추첨"`와 같은 한국어 라벨만 표시된다.

## 기술적 접근 (Technical Approach)

### 코드 변경 지점

| 파일 | 변경 내용 |
|------|----------|
| `lotto/web/data.py` | `compute_ticket_results()`: `_calc_prize` 호출 → `lotto.purchase.calc_prize()` 위임. 응답 dict에 `prize_rank`(영문 코드), `prize_amount`, `matched_count`(기존 `matched` 유지), `matched_bonus`(기존 `bonus_match` 유지) 추가 |
| `lotto/web/data.py` | `_calc_prize` 함수 제거 또는 deprecation 주석 (테스트 회귀 위험 시 위임 래퍼로 유지) |
| `lotto/web/routes/api.py` (lines 655-660) | 변경 없음 — `compute_ticket_results()` 반환값이 자동으로 확장됨 |
| `lotto/web/routes/pages.py` (`purchases_page`, `history_page`) | ROI 요약 계산 (총 매수·투자·당첨금·ROI%) 후 템플릿 컨텍스트에 `roi_summary` 추가 |
| `lotto/web/templates/purchases.html` | 기존 `stats` 영역에 4개 카드(매수/투자/당첨금/ROI) 추가 또는 별도 ROI 카드 행 추가 |
| `lotto/web/templates/history.html` | 동일하게 ROI 요약 카드 추가 |
| `lotto/purchase.py` | `TICKET_PRICE_KRW = 1000` 상수 신설, `calc_roi(responses: list[PurchaseResponse]) -> dict[str, Any]` 헬퍼 함수 추가 (총 매수·투자·당첨금·ROI% 반환) |
| `tests/test_purchase.py` (또는 신규 `tests/test_roi.py`) | `calc_roi()` 단위 테스트, `/api/history` 응답 필드 검증, ROI 카드 HTML 렌더링 검증 |

### Python 3.9 호환성 제약

- `zip(strict=True)` 사용 금지 — 명시적 길이 확인
- `X | Y` 런타임 union 금지 — `Optional[X]` 또는 `Union[X, Y]` 사용 (단, `from __future__ import annotations`는 형 힌트에만 적용)
- `match/case` 미사용
- 기존 `lotto/purchase.py`가 이미 `from __future__ import annotations` 사용 중 — 동일 패턴 유지

### 외부 의존성

신규 추가 외부 라이브러리 없음. 표준 라이브러리(`pathlib`, `json`)와 기존 `pydantic`, `fastapi`, `jinja2`만 사용.

## 위험 요소 (Risks)

| 위험 | 영향 | 완화책 |
|------|------|--------|
| `/api/history` 응답 스키마 확장으로 기존 API 소비자 깨짐 | 중 | 필드 추가만 수행하고 기존 필드는 변경하지 않음(하위 호환). 테스트로 보장 |
| `_calc_prize` 제거 시 다른 파일에서 의존 | 중 | Grep으로 호출처 확인 후, 호출처 0이 아니면 위임 래퍼 유지 |
| 1·2등이 `prize_amount=0`이라 ROI 왜곡 | 낮음 | 의도된 동작. SPEC 본문에 명시(범위 제외) 및 별도 SPEC으로 후속 처리 |
| `purchases.json`(SPEC-014)과 `history.json`(legacy) 두 저장소가 별개로 존재 | 낮음 | 본 SPEC은 두 경로 동시 일관화에만 집중. 단일화는 별도 SPEC |

## 제외 사항 (Exclusions / Out of Scope)

명시적으로 본 SPEC에서 **하지 않는** 작업:

1. 1·2등 변동 당첨금 외부 공시 데이터 연동
2. 회차별 ROI 시계열 차트 / 전략별 ROI 비교 UI
3. 1매당 단가의 사용자 입력 가변화 (1,000원 고정)
4. `history.json`(UUID)과 `purchases.json`(정수 ID) 단일 저장소 통합
5. 데이터베이스 마이그레이션, 외부 결제 게이트웨이 연동
6. `PurchaseResponse` 모델로 `/api/history` 응답 형식 완전 교체 (필드 추가만 수행, 기존 dict 키 유지)

## 참고 자료 (References)

- SPEC-LOTTO-014: 로또 구매 이력 관리 (`lotto/purchase.py` 모델·CRUD·`calc_prize` 정의)
- SPEC-WEB-001: 웹 UI 기반 SPEC
- 기존 코드:
  - `lotto/purchase.py:86-120` (`calc_prize` 함수)
  - `lotto/purchase.py:181-202` (`build_responses` 함수, ROI 계산 패턴 참고)
  - `lotto/web/data.py:195-252` (`_calc_prize`, `compute_ticket_results`)
  - `lotto/web/routes/api.py:655-660` (`list_history` 엔드포인트)
  - `lotto/web/templates/purchases.html:37-63` (기존 통계 카드 패턴)
