---
id: SPEC-LOTTO-014
version: 1.0.0
status: completed
created: 2026-05-26
updated: 2026-05-26
author: ircp
priority: medium
issue_number: null
---

# SPEC-LOTTO-014: 로또 구매 이력 관리

## HISTORY

- 2026-05-26 v1.0.0: 최초 작성 (manager-spec) — 구매 이력 등록·조회·삭제, 등수 자동 계산, ROI 통계 기능 정의

## 메타데이터

| 항목       | 값                                  |
| ---------- | ----------------------------------- |
| SPEC ID    | SPEC-LOTTO-014                      |
| 제목       | 로또 구매 이력 관리                  |
| 상태       | draft                               |
| 작성일     | 2026-05-26                          |
| 작성자     | ircp                                |
| 우선순위   | medium                              |
| 의존 SPEC  | SPEC-LOTTO-001 (DrawResult 모델), SPEC-WEB-001 (FastAPI 라우팅) |

## 개요 (Overview)

### 무엇을 (What)

사용자가 실제로 구매한 로또 번호 세트를 회차(`drwNo`)와 함께 영구 저장하고, 저장된 구매 내역을 추첨 결과와 자동 대조하여 등수와 ROI(투자수익률)를 계산·표시하는 기능을 추가한다. 데이터는 외부 DB 없이 `data/purchases.json` 단일 파일에 JSON 형태로 보관한다.

### 왜 (Why)

- 현재 시스템은 추천·분석·시뮬레이션 기능만 제공하며, 사용자가 실제 구매한 번호를 기록하고 결과를 확인할 수단이 없다.
- 구매 이력을 누적하면 추천 전략의 실효성을 사용자 본인의 실제 결과로 검증할 수 있다.
- 회차별 ROI 추이는 향후 전략 개선 SPEC의 근거 데이터가 된다.

### 범위 (Scope)

#### 포함 (In Scope)

- `data/purchases.json` 파일 기반 구매 이력 영구 저장
- 구매 등록 / 목록 조회 / 단건 삭제 REST API (`POST` / `GET` / `DELETE /api/purchases`)
- Jinja2 웹 UI: 구매 등록 폼, 등수 확인 목록, 통계 요약(누적 투자·당첨금·ROI)
- `draws.csv`와 자동 대조하여 1~5등 또는 "미당첨" / "미추첨" 산출
- Python 3.9.25 호환 코드(no `zip(strict=True)`, no `match/case`, no `X | Y` 런타임 union)
- pytest 기반 단위 테스트 추가 (전체 커버리지 100% 유지 목표)

#### 제외 (Out of Scope / Exclusions)

- 외부 DB(SQLite, PostgreSQL 등) 도입 — JSON 단일 파일 유지
- 멀티 사용자 / 인증 / 권한 관리 — 단일 로컬 사용자 가정
- 구매 이력 수정(UPDATE) API — 본 SPEC은 등록·조회·삭제만 제공
- 자동 추첨 결과 갱신 스케줄러 — 기존 수집 워크플로(SPEC-LOTTO-002)에 위임
- 1등·2등 당첨금의 정확한 회차별 금액 — 가변값이므로 "변동" 표기 또는 고정 추정치 사용
- 구매 번호 추천과의 연동(추천된 번호를 한 번에 구매 기록으로 저장) — 별도 SPEC으로 분리
- CSV / Excel 내보내기 기능
- 차트·그래프 시각화(통계는 숫자/표만 제공)

## 요구사항 (Requirements)

### 기능 요구사항 — 데이터 저장 (Functional: Storage)

#### REQ-014-001: 저장 위치 및 형식
- The system **shall** 모든 구매 이력을 `data/purchases.json` 파일에 JSON 배열 형태로 저장해야 한다.
- The system **shall** 파일이 존재하지 않을 때 빈 배열(`[]`)로 자동 생성해야 한다.
- The system **shall** 저장 파일의 인코딩을 UTF-8로 고정해야 한다.

#### REQ-014-002: 데이터 모델
- The system **shall** 각 구매 항목을 다음 필드로 구성해야 한다.
  - `id`: 자동 증가 정수 (1부터 시작, 기존 최대값 + 1)
  - `drwNo`: 추첨 회차 번호 (정수, 사용자가 직접 입력)
  - `numbers`: 1~45 범위의 6개 정수 리스트 (저장 시 오름차순 정렬)
  - `purchased_at`: ISO-8601 형식 타임스탬프 (생성 시각, 서버 로컬 시간)
- The system **shall** Pydantic v2 모델을 사용하여 입출력 시 위 스키마를 검증해야 한다.

