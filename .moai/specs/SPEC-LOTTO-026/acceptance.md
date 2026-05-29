# SPEC-LOTTO-026 인수 조건

## Given / When / Then 시나리오

### AC-1: 연도별 히트맵 행렬 조회 (REQ-TREND-001)

- **Given** 2023~2025년 회차 데이터가 CSV에 존재할 때
- **When** `GET /api/trend-heatmap?period=yearly`를 호출하면
- **Then** HTTP 200과 함께 `periods=["2023","2024","2025"]`, `numbers=[1..45]`,
  그리고 45 × 3 크기의 `matrix`가 반환된다. 각 셀은 해당 연도의 번호 출현 횟수다.

### AC-2: 분기별 히트맵 행렬 조회 (REQ-TREND-001)

- **Given** 여러 분기에 걸친 회차 데이터가 존재할 때
- **When** `GET /api/trend-heatmap?period=quarterly`를 호출하면
- **Then** `periods`가 `"YYYY-Qn"` 형식으로 시간순 정렬되어 반환되고,
  `matrix` 열 수가 `periods` 길이와 일치한다.

### AC-3: period 잘못된 값 검증 (REQ-TREND-002)

- **Given** API 서버가 실행 중일 때
- **When** `GET /api/trend-heatmap?period=monthly`를 호출하면
- **Then** HTTP 400과 함께 `yearly` 또는 `quarterly`만 허용된다는 메시지가 반환된다.

### AC-4: 핫/콜드 번호 조회 (REQ-TREND-003)

- **Given** 100회 이상의 회차 데이터가 존재할 때
- **When** `GET /api/hot-cold?recent_n=20`을 호출하면
- **Then** `hot` 배열에 평균 대비 출현이 높은 상위 10개 번호가,
  `cold` 배열에 하위 10개 번호가 각각 `{number, recent_count, avg_count, diff}` 형태로 반환된다.

### AC-5: recent_n 기본값 동작 (REQ-TREND-003)

- **Given** 회차 데이터가 충분히 존재할 때
- **When** `GET /api/hot-cold`을 `recent_n` 없이 호출하면
- **Then** `recent_n=20`이 기본 적용되어 핫/콜드 결과가 반환된다.

### AC-6: 트렌드 탭 시각화 (REQ-TREND-006)

- **Given** `/analyze` 페이지에 접속한 상태에서
- **When** "트렌드" 탭을 선택하면
- **Then** 번호별 × 기간별 색상 히트맵 테이블과 핫/콜드 번호 카드가 표시되고,
  연도/분기 토글로 기간 단위를 전환할 수 있다.

## 엣지 케이스 (Edge Cases)

### EC-1: 데이터 전무 (REQ-TREND-005)

- **Given** CSV에 회차 데이터가 한 건도 없을 때
- **When** `GET /api/trend-heatmap` 또는 `GET /api/hot-cold`를 호출하면
- **Then** HTTP 404가 아니라 HTTP 200과 빈 결과(`periods: []`, `matrix: []`, `hot: []`, `cold: []`)가 반환된다.

### EC-2: recent_n이 전체 회차보다 큼 (REQ-TREND-004)

- **Given** 전체 회차가 10회뿐인 상태에서
- **When** `GET /api/hot-cold?recent_n=50`을 호출하면
- **Then** 존재하는 10회 전체를 대상으로 계산하며 오류 없이 결과를 반환한다.

### EC-3: recent_n 비정상 값

- **Given** API 서버가 실행 중일 때
- **When** `recent_n=0` 또는 음수로 호출하면
- **Then** 최소값 1로 보정하거나 HTTP 400으로 명확히 거부한다 (구현 시 일관 정책 적용).

### EC-4: 추첨일 파싱 실패 회차 존재

- **Given** 일부 회차의 추첨일 형식이 비정상일 때
- **When** 히트맵 행렬을 계산하면
- **Then** 해당 회차는 집계에서 제외(스킵)되고 로그가 남으며, 나머지 회차는 정상 집계된다.

### EC-5: 빈 상태 UI (REQ-TREND-007)

- **Given** 빈 결과 응답을 받은 트렌드 탭에서
- **When** 화면이 렌더링되면
- **Then** "분석할 데이터가 없습니다" 메시지가 표시되고 차트 영역은 비어 있다.

## Definition of Done

- [ ] `build_trend_matrix`, `compute_hot_cold` 함수 구현 및 단위 테스트 통과
- [ ] `/api/trend-heatmap`, `/api/hot-cold` 엔드포인트 동작 및 통합 테스트 통과
- [ ] `period` 검증(400), 빈 데이터(200), `recent_n` 경계 처리 검증 완료
- [ ] `/analyze` 트렌드 탭에 히트맵 테이블 + 핫/콜드 카드 표시
- [ ] 테스트 커버리지 85% 이상
- [ ] 기존 706개 테스트 회귀 없음

## 품질 게이트 (Quality Gate)

- ruff lint 통과, 타입/런타임 오류 0
- 신규 함수에 한국어 docstring 및 주석 (code_comments: ko)
- TRUST 5: Tested(85%+), Readable, Unified, Secured(입력 검증), Trackable
