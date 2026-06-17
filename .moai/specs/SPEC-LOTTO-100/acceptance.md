# SPEC-LOTTO-100 인수 기준 (Acceptance Criteria)

## AC-FS-001: 유효한 6개 번호로 적합도 점수 반환

**Given** 서버에 당첨 이력 데이터가 존재하고  
**When** `GET /api/stats/fitness?numbers=1,7,14,23,35,44` 를 요청하면  
**Then** HTTP 200 응답으로 `numbers`, `fitness_score`, `grade`, `breakdown`, `disclaimer` 필드가 포함된 JSON을 반환한다  
**And** `fitness_score`는 0.0 이상 100.0 이하의 실수(소수 2자리)이다  
**And** `breakdown`에는 정확히 15개 통계 항목 키가 포함된다

---

## AC-FS-002: fitness_score 범위 보장

**Given** 임의의 유효한 6개 번호 조합이 주어지고  
**When** `get_fitness_score(numbers, draws)` 함수를 호출하면  
**Then** 반환된 `fitness_score`는 항상 0.0 이상 100.0 이하이다  
**And** `fitness_score`는 소수점 2자리로 반올림된 실수이다

---

## AC-FS-003: 잘못된 번호 개수 — 400 에러

**Given** 유저가 6개가 아닌 번호를 전달하고  
**When** `GET /api/stats/fitness?numbers=1,2,3,4,5` (5개) 를 요청하면  
**Then** HTTP 400 에러가 반환된다  
**And** `detail` 필드에 한국어 오류 메시지가 포함된다

---

## AC-FS-004: 범위 초과 번호 — 400 에러

**Given** 유저가 1~45 범위를 벗어난 번호를 포함하여 전달하고  
**When** `GET /api/stats/fitness?numbers=0,1,2,3,4,5` (0 포함) 를 요청하면  
**Then** HTTP 400 에러가 반환된다

**When** `GET /api/stats/fitness?numbers=1,2,3,4,5,46` (46 포함) 를 요청하면  
**Then** HTTP 400 에러가 반환된다

---

## AC-FS-005: 중복 번호 — 400 에러

**Given** 유저가 중복 번호를 포함하여 전달하고  
**When** `GET /api/stats/fitness?numbers=1,1,2,3,4,5` (1 중복) 를 요청하면  
**Then** HTTP 400 에러가 반환된다

---

## AC-FS-006: 빈 데이터 상태에서의 응답

**Given** 서버에 당첨 이력 데이터가 없거나 None인 상태에서  
**When** `get_fitness_score([1,7,14,23,35,44], None)` 또는 빈 리스트로 함수를 호출하면  
**Then** `fitness_score=0.0`, `grade="데이터 없음"`, `breakdown={}` 를 반환한다

---

## AC-FS-007: breakdown 구조 확인

**Given** 유효한 6개 번호와 당첨 이력 데이터가 존재하고  
**When** `get_fitness_score` 함수를 호출하면  
**Then** `breakdown` 딕셔너리의 각 값은 `label`, `bucket`, `pct` 키를 포함한다  
**And** 각 `pct`는 0.0 이상 100.0 이하이다

---

## AC-FS-008: 등급 분류 정확성

**Given** `fitness_score`가 각 등급 임계값에 해당하는 상황에서  
**When** 점수 등급 함수를 호출하면  
**Then** 다음 분류를 정확히 반환한다:
- 80.0 이상 → "매우 높음"
- 60.0 이상 80.0 미만 → "높음"
- 40.0 이상 60.0 미만 → "보통"
- 20.0 이상 40.0 미만 → "낮음"
- 20.0 미만 → "매우 낮음"
- 0.0 (데이터 없음) → "데이터 없음"

---

## AC-FS-009: 면책 고지 포함

**Given** 유효한 6개 번호로 API를 요청하면  
**When** 응답 JSON을 확인하면  
**Then** `disclaimer` 필드에 당첨 가능성을 예측하지 않는다는 안내 문구가 포함된다

---

## AC-FS-010: 통계적으로 흔한 패턴 → 높은 점수

**Given** 역대 통계에서 높은 빈도를 보이는 특성들로 구성된 조합(예: 홀수 3개, 저번호 3개, 연속 없음, AC값 7~8 수준)을 입력하고  
**When** 적합도 점수를 계산하면  
**Then** `fitness_score`는 50.0 이상이다 (통계적으로 흔한 패턴은 평균보다 높은 점수를 받는다)