#### REQ-014-003: 입력 검증 (Unwanted Behavior)
- **If** `numbers`가 6개가 아니면, **then** the system **shall** HTTP 422 응답을 반환해야 한다.
- **If** `numbers`에 1 미만 또는 45 초과의 값이 포함되면, **then** the system **shall** HTTP 422 응답을 반환해야 한다.
- **If** `numbers`에 중복된 값이 포함되면, **then** the system **shall** HTTP 422 응답을 반환해야 한다.
- **If** `drwNo`가 1 미만의 정수이면, **then** the system **shall** HTTP 422 응답을 반환해야 한다.

### 기능 요구사항 — REST API (Functional: API)

#### REQ-014-010: 구매 등록 API
- **When** 클라이언트가 `POST /api/purchases` 에 유효한 `drwNo`와 `numbers`를 JSON 본문으로 전송하면, **then** the system **shall** 새 항목을 저장하고 HTTP 201과 함께 생성된 항목(`id`, `drwNo`, `numbers`, `purchased_at`)을 반환해야 한다.
- The system **shall** 등록 시 `numbers`를 자동으로 오름차순 정렬하여 저장해야 한다.
- The system **shall** `purchased_at`을 서버에서 자동 생성해야 한다 (클라이언트 입력 무시).

#### REQ-014-011: 구매 목록 조회 API
- **When** 클라이언트가 `GET /api/purchases` 를 호출하면, **then** the system **shall** 저장된 모든 항목과 각 항목의 등수(`prize_rank`)를 포함한 JSON 배열을 HTTP 200으로 반환해야 한다.
- The system **shall** 각 항목에 다음 파생 필드를 추가하여 응답해야 한다.
  - `prize_rank`: `"1st" | "2nd" | "3rd" | "4th" | "5th" | "none" | "pending"` 중 하나
  - `prize_amount`: 정수(KRW), 미당첨/미추첨은 `0`
  - `matched_count`: 본 번호와 일치한 개수 (0~6)
  - `matched_bonus`: 보너스 번호 일치 여부 (불리언, 미추첨 시 `false`)
- The system **shall** 결과를 `id` 내림차순(최신 등록 순)으로 정렬하여 반환해야 한다.

#### REQ-014-012: 구매 삭제 API
- **When** 클라이언트가 `DELETE /api/purchases/{id}` 를 호출하고 해당 `id`가 존재하면, **then** the system **shall** 항목을 삭제하고 HTTP 204를 반환해야 한다.
- **If** 해당 `id`가 존재하지 않으면, **then** the system **shall** HTTP 404를 반환해야 한다.

### 기능 요구사항 — 등수 계산 (Functional: Prize Logic)

#### REQ-014-020: 등수 산출 규칙
- The system **shall** 각 구매 항목의 `drwNo`로 `draws.csv`에서 `DrawResult`를 조회하고, 본 번호 6개와 보너스 번호 1개를 기준으로 다음 규칙에 따라 등수를 산출해야 한다.
  - 1등: 본 번호 6개 일치 → `"1st"`
  - 2등: 본 번호 5개 + 보너스 번호 1개 일치 → `"2nd"`
  - 3등: 본 번호 5개 일치 (보너스 불일치) → `"3rd"`
  - 4등: 본 번호 4개 일치 → `"4th"`
  - 5등: 본 번호 3개 일치 → `"5th"`
  - 미당첨: 본 번호 2개 이하 일치 → `"none"`

#### REQ-014-021: 미추첨 회차 처리
- **If** 요청된 `drwNo`가 `draws.csv`에 존재하지 않으면, **then** the system **shall** `prize_rank = "pending"`, `prize_amount = 0`, `matched_count = 0`, `matched_bonus = False`로 반환해야 한다.
- 한국어 UI 라벨은 `"미추첨"`으로 표시해야 한다.

#### REQ-014-022: 당첨금 산정
- The system **shall** 다음 고정 추정치를 당첨금으로 사용해야 한다.
  - 1등: `"variable"` 표기 (정수 필드는 `0`으로 두고 별도 문자열 라벨로 표시)
  - 2등: `"variable"` 표기 (동일 처리)
  - 3등: 1,500,000 KRW
  - 4등: 50,000 KRW
  - 5등: 5,000 KRW
- The system **shall** 1·2등의 `prize_amount`는 ROI 계산에서 제외(0으로 처리)하고, UI에서 별도로 "변동" 라벨을 표시해야 한다.

### 기능 요구사항 — 웹 UI (Functional: Web UI)

#### REQ-014-030: 구매 등록 폼
- The system **shall** `GET /purchases` 경로에 Jinja2 템플릿 기반 페이지를 제공해야 한다.
- The system **shall** 페이지 상단에 `drwNo` 정수 입력 1개와 6개의 번호 입력(또는 선택) 필드를 포함한 등록 폼을 표시해야 한다.
- **When** 사용자가 폼을 제출하면, **then** the system **shall** `POST /api/purchases`를 호출하고 성공 시 동일 페이지를 새로고침해야 한다.

