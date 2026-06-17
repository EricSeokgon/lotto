# SPEC-LOTTO-101 인수 기준

## 인수 체크리스트

### API 동작 검증

- [ ] **AC-101-001**: `GET /api/stats/fitness-recommend` 기본 요청 시 JSON 배열 반환
  - 각 항목에 `numbers`(6개 정수 목록), `score`(0~100 실수), `grade`(문자열) 포함
  - HTTP 200 응답

- [ ] **AC-101-002**: `min_score=80` 요청 시 모든 항목의 `score`가 80 이상
  - 80 미만 항목이 응답에 포함되지 않음

- [ ] **AC-101-003**: `count=3` 요청 시 응답 항목 수가 최대 3개
  - `pool_size=1000`, `min_score=0` 조건에서 확인

- [ ] **AC-101-004**: 결과가 `score` 기준 내림차순 정렬
  - 첫 번째 항목의 점수가 마지막 항목보다 크거나 같음

- [ ] **AC-101-006**: `min_score=99`, `pool_size=100`으로 조건 미달 시 부분 반환
  - 빈 배열(`[]`)도 HTTP 200으로 유효한 응답

### 파라미터 검증

- [ ] **AC-101-005a**: `count=0` → HTTP 422
- [ ] **AC-101-005b**: `count=21` → HTTP 422
- [ ] **AC-101-005c**: `min_score=-1` → HTTP 422
- [ ] **AC-101-005d**: `min_score=101` → HTTP 422
- [ ] **AC-101-005e**: `pool_size=0` → HTTP 422
- [ ] **AC-101-005f**: `pool_size=5001` → HTTP 422
- [ ] 경계값 허용: `count=1`, `count=20`, `min_score=0`, `min_score=100`, `pool_size=1`, `pool_size=5000` → HTTP 200

### 웹 페이지 검증

- [ ] **AC-101-007**: `GET /stats/fitness-recommend` → HTTP 200, HTML 응답
  - 파라미터 설정 폼(count, min_score, pool_size) 포함
  - 결과 테이블 영역 포함

- [ ] **AC-101-008**: `base.html` 기반 모든 페이지에 "적합도 추천" 내비게이션 탭 존재
  - `/stats/fitness-recommend` 링크로 연결

### 품질 게이트

- [ ] `pytest tests/test_fitness_recommend.py` — 모든 테스트 통과
- [ ] `mypy lotto/web/routes/api.py lotto/web/routes/pages.py` — 타입 오류 0건
- [ ] Python 3.9 호환성: `str | None` 대신 `Optional[str]` 사용 확인

## 테스트 실행 방법

```bash
# 전체 테스트
pytest tests/test_fitness_recommend.py -v

# 커버리지 포함
pytest tests/test_fitness_recommend.py -v --cov=lotto/web/routes

# 특정 테스트
pytest tests/test_fitness_recommend.py::test_fitness_recommend_api_min_score_filter -v
```

## 관련 SPEC

- SPEC-LOTTO-100: `get_fitness_score()` 함수 구현 (선행 의존성)
