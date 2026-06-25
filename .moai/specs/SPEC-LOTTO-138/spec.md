# SPEC-LOTTO-138: 번호 십의 자리 분포 분석

## 개요
당첨 번호를 십의 자리 그룹(01~09, 10~19, 20~29, 30~39, 40~45)별로 분포 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-138-01: 5개 그룹(01~09/10~19/20~29/30~39/40~45) 풀 크기 및 기댓값 계산
- REQ-138-02: 그룹별 총 출현·평균 및 이론적 기댓값 대비 차이 표시
- REQ-138-03: 그룹별 회차당 포함 개수 분포(0~6) 통계
- REQ-138-04: 상위 10개 그룹 조합 패턴(5-tuple) 빈도 분석
- REQ-138-05: 최근 20회차 그룹별 분포 현황 테이블

### 비기능 요구사항
- REQ-138-06: Bootstrap 5 반응형 UI
- REQ-138-07: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_tens_digit_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/tens-digit` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/tens_digit.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_tens_digit.py` (10개)

## 인수 기준
- [x] group_stats 길이 5
- [x] 풀 크기 합계 45
- [x] dist_list 길이 7
- [x] top_patterns 최대 10개
- [x] `/stats/tens-digit` HTTP 200 응답
- [x] 전체 테스트 통과 (3333 → 3343)

## 커밋
- feat: `dbd58ed` feat(SPEC-LOTTO-138): 번호 십의 자리 분포 분석 구현 (+10 tests, 3333→3343)
