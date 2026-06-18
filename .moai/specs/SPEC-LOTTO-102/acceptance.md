# SPEC-LOTTO-102 인수 기준 (Acceptance Criteria)

## AC-SIM-001: 유효한 6개 번호로 시뮬레이션 결과 반환

**Given** 서버에 당첨 이력 데이터가 존재하고
**When** `POST /api/stats/simulate` 에 body `{"numbers": [3, 12, 21, 30, 38, 45]}` 를 요청하면
**Then** HTTP 200 응답으로 `numbers`, `summary`, `rounds`, `fitness`, `disclaimer` 필드가 포함된 JSON을 반환한다

---

## AC-SIM-002: summary 구조 확인

**Given** 유효한 6개 번호로 시뮬레이션을 요청하고
**When** 응답의 `summary`를 확인하면
**Then** `total_rounds`(정수), `grade_counts`(딕셔너리), `grade_percentages`(딕셔너리)가 포함된다
**And** `grade_counts`와 `grade_percentages`는 각각 `"1등"`, `"2등"`, `"3등"`, `"4등"`, `"5등"`, `"꽝"` 6개 키를 모두 가진다

---

## AC-SIM-003: 미발생 등급도 0으로 포함

**Given** 1등이 한 번도 발생하지 않은 조합으로 시뮬레이션하고
**When** `summary.grade_counts`를 확인하면
**Then** `"1등"` 키가 존재하며 값은 `0`이다 (키 누락이 아니다)

---

## AC-SIM-004: 등급별 비율 합 ≈ 100%

**Given** 당첨 이력이 1회 이상 존재하는 상태에서 시뮬레이션하고
**When** `summary.grade_percentages` 값들을 합산하면
**Then** 합계가 100.0에 근사한다 (반올림 오차 허용, 99.9 ~ 100.1)

---

## AC-SIM-005: 회차별 상세 구조

**Given** 유효한 6개 번호로 시뮬레이션하고
**When** 응답의 `rounds` 배열 각 항목을 확인하면
**Then** 각 항목은 `draw_no`(정수), `date`(문자열), `match_count`(0~6 정수), `bonus_match`(bool), `grade`(문자열) 키를 가진다

---

## AC-SIM-006: 1등 판정

**Given** 특정 회차의 본번호 6개와 정확히 동일한 조합을 입력하고
**When** 해당 회차를 시뮬레이션하면
**Then** 그 회차의 `match_count`는 6, `grade`는 `"1등"`이다

---

## AC-SIM-007: 2등 판정 (5개 일치 + 보너스 일치)

**Given** 어떤 회차의 본번호 중 5개와 그 회차의 보너스 번호를 포함하는 조합을 입력하고
**When** 해당 회차를 시뮬레이션하면
**Then** `match_count`는 5, `bonus_match`는 `true`, `grade`는 `"2등"`이다

---

## AC-SIM-008: 3등 판정 (5개 일치 + 보너스 불일치)

**Given** 어떤 회차의 본번호 중 5개를 포함하되 그 회차의 보너스 번호는 포함하지 않는 조합을 입력하고
**When** 해당 회차를 시뮬레이션하면
**Then** `match_count`는 5, `bonus_match`는 `false`, `grade`는 `"3등"`이다

---

## AC-SIM-009: 4등 / 5등 / 꽝 판정

**Given** 임의의 조합과 회차에 대해
**When** 일치 개수가 4개이면 `grade`는 `"4등"`,
**And** 일치 개수가 3개이면 `grade`는 `"5등"`,
**And** 일치 개수가 3개 미만이면 `grade`는 `"꽝"`이다

---

## AC-SIM-010: match_count는 보너스를 포함하지 않음

**Given** 사용자 조합에 어떤 회차의 보너스 번호가 포함되어 있고 본번호는 3개만 일치하는 경우
**When** 해당 회차를 시뮬레이션하면
**Then** `match_count`는 3(본번호 일치만)이고 보너스는 더해지지 않는다
**And** `grade`는 `"5등"`이다 (4등으로 잘못 승급되지 않는다)

---

## AC-SIM-011: 빈 데이터 상태 — 빈 요약 (HTTP 200)

**Given** 당첨 이력 데이터가 없거나 None인 상태에서
**When** `get_combo_simulation([3,12,21,30,38,45], None)` 또는 빈 리스트로 호출하면
**Then** `summary.total_rounds`는 0, 모든 `grade_counts` 값은 0, 모든 `grade_percentages` 값은 0.0, `rounds`는 빈 배열이다
**And** 에러가 아닌 정상 결과를 반환한다

---