#### REQ-014-031: 등수 확인 목록
- The system **shall** 등록된 모든 구매 항목을 테이블로 표시하고 각 행에 다음 컬럼을 포함해야 한다.
  - 등록 시각 (`purchased_at`, YYYY-MM-DD HH:MM)
  - 회차 (`drwNo`)
  - 구매 번호 6개 (정렬된 순서)
  - 등수 라벨 (`1등`/`2등`/`3등`/`4등`/`5등`/`미당첨`/`미추첨`)
  - 당첨금 (KRW 콤마 표기, 1·2등은 "변동")
  - 삭제 버튼

#### REQ-014-032: 통계 요약
- The system **shall** 페이지 상단에 다음 3개 지표를 표시해야 한다.
  - 누적 투자액: 구매 항목 수 × 1,000 KRW
  - 누적 당첨금: 3·4·5등 당첨금 합계 (1·2등 제외)
  - ROI: `누적 당첨금 / 누적 투자액`을 백분율로 표시 (투자액이 0이면 `0.0%`)
- The system **shall** 모든 금액을 한국 원화(KRW) 콤마 형식으로 표시해야 한다.

#### REQ-014-033: 네비게이션 연동
- The system **shall** `base.html`의 네비게이션 바에 "구매 이력" 메뉴 항목을 추가하고 `/purchases` 경로로 연결해야 한다.

### 비기능 요구사항 (Non-Functional)

#### NFR-014-001: Python 3.9 호환성
- The system **shall** Python 3.9.25 환경에서 동작해야 한다.
- The system **shall not** `zip(strict=True)`, `match/case`, `X | Y` 런타임 union 문법을 사용해서는 안 된다.
- Type hints의 union은 `Optional[X]` 또는 `Union[X, Y]` (`typing` 모듈) 형식을 사용해야 한다.

#### NFR-014-002: 파일 동시성
- The system **shall** `data/purchases.json` 읽기·쓰기 시 단순 락 없이 동작하나, 단일 사용자 가정하에 read-modify-write 순서를 보장해야 한다.
- The system **shall** 쓰기 실패(디스크 오류 등) 시 HTTP 500을 반환하고 기존 파일을 손상시키지 않아야 한다 (임시 파일 → rename 패턴 권장).

#### NFR-014-003: 테스트 커버리지
- The system **shall** 신규 코드의 라인 커버리지를 100%로 유지해야 한다 (현재 460 tests, 100% 기준선 유지).
- 테스트는 다음 분기를 포함해야 한다.
  - 정상 등록/조회/삭제
  - 입력 검증 실패 (422)
  - 존재하지 않는 ID 삭제 (404)
  - 1·2·3·4·5등 / 미당첨 / 미추첨 각 케이스
  - 빈 파일 / 잘못된 JSON 파일 복구
  - ROI 계산 (투자액 0 포함)

#### NFR-014-004: 코드 스타일 (TRUST 5)
- 모든 코드는 ruff 린트를 0 경고로 통과해야 한다.
- 새로 추가되는 라우트 함수는 한국어 docstring을 포함해야 한다.
- API 응답 모델은 Pydantic v2 `BaseModel` 서브클래스로 정의해야 한다.

#### NFR-014-005: 응답 시간
- The system **shall** 100건 이하의 구매 이력에서 `GET /api/purchases` 응답을 500ms 이내에 반환해야 한다 (`draws.csv` 캐싱 가정).

## 인수 기준 (Acceptance Criteria — 체크리스트)

### AC-1: 데이터 저장
- [ ] `data/purchases.json`이 존재하지 않을 때 `POST /api/purchases` 첫 호출이 파일을 생성하고 항목을 저장한다.
- [ ] 동일 회차에 대해 여러 항목을 등록할 수 있다 (중복 회차 허용).
- [ ] 저장된 `numbers`가 오름차순으로 정렬되어 있다.

### AC-2: REST API
- [ ] `POST /api/purchases`가 유효 입력에 대해 HTTP 201과 생성된 항목을 반환한다.
- [ ] `POST /api/purchases`가 `numbers` 길이 ≠ 6일 때 HTTP 422를 반환한다.
- [ ] `POST /api/purchases`가 1~45 범위 밖 번호에 대해 HTTP 422를 반환한다.
- [ ] `POST /api/purchases`가 중복 번호에 대해 HTTP 422를 반환한다.
- [ ] `GET /api/purchases`가 모든 항목을 `id` 내림차순으로 반환한다.
- [ ] `GET /api/purchases` 응답에 `prize_rank`, `prize_amount`, `matched_count`, `matched_bonus` 파생 필드가 포함된다.
- [ ] `DELETE /api/purchases/{id}`가 존재하는 항목에 대해 HTTP 204를 반환한다.
- [ ] `DELETE /api/purchases/{id}`가 존재하지 않는 항목에 대해 HTTP 404를 반환한다.

