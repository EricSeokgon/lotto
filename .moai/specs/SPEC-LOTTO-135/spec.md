# SPEC-LOTTO-135: 특수 번호(삼각수·제곱수) 분석

## 개요
1~45 범위 내 삼각수와 제곱수의 당첨 번호 포함 빈도 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-135-01: 삼각수(1,3,6,10,15,21,28,36,45) 9개 정의 및 당첨 번호 포함 빈도 분석
- REQ-135-02: 제곱수(1,4,9,16,25,36) 6개 정의 및 당첨 번호 포함 빈도 분석
- REQ-135-03: 교집합({1,36}) 2개 표시
- REQ-135-04: 회차별 삼각수/제곱수 포함 개수 분포(0~6) 통계
- REQ-135-05: 이론적 기댓값(삼각수: 9/45×6≈1.2, 제곱수: 6/45×6≈0.8) 대비 실제 평균 비교
- REQ-135-06: 삼각수·제곱수 개별 번호 출현 빈도 순위
- REQ-135-07: 최근 20회차 특수 번호 포함 현황 테이블

### 비기능 요구사항
- REQ-135-08: Bootstrap 5 반응형 UI
- REQ-135-09: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_special_numbers_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/special-numbers` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/special_numbers.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_special_numbers.py` (10개)

## 인수 기준
- [x] `get_special_numbers_analysis()` 함수 반환 구조 검증
- [x] 삼각수 9개, 제곱수 6개, 교집합 2개 확인
- [x] 분포 리스트 길이 7 (0~6개)
- [x] 최근 회차 리스트 최대 20개
- [x] `/stats/special-numbers` HTTP 200 응답
- [x] 전체 테스트 통과 (3303 → 3313)

## 커밋
- feat: `ff4226f` feat(SPEC-LOTTO-135): 특수 번호(삼각수·제곱수) 분석 구현 (+10 tests, 3303→3313)
