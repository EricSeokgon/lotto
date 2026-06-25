# SPEC-LOTTO-141: 번호 중앙값 분포 분석

## 개요
정렬된 6개 번호 중 3번째와 4번째 번호의 평균(중앙값) 분포 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-141-01: 중앙값 = (3번째 + 4번째) / 2 계산 및 분포 분석
- REQ-141-02: 실제 평균 중앙값 vs 이론적 중앙값(23.0) 비교
- REQ-141-03: 구간(5 단위) 분포 진행 막대
- REQ-141-04: 정수/반정수(0.5) 중앙값 비율 표시
- REQ-141-05: 상위 10개 최빈 중앙값 테이블
- REQ-141-06: 최근 20회차 중앙값 현황 테이블

### 비기능 요구사항
- REQ-141-07: Bootstrap 5 반응형 UI
- REQ-141-08: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_median_dist_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/median-dist` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/median_dist.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_median_dist.py` (10개)

## 인수 기준
- [x] theoretical_avg == 23.0
- [x] int_count + half_count == total
- [x] bucket_list 길이 9
- [x] top_medians 최대 10개
- [x] `/stats/median-dist` HTTP 200 응답
- [x] 전체 테스트 통과 (3363 → 3373)
