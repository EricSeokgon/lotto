# SPEC-LOTTO-028 구현 계획: 번호 조합 분석기

## 개요

사용자가 입력한 6개 번호 조합에 대해 과거 당첨 데이터 기반 통계를 분석하는
API와 웹 UI를 추가한다. 기존 `analyzer.py`의 빈도/동반 분석 로직을 최대한
재사용하여 신규 코드를 최소화한다.

## 기술 접근

### 1. 조합 분석 로직 (계산 계층)

조합 분석에 필요한 항목은 두 부류로 나뉜다.

**입력만으로 계산 가능 (데이터 무관)**
- `sum`: `sum(numbers)`
- `odd_count` / `even_count`: 홀짝 카운트
- `range_distribution`: 5개 구간(1-10, 11-20, 21-30, 31-40, 41-45) 버킷팅
- `consecutive_count`: 정렬 후 인접 차이가 1인 쌍 카운트

**과거 데이터 필요 (analyzer 재사용)**
- `frequency_score`: 전체 회차 번호별 출현 빈도 → 입력 6개의 평균
- `recent_score`: 최근 20회 출현 빈도 → 입력 6개의 평균
- `companion_score`: 입력 6개의 15개 쌍에 대한 동반 출현 빈도 평균
- `historical_match`: 전체 회차 순회, 입력 조합과 5개 이상 일치 회차 추출
- `verdict`: `frequency_score`와 전체 평균 빈도 비교로 판정

### 2. 배치 위치

- `lotto/analyzer.py`에 `analyze_combination(numbers, draws)` 함수 추가
  (기존 빈도/동반 헬퍼를 내부에서 호출)
- 또는 조합 분석 전용 헬퍼를 `lotto/web/data.py`에 추가하여
  웹 데이터 로딩 흐름과 일관성 유지
- 결정: 순수 통계 로직은 `analyzer.py`에, 데이터 로딩 연동은 `web/data.py`에 배치

### 3. API 엔드포인트

- `lotto/web/` 라우터에 `POST /api/analyze-combination` 추가
- Pydantic 모델로 입력 검증:
  - `numbers: list[int]`, 길이 6, 각 1~45, 중복 불가
  - 검증 실패 시 FastAPI가 자동으로 HTTP 422 반환
- 데이터 부재 시 기본값 처리 (REQ-CMB-003)

### 4. 웹 UI

- `/recommend` 템플릿에 "조합 분석" 섹션 추가
- 6개 번호 입력 폼 + 분석 버튼
- JS fetch로 `POST /api/analyze-combination` 호출, 결과 카드 렌더링
- 클라이언트 측 1차 검증 + 서버 422 응답 시 오류 메시지 표시

## 마일스톤

### Milestone 1 (Priority High): 조합 분석 계산 로직
- `analyze_combination` 순수 함수 구현 (입력 기반 4개 항목)
- 빈도/동반/과거매칭/판정 로직 (analyzer 재사용)
- 데이터 부재 기본값 처리
- 단위 테스트 작성

### Milestone 2 (Priority High): API 엔드포인트
- Pydantic 입력 모델 + 검증 (REQ-CMB-002)
- `POST /api/analyze-combination` 라우터
- 422 응답 케이스 테스트
- 정상 응답 통합 테스트

### Milestone 3 (Priority Medium): 웹 UI
- `/recommend` 페이지 "조합 분석" 섹션 추가 (REQ-CMB-005)
- 입력 폼 + 결과 카드 + 클라이언트 검증 (REQ-CMB-006)
- 웹 렌더링 테스트

## 위험 요소

| 위험 | 영향 | 완화 |
|------|------|------|
| `companion_score` 계산이 15개 쌍 × 전체 회차로 느릴 수 있음 | 응답 지연 | 동반 빈도 사전 집계 캐시 또는 analyzer 기존 동반 맵 재사용 |
| 판정(verdict) 임계값이 주관적 | 사용자 혼란 | ±15% 편차 기준을 명확히 문서화, 테스트로 경계 고정 |
| 데이터 부재 시 0.0 분모 문제 | 0 나눗셈 오류 | 빈도 0일 때 점수 0.0 반환, verdict는 cold 고정 |

## 검증 방법

- 단위 테스트: 알려진 조합에 대한 합계/홀짝/연속/분포 정확도
- 빈도 점수: 고정 회차 데이터에 대한 결정적(deterministic) 결과
- 422 검증: 6개 미만, 범위 초과, 중복 케이스
- 데이터 부재: 빈 회차 입력 시 기본값 반환
- 전체 테스트 통과 + 커버리지 85% 이상