---

## AC-FS-011: 통계적으로 드문 패턴 → 낮은 점수

**Given** 역대 통계에서 낮은 빈도를 보이는 특성들로 구성된 조합(예: 모두 홀수 6개, 모두 1단위 번호로 스팬 극소, AC값 0 등 극단적 조합)을 입력하고  
**When** 적합도 점수를 계산하면  
**Then** `fitness_score`는 해당 패턴의 전체 빈도 평균보다 낮다 (드문 패턴은 낮은 점수를 받는다)

---

## AC-FS-012: 웹 페이지 렌더링

**Given** 사용자가 브라우저로 접근하고  
**When** `GET /stats/fitness` 를 요청하면  
**Then** HTTP 200 응답으로 `fitness.html` 기반의 HTML 페이지가 렌더링된다  
**And** 번호 6개를 입력하는 폼이 포함된다  
**And** 면책 고지 문구가 페이지에 표시된다

---

## AC-FS-013: 웹 페이지 번호 폼 제출 흐름

**Given** 사용자가 `/stats/fitness` 페이지에서 6개 번호를 입력하고 "점수 계산" 버튼을 클릭하면  
**When** JavaScript가 `/api/stats/fitness?numbers=...` API를 fetch로 호출하면  
**Then** 페이지 새로고침 없이 Fitness Score와 등급이 화면에 표시된다  
**And** 항목별 breakdown 테이블이 표시된다

---

## AC-FS-014: 사이드바 내비게이션 링크

**Given** 임의의 페이지가 렌더링된 상태에서  
**When** HTML 소스의 사이드바 내비게이션을 확인하면  
**Then** "적합도 점수" 링크(`/stats/fitness`)가 포함되어 있다

---

## AC-FS-015: `numbers` 쿼리 파라미터 미제공 — 422

**Given** 필수 파라미터 `numbers`를 제공하지 않고  
**When** `GET /api/stats/fitness` (파라미터 없음) 를 요청하면  
**Then** HTTP 422 Unprocessable Entity 응답이 반환된다

---

## AC-FS-016: 번호 순서 독립성

**Given** 동일한 6개 번호가 다른 순서로 제공되고  
**When** `GET /api/stats/fitness?numbers=44,35,23,14,7,1` 을 요청하면  
**Then** `GET /api/stats/fitness?numbers=1,7,14,23,35,44` 와 동일한 `fitness_score`를 반환한다

---

## AC-FS-017: 홀짝 항목 breakdown 정확성

**Given** 홀수 4개, 짝수 2개로 구성된 6개 번호(예: 1,3,5,7,2,4)를 입력하고  
**When** 적합도 점수를 계산하면  
**Then** `breakdown["odd_even"]["bucket"]`은 `"4"`(홀수 개수)이다  
**And** `breakdown["odd_even"]["pct"]`는 `get_odd_even_stats` 결과의 `distribution[4]["pct"]`와 동일하다

---

## AC-FS-018: 사분위 항목 breakdown 정확성

**Given** Q1(1-11)에 2개, Q2(12-22)에 1개, Q3(23-33)에 2개, Q4(34-45)에 1개인 조합을 입력하면  
**When** 적합도 점수를 계산하면  
**Then** `breakdown["quartile"]["bucket"]`은 `"2-1-2-1"`이다

---

## AC-FS-019: 구간 커버리지 항목 정확성

**Given** 5개 서로 다른 9-구간을 커버하는 6개 번호를 입력하면  
**When** 적합도 점수를 계산하면  
**Then** `breakdown["zone_coverage"]["bucket"]`은 `"5"`이다  
**And** `breakdown["zone_coverage"]["pct"]`는 `get_zone_coverage_stats` 결과의 `zone_coverage_distribution["5"]["pct"]`와 동일하다

---

## AC-FS-020: 스팬 항목 버킷 매핑

**Given** 번호 1과 44를 포함하는 조합(스팬=43)을 입력하면  
**When** 적합도 점수를 계산하면  
**Then** `breakdown["span"]["bucket"]`은 `"41 이상"` 또는 해당 스팬 구간 라벨이다
