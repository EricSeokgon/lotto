# SPEC-LOTTO-140: 번호 합계 분포 분석

## 개요
6개 당첨 번호의 합계 통계 및 구간별 분포 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-140-01: 합계 최솟값·최댓값·평균 및 이론적 평균(138) 대비 차이 표시
- REQ-140-02: 합계 구간(20 단위) 분포 진행 막대
- REQ-140-03: 상위 10개 최빈 합계 값 표시
- REQ-140-04: 최빈 합계 및 최빈 구간 하이라이트
- REQ-140-05: 최근 20회차 합계 현황 테이블

### 비기능 요구사항
- REQ-140-06: Bootstrap 5 반응형 UI
- REQ-140-07: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_sum_distribution_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/sum-distribution` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/sum_distribution.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_sum_distribution.py` (10개)

## 인수 기준
- [x] theoretical_avg == 138
- [x] actual_min >= 21, actual_max <= 255
- [x] top_sums 최대 10개
- [x] `/stats/sum-distribution` HTTP 200 응답
- [x] 전체 테스트 통과 (3353 → 3363)
