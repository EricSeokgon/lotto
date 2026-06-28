# SPEC-LOTTO-146: 7의 배수 분포 분석

## 개요
1~45 내 7의 배수(7,14,21,28,35,42) 6개의 당첨 번호 포함 빈도 분석 페이지 구현.

## 요구사항

### 기능 요구사항
- REQ-146-01: 7의 배수 6개 정의 및 포함 개수(0~6) 분포 분석
- REQ-146-02: 실제 평균 vs 이론적 기댓값(≈0.8) 비교
- REQ-146-03: 개별 7의 배수 출현 빈도 순위
- REQ-146-04: 7의 배수 0개 포함 회차 비율
- REQ-146-05: 최근 20회차 포함 현황 테이블

### 비기능 요구사항
- REQ-146-06: Bootstrap 5 반응형 UI
- REQ-146-07: 데스크톱·모바일 양쪽 내비게이션에 링크 추가

## 기술 구현
- 분석 함수: `get_multiples7_analysis()` in `lotto/web/data.py`
- 라우트: `GET /stats/multiples-7` in `lotto/web/routes/pages.py`
- 템플릿: `lotto/web/templates/multiples7.html`
- 내비게이션: `lotto/web/templates/base.html` (데스크톱·모바일)
- 테스트: `tests/test_multiples7.py` (10개)

## 인수 기준
- [x] mult7_count == 6
- [x] expected == round(6/45*6, 3)
- [x] dist_list 길이 7
- [x] freq_list 길이 6
- [x] `/stats/multiples-7` HTTP 200 응답
- [x] 전체 테스트 통과 (3413 → 3423)