### AC-3: 등수 계산
- [ ] 본 번호 6개 일치 시 `prize_rank == "1st"`이다.
- [ ] 본 번호 5개 + 보너스 일치 시 `prize_rank == "2nd"`이다.
- [ ] 본 번호 5개 일치(보너스 불일치) 시 `prize_rank == "3rd"`이다.
- [ ] 본 번호 4개 일치 시 `prize_rank == "4th"`이다.
- [ ] 본 번호 3개 일치 시 `prize_rank == "5th"`이다.
- [ ] 본 번호 2개 이하 일치 시 `prize_rank == "none"`이다.
- [ ] `draws.csv`에 없는 `drwNo`에 대해 `prize_rank == "pending"`이고 `prize_amount == 0`이다.

### AC-4: 웹 UI
- [ ] `GET /purchases` 페이지가 200으로 응답한다.
- [ ] 등록 폼이 `drwNo`와 6개 번호 입력을 포함한다.
- [ ] 등록 후 페이지가 새로고침되어 새 항목이 목록에 나타난다.
- [ ] 목록 테이블이 등록 시각, 회차, 번호, 등수, 당첨금, 삭제 버튼을 표시한다.
- [ ] 통계 요약에 누적 투자액·누적 당첨금·ROI(%)가 표시된다.
- [ ] 투자액이 0일 때 ROI가 `0.0%`로 표시된다 (ZeroDivisionError 미발생).
- [ ] 1·2등 항목의 당첨금 컬럼이 "변동"으로 표시된다.
- [ ] `base.html` 네비게이션에 "구매 이력" 메뉴가 추가되어 있다.

### AC-5: 비기능 / 품질
- [ ] Python 3.9.25에서 모든 테스트가 통과한다.
- [ ] `zip(strict=True)`, `match/case`, `X | Y` 런타임 union 사용이 없다 (grep 검증).
- [ ] 신규 모듈에 대해 100% 라인 커버리지를 달성한다.
- [ ] `ruff check`가 0 경고로 통과한다.
- [ ] `data/purchases.json`이 잘못된 JSON일 때 안전하게 빈 배열로 복구한다 (또는 명시적 에러 로깅).
- [ ] 동시 다발 쓰기 시뮬레이션 테스트에서 기존 파일이 손상되지 않는다 (임시 파일 → rename).

## 영향 받는 파일 (Affected Files — 예상)

### 신규 (New)
- `lotto/purchase.py` — Pydantic 모델 + JSON CRUD + 등수 계산 로직
- `lotto/web/routes/purchases.py` — REST API 라우트 (`/api/purchases`)
- `lotto/web/templates/purchases.html` — 구매 이력 페이지 Jinja2 템플릿
- `tests/test_purchase.py` — 단위 테스트 (모델·CRUD·등수)
- `tests/test_purchases_api.py` — REST API 통합 테스트
- `tests/test_purchases_page.py` — 페이지 라우트 테스트
- `data/purchases.json` — 런타임 생성 (gitignore 추가)

### 수정 (Modified)
- `lotto/web/routes/pages.py` — `GET /purchases` 페이지 라우트 추가
- `lotto/web/templates/base.html` — 네비게이션 메뉴 항목 추가
- `main.py` — 신규 API 라우터 등록
- `.gitignore` — `data/purchases.json` 추가

## 위험 요소 (Risks)

| 위험 | 영향 | 완화 방안 |
| ---- | ---- | --------- |
| `data/purchases.json` 손상 시 전체 이력 손실 | High | 임시 파일 → rename 쓰기 패턴, 잘못된 JSON 시 빈 배열 복구 + 에러 로깅 |
| `draws.csv`가 비어 있거나 누락된 환경 | Medium | `pending` 상태로 우아하게 처리, 테스트 케이스 명시 |
| 1·2등 당첨금이 "변동"이라 ROI가 실제값과 괴리 | Low | UI 라벨로 명시, 향후 SPEC에서 회차별 실제값 도입 검토 |
| 동시 요청 시 race condition | Low | 단일 사용자 가정, 임시 파일 + rename으로 최소 보호 |
| 구매 이력이 수백 건 누적될 때 응답 지연 | Low | 본 SPEC은 100건 기준 NFR-014-005 충족, 초과 시 별도 SPEC에서 페이징 도입 |

## 참고 (References)

- SPEC-LOTTO-001: `DrawResult` 도메인 모델 및 `draws.csv` 스키마
- SPEC-WEB-001: FastAPI + Jinja2 라우팅 패턴
- SPEC-LOTTO-008: 시뮬레이션 기능의 등수 계산 로직 (재사용 가능 여부 검토)
- 동행복권 공식 당첨금 규정: 3·4·5등 금액 출처
