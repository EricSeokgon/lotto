# SPEC-LOTTO-026 구현 계획

## 기술 접근 (Technical Approach)

기존 `analyzer.py`에 트렌드 집계 함수를 추가하고, `api.py`에 두 개의 신규
엔드포인트를 노출한다. 회차 데이터에 포함된 추첨일(draw date)을 파싱하여
연도/분기 라벨로 그룹화하고, 번호별 출현 횟수를 누적해 행렬을 구성한다.
핫/콜드 계산은 최근 N회차 슬라이스와 전체 평균 비율을 비교하는 단순 통계로 처리한다.
모든 계산은 메모리 내에서 수행하며 별도 영속화는 하지 않는다.

## 구현 단계 (Phases)

### Phase 1: 분석 로직 (우선순위 High)

- `lotto/analyzer.py`
  - `build_trend_matrix(draws, period="yearly") -> dict`: 기간 라벨 그룹화 + 번호별 출현 행렬 생성
  - `compute_hot_cold(draws, recent_n=20) -> dict`: 최근 N회 vs 전체 평균 비교, 상위/하위 10개 산출
  - 추첨일 → 연도/분기 라벨 변환 헬퍼 (`_period_label`)
  - 빈 데이터 / `recent_n` 초과 등 경계 처리 포함

### Phase 2: API 엔드포인트 (우선순위 High)

- `lotto/web/routes/api.py`
  - `GET /api/trend-heatmap` 추가: `period` 쿼리 검증(400) 후 `build_trend_matrix` 호출
  - `GET /api/hot-cold` 추가: `recent_n` 파싱(최소 1) 후 `compute_hot_cold` 호출
  - 데이터 없을 때 빈 결과 + HTTP 200 보장

### Phase 3: 프론트엔드 트렌드 탭 (우선순위 Medium)

- `lotto/web/templates/analyze.html` (또는 해당 페이지 템플릿)
  - "트렌드" 탭 추가, 연도/분기 토글 버튼
  - Chart.js 히트맵용 색상 테이블 렌더링 (행렬 → 셀 색 농도 매핑)
  - 핫/콜드 카드 영역 추가
  - 빈 상태 메시지 처리 (REQ-TREND-007)
- 필요 시 `lotto/web/static/js/`에 트렌드 탭 전용 스크립트 추가

## 생성/수정 파일 (Files)

| 구분 | 경로 | 작업 |
|------|------|------|
| 수정 | `lotto/analyzer.py` | 트렌드/핫콜드 집계 함수 추가 |
| 수정 | `lotto/web/routes/api.py` | `/api/trend-heatmap`, `/api/hot-cold` 추가 |
| 수정 | `lotto/web/templates/analyze.html` | 트렌드 탭 마크업 추가 |
| 수정(선택) | `lotto/web/static/js/trend.js` | 히트맵/카드 렌더링 스크립트 |
| 생성 | `tests/test_trend_analysis.py` | 집계 로직 + API 단위/통합 테스트 |

## 위험 요소 (Risks)

- 추첨일 형식이 회차마다 일관되지 않을 가능성 → 파싱 실패 시 해당 회차 스킵 + 로그.
- 분기 라벨 정렬(연도-분기 순) 보장 필요 → 정렬 키를 명시적으로 지정.
- Chart.js 기본 차트로 히트맵 구현 시 셀 표현 한계 → 색상 테이블(HTML table + 배경색)로 대체.

## 의존성 (Dependencies)

- 신규 외부 패키지 없음 (표준 라이브러리 + 기존 FastAPI/Jinja2/Chart.js 사용).
