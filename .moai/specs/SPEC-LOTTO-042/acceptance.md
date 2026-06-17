# SPEC-LOTTO-042 인수 기준 (Acceptance Criteria)

Given-When-Then 형식. 각 항목은 테스트로 검증된다.

## 데이터 레이어 (number_trend)

### AC-1: 정상 구조 반환
- **Given** 유효한 번호 리스트와 draws
- **When** `number_trend([7], recent_n=N, draws)` 호출
- **Then** `recent_n`, `draws_analyzed`, `numbers` 키를 포함하고 `numbers`는 리스트다.

### AC-2: 타임라인 길이
- **Given** 윈도가 산출된 상태
- **When** 각 번호 항목의 `timeline`을 확인
- **Then** `len(timeline) == draws_analyzed`.

### AC-3: 출현 횟수 정확성
- **Given** 픽스처 데이터에서 번호의 실제 출현 횟수가 알려진 상태
- **When** `total_appearances`를 확인
- **Then** 픽스처 내 실제 본번호 출현 횟수와 일치한다.

### AC-4: 평균 간격(avg_gap)
- **Given** 번호가 2회 미만 출현
- **When** `avg_gap`을 확인
- **Then** `None`이다. 2회 이상이면 위치 간격 평균(소수 1자리)이다.

### AC-5: current_gap
- **Given** 번호가 윈도 최신 회차에 출현
- **When** `current_gap`을 확인
- **Then** 0이다. 마지막 출현이 더 과거면 그만큼의 회차 수다.

### AC-6: 빈 draws
- **Given** `draws=[]`
- **When** `number_trend([7], draws=[])` 호출
- **Then** `{"recent_n": ..., "draws_analyzed": 0, "numbers": []}` (예외 없음).

### AC-7: None draws
- **Given** `draws=None`
- **When** `number_trend([7], draws=None)` 호출
- **Then** 빈 구조 반환 (예외 없음).

### AC-8: recent_n 클램프
- **Given** `recent_n`이 전체 회차 수보다 큼
- **When** `draws_analyzed`를 확인
- **Then** `draws_analyzed == 전체 회차 수`.

## API (GET /api/numbers/trend)

### AC-9: 정상 응답
- **Given** 유효 번호 파라미터
- **When** `GET /api/numbers/trend?n=7&n=14`
- **Then** 200, `recent_n`/`draws_analyzed`/`numbers` 키 포함.

### AC-10: 중복 번호 → 422
- **When** `GET /api/numbers/trend?n=7&n=7`
- **Then** 422.

### AC-11: 범위 외 번호 → 422
- **When** `GET /api/numbers/trend?n=0`
- **Then** 422.

### AC-12: 4개 번호 → 422
- **When** `GET /api/numbers/trend?n=1&n=2&n=3&n=4`
- **Then** 422.

### AC-13: 데이터 부재 → 200 + 빈 구조
- **Given** `get_draws`가 None
- **When** `GET /api/numbers/trend?n=7`
- **Then** 200, `draws_analyzed == 0`, `numbers == []`.

## 페이지 (GET /numbers/trend)

### AC-14: 폼 표시
- **When** `GET /numbers/trend` (파라미터 없음)
- **Then** 200 HTML.

### AC-15: 결과 표시
- **Given** draws가 존재
- **When** `GET /numbers/trend?n=7&recent_n=50`
- **Then** 200 HTML, 데이터가 렌더링된다.

### AC-16: 데이터 부재에도 200
- **Given** `get_draws`가 None
- **When** `GET /numbers/trend`
- **Then** 200 (크래시 없음).

### AC-17: 네비게이션 링크
- **When** `GET /`
- **Then** 응답 HTML에 `href="/numbers/trend"` 포함.