## AC-SIM-012: 잘못된 번호 개수 — 422 에러

**Given** 유저가 6개가 아닌 번호를 전달하고
**When** `POST /api/stats/simulate` body `{"numbers": [1, 2, 3, 4, 5]}` (5개) 를 요청하면
**Then** HTTP 422 응답이 반환된다

**When** body `{"numbers": [1, 2, 3, 4, 5, 6, 7]}` (7개) 를 요청하면
**Then** HTTP 422 응답이 반환된다

---

## AC-SIM-013: 범위 초과 번호 — 422 에러

**Given** 유저가 1~45 범위를 벗어난 번호를 포함하여 전달하고
**When** body `{"numbers": [0, 1, 2, 3, 4, 5]}` (0 포함) 를 요청하면
**Then** HTTP 422 응답이 반환된다

**When** body `{"numbers": [1, 2, 3, 4, 5, 46]}` (46 포함) 를 요청하면
**Then** HTTP 422 응답이 반환된다

---

## AC-SIM-014: 중복 번호 — 422 에러

**Given** 유저가 중복 번호를 포함하여 전달하고
**When** body `{"numbers": [1, 1, 2, 3, 4, 5]}` (1 중복) 를 요청하면
**Then** HTTP 422 응답이 반환된다

---

## AC-SIM-015: 적합도 점수 통합

**Given** 유효한 6개 번호로 시뮬레이션하고
**When** 응답의 `fitness` 객체를 확인하면
**Then** `fitness_score`(0.0~100.0 실수)와 `grade`(S/A/B/C/D 문자열) 키가 포함된다
**And** 이 값은 동일 번호로 `get_fitness_score`를 호출한 결과의 `fitness_score`, `grade`와 일치한다

---

## AC-SIM-016: 번호 순서 독립성

**Given** 동일한 6개 번호가 다른 순서로 제공되고
**When** body `{"numbers": [45, 38, 30, 21, 12, 3]}` 로 요청하면
**Then** `{"numbers": [3, 12, 21, 30, 38, 45]}` 와 동일한 `summary`를 반환한다

---

## AC-SIM-017: 면책 고지 포함

**Given** 유효한 6개 번호로 API를 요청하고
**When** 응답 JSON을 확인하면
**Then** `disclaimer` 필드에 미래 당첨 가능성을 예측하지 않는다는 안내 문구가 포함된다

---

## AC-SIM-018: 웹 페이지 렌더링

**Given** 사용자가 브라우저로 접근하고
**When** `GET /stats/simulate` 를 요청하면
**Then** HTTP 200 응답으로 `simulate_combo.html` 기반 HTML 페이지가 렌더링된다
**And** 번호 6개를 입력하는 폼이 포함된다
**And** 면책 고지 문구가 페이지에 표시된다

---

## AC-SIM-019: 웹 페이지 폼 제출 흐름

**Given** 사용자가 `/stats/simulate` 페이지에서 6개 번호를 입력하고 "시뮬레이션 실행" 버튼을 클릭하면
**When** JavaScript가 `POST /api/stats/simulate` 를 fetch로 호출하면
**Then** 전체 페이지 새로고침 없이 등급 분포 테이블과 적합도 점수가 화면에 표시된다

---

## AC-SIM-020: 내비게이션 링크 및 기존 경로 무충돌

**Given** 임의의 페이지가 렌더링된 상태에서
**When** HTML 소스의 내비게이션을 확인하면
**Then** "조합 시뮬레이션" 링크(`/stats/simulate`)가 포함되어 있다
**And** 기존 "시뮬레이션"(`/simulate`) 링크는 그대로 유지되며 두 경로가 충돌하지 않는다

---

## Definition of Done

- [x] AC-SIM-001 ~ AC-SIM-020 전부 통과
- [x] `get_combo_simulation`, `_judge_grade` 함수 구현 및 타입 힌트 완비
- [x] `POST /api/stats/simulate` 엔드포인트 동작 (검증 위반 시 HTTP 422)
- [x] `GET /stats/simulate` 페이지 및 `simulate_combo.html` 렌더링
- [x] `base.html` 내비게이션에 "조합 시뮬레이션" 추가, active_tab 헤딩 분기 추가
- [x] 기존 `/simulate` 및 `/simulation-history` 라우트 미변경
- [x] Python 3.9 호환 (match/case·zip strict 미사용)
- [x] ruff 린트 통과
- [x] mypy 통과
- [x] 신규 테스트 47개 추가 (2781 → 2828), 전체 테스트 스위트 그린
- [x] 면책 고지 API 응답·UI 모두 포함
