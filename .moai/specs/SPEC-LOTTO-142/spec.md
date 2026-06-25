# SPEC-LOTTO-142: 피보나치 번호 분포 분석

## 개요
1~45 내 피보나치 수(1,2,3,5,8,13,21,34) 8개의 당첨 번호 포함 빈도 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-142-01: 피보나치 수 8개 정의 및 포함 개수(0~6) 분포 분석
- REQ-142-02: 실제 평균 포함 수 vs 이론적 기댓값(8/45×6≈1.067) 비교
- REQ-142-03: 개별 피보나치 번호 출현 빈도 순위
- REQ-142-04: 피보나치 0개 포함 회차 비율
- REQ-142-05: 최근 20회차 피보나치 포함 현황 테이블

### 비기능 요구사항
- REQ-142-06: Bootstrap 5 반응형 UI
- REQ-142-07: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_fibonacci_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/fibonacci` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/fibonacci.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_fibonacci.py` (10개)

## 인수 기준
- [x] fib_count == 8
- [x] fib_numbers == {1,2,3,5,8,13,21,34}
- [x] dist_list 길이 7
- [x] freq_list 길이 8
- [x] `/stats/fibonacci` HTTP 200 응답
- [x] 전체 테스트 통과 (3373 → 3383)
