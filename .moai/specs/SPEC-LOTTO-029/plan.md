# SPEC-LOTTO-029 구현 계획: 회차별 상세 보기

## 개요

특정 회차의 상세 정보를 조회하는 JSON API(`GET /api/draws/{drw_no}`)와
HTML 페이지(`GET /draw/{drw_no}`)를 추가한다. 기존 수집 데이터 로딩
헬퍼를 재사용하며, 새로운 통계 계산은 하지 않는 단순 조회/표시 기능이다.

## 기술 접근

### 1. 데이터 조회 헬퍼

- `lotto/web/data.py`에 `get_draw_detail(drw_no)` 헬퍼 추가
  - 기존 회차 로딩 로직을 사용해 단일 회차 레코드 조회
  - 1등 당첨금/당첨자 데이터(SPEC-LOTTO-022 결과)를 병합
  - 회차 없으면 `None` 반환
- 이전/다음 회차 존재 여부 판단을 위해 최소/최대 회차 번호 조회 헬퍼 활용

### 2. JSON API

- `GET /api/draws/{drw_no}` 라우터 추가
  - `get_draw_detail` 호출
  - 결과 있으면 200 + JSON (REQ-DRW-001)
  - 결과 없으면 `HTTPException(status_code=404)` (REQ-DRW-002)
  - 당첨금/당첨자 없으면 해당 필드 null

### 3. HTML 페이지

- `GET /draw/{drw_no}` 라우터 + Jinja2 템플릿 `draw_detail.html` 추가
  - 회차 있으면 상세 렌더링 (REQ-DRW-003)
  - 당첨 번호/보너스를 색상 볼로 시각화 (기존 다른 페이지의 볼 스타일 재사용)
  - 1등 당첨금/당첨자 수 표시
  - 이전/다음 네비게이션 링크 (경계 처리: REQ-DRW-004)
  - 즐겨찾기 번호 대조 강조 (설정 있을 때만: REQ-DRW-005)
  - 회차 없으면 404 HTML 페이지 반환 (REQ-DRW-007)

### 4. 수집 목록 연동

- `/collect` 템플릿의 회차 목록 각 행 번호에
  `/draw/{drw_no}` 링크 추가 (REQ-DRW-006)

### 5. 네비게이션 경계 로직

- 최소 회차 번호와 최대 회차 번호를 템플릿에 전달
- `drw_no == min_drw_no`이면 이전 링크 숨김/비활성
- `drw_no == max_drw_no`이면 다음 링크 숨김/비활성

## 마일스톤

### Milestone 1 (Priority High): 데이터 조회 + JSON API
- `get_draw_detail(drw_no)` 헬퍼 구현 (당첨금 병합 포함)
- `GET /api/draws/{drw_no}` 라우터 (200/404)
- API 단위/통합 테스트

### Milestone 2 (Priority High): HTML 상세 페이지
- `draw_detail.html` 템플릿 (색상 볼 시각화, 당첨금/당첨자)
- `GET /draw/{drw_no}` 라우터
- 이전/다음 네비게이션 + 경계 처리 (REQ-DRW-004)
- 404 HTML 페이지 처리 (REQ-DRW-007)
- 렌더링 테스트

### Milestone 3 (Priority Medium): 부가 연동
- 즐겨찾기 번호 대조 강조 (REQ-DRW-005)
- `/collect` 목록 상세 링크 추가 (REQ-DRW-006)
- 연동 테스트

## 위험 요소

| 위험 | 영향 | 완화 |
|------|------|------|
| 1등 당첨금 데이터가 일부 회차에만 존재 | null 처리 누락 | 당첨금/당첨자 필드를 nullable로 일관 처리, 템플릿에서 조건부 표시 |
| 최소/최대 회차 조회가 매 요청마다 전체 스캔 | 성능 저하 | 회차 목록 로딩 시 min/max를 함께 계산해 재사용 |
| 즐겨찾기 미설정 시 대조 로직 오류 | 페이지 깨짐 | 설정 부재를 명시적으로 분기, 대조 섹션 자체를 조건부 렌더 |
| `/draw/{drw_no}`와 API 404가 다른 형태여야 함 | 혼동 | API는 JSON 404, 페이지는 HTML 404로 명확히 분리 |

## 검증 방법

- 단위 테스트: `get_draw_detail`의 정상/없음/당첨금-null 케이스
- API 테스트: 존재 회차 200, 미존재 회차 404
- 페이지 테스트: 상세 렌더, 첫/마지막 회차 네비게이션 경계, 404 HTML
- 즐겨찾기 대조: 설정 있음/없음 분기
- `/collect` 링크 존재 확인
- 전체 테스트 통과 + 커버리지 85% 이상
