# SPEC-LOTTO-039 인수 기준 (acceptance.md)

## Definition of Done

- [ ] `prediction_report(draws=None, recent_n=50)`가 `lotto/web/data.py`에 존재
- [ ] `GET /api/prediction/report?recent_n=50` 엔드포인트 동작
- [ ] `GET /prediction` 페이지 렌더링 동작
- [ ] `prediction.html` 템플릿 존재
- [ ] 최소 12개 신규 테스트, 신규 코드 커버리지 85%+
- [ ] 기존 961개 테스트 전부 통과 (회귀 없음)
- [ ] ruff 통과, Python 3.9 호환 준수
- [ ] 신규 외부 의존성 0개
- [ ] 모든 REQ-PRED-001~018 충족

---

## Given-When-Then 시나리오

### 시나리오 1: 정상 예측 리포트 생성 (REQ-PRED-002, 004~007)
- **Given** 100개 이상의 회차 draws 데이터가 있고
- **When** `prediction_report(draws, recent_n=50)`을 호출하면
- **Then** `top_candidates`는 정확히 10개 항목을 가지며 composite_score
  내림차순(동률 시 번호 오름차순)으로 정렬되어 있고,
- **And** 각 항목은 `{number, composite_score, breakdown}` 구조이며
  `breakdown`은 `frequency/interval/odd_even/range` 4개 키를 갖고,
- **And** `recommended_combinations`는 3세트이며 각 세트는 6개의 서로 다른
  번호를 오름차순으로 담는다.

### 시나리오 2: recent_n이 가용 회차 초과 (REQ-PRED-003, 010)
- **Given** 30개 회차만 보유한 draws 데이터에서
- **When** `prediction_report(draws, recent_n=200)`을 호출하면
- **Then** `draws_analyzed == 30`(가용 전체 사용)이고
- **And** `recent_n == 200`(요청값 그대로 노출)이다.

### 시나리오 3: 빈/None 데이터 방어 (REQ-PRED-009)
- **Given** draws가 `None`이거나 `[]`인 상태에서
- **When** `prediction_report(None)` 또는 `prediction_report([])`을 호출하면
- **Then** 예외 없이 `draws_analyzed=0`, `top_candidates=[]`,
  `recommended_combinations=[]`인 일관된 빈 구조를 반환한다.

### 시나리오 4: composite score 정규화 (REQ-PRED-005)
- **Given** 가중치 상수의 합이 1.0이고 모든 부분 점수가 0.0~1.0일 때
- **When** composite score를 계산하면
- **Then** 모든 후보의 composite_score는 0.0 이상 1.0 이하이다.

### 시나리오 5: 결정성 (REQ-PRED-018)
- **Given** 동일한 draws와 recent_n으로
- **When** `prediction_report`를 두 번 연속 호출하면
- **Then** 두 결과가 완전히 동일하다 (난수 미사용).

### 시나리오 6: 추천 조합 비중복 (REQ-PRED-008)
- **Given** 후보 번호가 10개 이상 생성된 상태에서
- **When** 추천 조합 3세트를 구성하면
- **Then** 세 조합이 서로 완전히 동일하지 않다 (적어도 한 쌍은 다름).

### 시나리오 7: API 정상 응답 (REQ-PRED-011, 012)
- **Given** draws 데이터가 있는 서버에서
- **When** `GET /api/prediction/report?recent_n=50`을 요청하면
- **Then** HTTP 200과 함께 `recent_n`, `draws_analyzed`, `top_candidates`,
  `recommended_combinations` 키를 포함한 JSON을 반환한다.

### 시나리오 8: API 검증 실패 (REQ-PRED-013)
- **Given** 서버가 실행 중일 때
- **When** `GET /api/prediction/report?recent_n=0` 또는 `recent_n=201`을 요청하면
- **Then** HTTP 422를 반환한다.

### 시나리오 9: API 데이터 부재 (REQ-PRED-014)
- **Given** `get_draws()`가 None을 반환하는 상태에서 (patch)
- **When** `GET /api/prediction/report`를 요청하면
- **Then** HTTP 200과 빈 리포트 구조를 반환한다 (500 아님).

### 시나리오 10: 페이지 렌더 (REQ-PRED-015, 016)
- **Given** draws 데이터가 있는 서버에서
- **When** `GET /prediction`을 요청하면
- **Then** HTTP 200과 함께 후보 번호 표·추천 조합 카드를 포함한 HTML을 반환한다.

### 시나리오 11: 페이지 빈 상태 (REQ-PRED-017)
- **Given** `get_draws()`가 None을 반환하는 상태에서 (patch)
- **When** `GET /prediction`을 요청하면
- **Then** HTTP 200과 함께 빈 상태 안내 메시지를 포함한 HTML을 반환한다 (500 아님).

### 시나리오 12: 후보 6개 미만 방어 (REQ-PRED-007 엣지)
- **Given** 표본에서 의미 있는 후보가 6개 미만으로 산출되는 극소 데이터에서
- **When** `prediction_report`를 호출하면
- **Then** 예외 없이 가능한 범위의 조합만 반환하거나 빈 조합을 반환한다.

---

## 엣지 케이스 (Edge Cases)

- recent_n=1 (단일 회차): interval/frequency 분모 처리, 예외 없음
- 모든 번호가 동일 빈도: 동률 타이브레이크(번호 오름차순) 적용
- draws에 정확히 6개 회차만: 정규화 분모 0 방어
- composite_score 동률 다수: 안정 정렬로 번호 오름차순 보장

---

## 품질 게이트 (Quality Gate)

- [ ] `pytest --tb=short -q` 전부 통과 (961 → 973+ tests)
- [ ] 신규 코드(`prediction_report` + 라우트) 커버리지 85% 이상
- [ ] `ruff check` 경고 0
- [ ] `X | Y` 런타임 평가 위치 부재, `zip(strict=)` 미사용 (Python 3.9)
- [ ] `pip` 신규 패키지 설치 없음 (의존성 변화 0)
- [ ] 가중치 합 1.0 검증 테스트 포함
