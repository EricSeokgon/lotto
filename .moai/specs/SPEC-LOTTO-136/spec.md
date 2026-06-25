# SPEC-LOTTO-136: 번호 위치별 분포 분석

## 개요
6개 당첨 번호를 오름차순 정렬했을 때 각 위치(1~6번째)별 번호 분포 통계 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-136-01: 정렬된 6개 번호의 각 위치별 평균·최소·최대·최빈값 계산
- REQ-136-02: 각 위치별 번호 구간(1-9, 10-19, 20-29, 30-39, 40-45) 분포
- REQ-136-03: 각 위치별 상위 5개 최빈 번호 표시
- REQ-136-04: 최근 20회차 위치별 번호 현황 테이블

### 비기능 요구사항
- REQ-136-05: Bootstrap 5 반응형 UI
- REQ-136-06: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_position_dist_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/position-dist` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/position_dist.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_position_dist.py` (10개)

## 인수 기준
- [x] positions 리스트 길이 6
- [x] 각 위치 bucket_list 길이 5
- [x] 최근 회차 최대 20개
- [x] `/stats/position-dist` HTTP 200 응답
- [x] 전체 테스트 통과 (3313 → 3323)

## 커밋
- feat: `6056fe5` feat(SPEC-LOTTO-136): 번호 위치별 분포 분석 구현 (+10 tests)
